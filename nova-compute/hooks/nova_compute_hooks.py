#!/usr/bin/python
import sys

from charmhelpers.core.hookenv import (
    Hooks,
    config,
    is_relation_made,
    log,
    INFO,
    ERROR,
    relation_ids,
    relation_get,
    relation_set,
    service_name,
    unit_get,
    UnregisteredHookError,
)
from charmhelpers.core.host import (
    restart_on_change,
)

from charmhelpers.fetch import (
    apt_install,
    apt_update,
    filter_installed_packages,
)

from charmhelpers.contrib.openstack.utils import (
    configure_installation_source,
    openstack_upgrade_available,
)

from charmhelpers.contrib.storage.linux.ceph import (
    ensure_ceph_keyring,
    CephBrokerRq,
    CephBrokerRsp,
)
from charmhelpers.payload.execd import execd_preinstall
from nova_compute_utils import (
    create_libvirt_secret,
    determine_packages,
    import_authorized_keys,
    import_keystone_ca_cert,
    initialize_ssh_keys,
    migration_enabled,
    network_manager,
    neutron_plugin,
    do_openstack_upgrade,
    public_ssh_key,
    restart_map,
    services,
    register_configs,
    NOVA_CONF,
    QUANTUM_CONF, NEUTRON_CONF,
    ceph_config_file, CEPH_SECRET,
    enable_shell, disable_shell,
    fix_path_ownership,
    assert_charm_supports_ipv6
)

from charmhelpers.contrib.network.ip import (
    get_ipv6_addr
)

from nova_compute_context import (
    CEPH_SECRET_UUID,
    assert_libvirt_imagebackend_allowed
)
from charmhelpers.contrib.charmsupport import nrpe
from charmhelpers.core.sysctl import create as create_sysctl

from socket import gethostname

hooks = Hooks()
CONFIGS = register_configs()


@hooks.hook()
def install():
    execd_preinstall()
    configure_installation_source(config('openstack-origin'))
    apt_update()
    apt_install(determine_packages(), fatal=True)


@hooks.hook('config-changed')
@restart_on_change(restart_map())
def config_changed():
    if config('prefer-ipv6'):
        assert_charm_supports_ipv6()

    global CONFIGS
    if openstack_upgrade_available('nova-common'):
        CONFIGS = do_openstack_upgrade()

    sysctl_dict = config('sysctl')
    if sysctl_dict:
        create_sysctl(sysctl_dict, '/etc/sysctl.d/50-nova-compute.conf')

    if migration_enabled() and config('migration-auth-type') == 'ssh':
        # Check-in with nova-c-c and register new ssh key, if it has just been
        # generated.
        initialize_ssh_keys()
        import_authorized_keys()

    if config('enable-resize') is True:
        enable_shell(user='nova')
        initialize_ssh_keys(user='nova')
        import_authorized_keys(user='nova', prefix='nova')
    else:
        disable_shell(user='nova')

    if config('instances-path') is not None:
        fp = config('instances-path')
        fix_path_ownership(fp, user='nova')

    [compute_joined(rid) for rid in relation_ids('cloud-compute')]

    update_nrpe_config()

    CONFIGS.write_all()


@hooks.hook('amqp-relation-joined')
def amqp_joined(relation_id=None):
    relation_set(relation_id=relation_id,
                 username=config('rabbit-user'),
                 vhost=config('rabbit-vhost'))


@hooks.hook('amqp-relation-changed')
@hooks.hook('amqp-relation-departed')
@restart_on_change(restart_map())
def amqp_changed():
    if 'amqp' not in CONFIGS.complete_contexts():
        log('amqp relation incomplete. Peer not ready?')
        return
    CONFIGS.write(NOVA_CONF)
    # No need to write NEUTRON_CONF if neutron-plugin is managing it
    if not relation_ids('neutron-plugin'):
        if network_manager() == 'quantum' and neutron_plugin() == 'ovs':
            CONFIGS.write(QUANTUM_CONF)
        if network_manager() == 'neutron' and neutron_plugin() == 'ovs':
            CONFIGS.write(NEUTRON_CONF)


@hooks.hook('shared-db-relation-joined')
def db_joined(rid=None):
    if is_relation_made('pgsql-db'):
        # error, postgresql is used
        e = ('Attempting to associate a mysql database when there is already '
             'associated a postgresql one')
        log(e, level=ERROR)
        raise Exception(e)

    relation_set(relation_id=rid,
                 nova_database=config('database'),
                 nova_username=config('database-user'),
                 nova_hostname=unit_get('private-address'))


@hooks.hook('pgsql-db-relation-joined')
def pgsql_db_joined():
    if is_relation_made('shared-db'):
        # raise error
        e = ('Attempting to associate a postgresql database when'
             ' there is already associated a mysql one')
        log(e, level=ERROR)
        raise Exception(e)

    relation_set(database=config('database'))


@hooks.hook('shared-db-relation-changed')
@restart_on_change(restart_map())
def db_changed():
    if 'shared-db' not in CONFIGS.complete_contexts():
        log('shared-db relation incomplete. Peer not ready?')
        return
    CONFIGS.write(NOVA_CONF)


@hooks.hook('pgsql-db-relation-changed')
@restart_on_change(restart_map())
def postgresql_db_changed():
    if 'pgsql-db' not in CONFIGS.complete_contexts():
        log('pgsql-db relation incomplete. Peer not ready?')
        return
    CONFIGS.write(NOVA_CONF)


@hooks.hook('image-service-relation-changed')
@restart_on_change(restart_map())
def image_service_changed():
    if 'image-service' not in CONFIGS.complete_contexts():
        log('image-service relation incomplete. Peer not ready?')
        return
    CONFIGS.write(NOVA_CONF)


@hooks.hook('cloud-compute-relation-joined')
def compute_joined(rid=None):
    # NOTE(james-page) in MAAS environments the actual hostname is a CNAME
    # record so won't get scanned based on private-address which is an IP
    # add the hostname configured locally to the relation.
    settings = {
        'hostname': gethostname()
    }
    if config('prefer-ipv6'):
        settings = {'private-address': get_ipv6_addr()[0]}
    if migration_enabled():
        auth_type = config('migration-auth-type')
        settings['migration_auth_type'] = auth_type
        if auth_type == 'ssh':
            settings['ssh_public_key'] = public_ssh_key()
        relation_set(relation_id=rid, **settings)
    if config('enable-resize'):
        settings['nova_ssh_public_key'] = public_ssh_key(user='nova')
        relation_set(relation_id=rid, **settings)


@hooks.hook('cloud-compute-relation-changed')
@restart_on_change(restart_map())
def compute_changed():
    # rewriting all configs to pick up possible net or vol manager
    # config advertised from controller.
    CONFIGS.write_all()
    import_authorized_keys()
    import_authorized_keys(user='nova', prefix='nova')
    import_keystone_ca_cert()


@hooks.hook('ceph-relation-joined')
@restart_on_change(restart_map())
def ceph_joined():
    apt_install(filter_installed_packages(['ceph-common']), fatal=True)


@hooks.hook('ceph-relation-changed')
@restart_on_change(restart_map())
def ceph_changed():
    if 'ceph' not in CONFIGS.complete_contexts():
        log('ceph relation incomplete. Peer not ready?')
        return

    if not ensure_ceph_keyring(service=service_name(), user='nova',
                               group='nova'):
        log('Could not create ceph keyring: peer not ready?')
        return

    CONFIGS.write(ceph_config_file())
    CONFIGS.write(CEPH_SECRET)
    CONFIGS.write(NOVA_CONF)

    # With some refactoring, this can move into NovaComputeCephContext
    # and allow easily extended to support other compute flavors.
    if config('virt-type') in ['kvm', 'qemu', 'lxc']:
        create_libvirt_secret(secret_file=CEPH_SECRET,
                              secret_uuid=CEPH_SECRET_UUID,
                              key=relation_get('key'))

    if (config('libvirt-image-backend') == 'rbd' and
            assert_libvirt_imagebackend_allowed()):
        settings = relation_get()
        if settings and 'broker_rsp' in settings:
            rsp = CephBrokerRsp(settings['broker_rsp'])
            # Non-zero return code implies failure
            if rsp.exit_code:
                log("Ceph broker request failed (rc=%s, msg=%s)" %
                    (rsp.exit_code, rsp.exit_msg), level=ERROR)
                return

            log("Ceph broker request succeeded (rc=%s, msg=%s)" %
                (rsp.exit_code, rsp.exit_msg), level=INFO)
        else:
            rq = CephBrokerRq()
            replicas = config('ceph-osd-replication-count')
            rq.add_op_create_pool(name=config('rbd-pool'),
                                  replica_count=replicas)
            for rid in relation_ids('ceph'):
                relation_set(broker_req=rq.request)
                log("Request(s) sent to Ceph broker (rid=%s)" % (rid))


@hooks.hook('amqp-relation-broken',
            'ceph-relation-broken',
            'image-service-relation-broken',
            'shared-db-relation-broken',
            'pgsql-db-relation-broken')
@restart_on_change(restart_map())
def relation_broken():
    CONFIGS.write_all()


@hooks.hook('upgrade-charm')
def upgrade_charm():
    for r_id in relation_ids('amqp'):
        amqp_joined(relation_id=r_id)
    update_nrpe_config()


@hooks.hook('nova-ceilometer-relation-changed')
@restart_on_change(restart_map())
def nova_ceilometer_relation_changed():
    CONFIGS.write_all()


@hooks.hook('nrpe-external-master-relation-joined',
            'nrpe-external-master-relation-changed')
def update_nrpe_config():
    # python-dbus is used by check_upstart_job
    apt_install('python-dbus')
    hostname = nrpe.get_nagios_hostname()
    current_unit = nrpe.get_nagios_unit_name()
    nrpe_setup = nrpe.NRPE(hostname=hostname)
    nrpe.add_init_service_checks(nrpe_setup, services(), current_unit)
    nrpe_setup.write()


def main():
    try:
        hooks.execute(sys.argv)
    except UnregisteredHookError as e:
        log('Unknown hook {} - skipping.'.format(e))


if __name__ == '__main__':
    main()
