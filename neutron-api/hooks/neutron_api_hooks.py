#!/usr/bin/python

import sys
import uuid

from subprocess import check_call
from charmhelpers.core.hookenv import (
    Hooks,
    UnregisteredHookError,
    config,
    is_relation_made,
    log,
    ERROR,
    relation_get,
    relation_ids,
    relation_set,
    open_port,
    unit_get,
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
    sync_db_with_multi_ipv6_addresses
)

from neutron_api_utils import (
    NEUTRON_CONF,
    api_port,
    determine_packages,
    determine_ports,
    do_openstack_upgrade,
    register_configs,
    restart_map,
    services,
    setup_ipv6
)
from neutron_api_context import (
    get_l2population,
    get_overlay_network_type,
)

from charmhelpers.contrib.hahelpers.cluster import (
    get_hacluster_config,
)

from charmhelpers.payload.execd import execd_preinstall

from charmhelpers.contrib.openstack.ip import (
    canonical_url,
    PUBLIC, INTERNAL, ADMIN
)

from charmhelpers.contrib.network.ip import (
    get_iface_for_address,
    get_netmask_for_address,
    get_address_in_network,
    get_ipv6_addr,
    is_ipv6
)

from charmhelpers.contrib.openstack.context import ADDRESS_TYPES

from charmhelpers.contrib.charmsupport import nrpe

hooks = Hooks()
CONFIGS = register_configs()


def configure_https():
    '''
    Enables SSL API Apache config if appropriate and kicks identity-service
    with any required api updates.
    '''
    # need to write all to ensure changes to the entire request pipeline
    # propagate (c-api, haprxy, apache)
    CONFIGS.write_all()
    if 'https' in CONFIGS.complete_contexts():
        cmd = ['a2ensite', 'openstack_https_frontend']
        check_call(cmd)
    else:
        cmd = ['a2dissite', 'openstack_https_frontend']
        check_call(cmd)

    for rid in relation_ids('identity-service'):
        identity_joined(rid=rid)


@hooks.hook()
def install():
    execd_preinstall()
    configure_installation_source(config('openstack-origin'))
    apt_update()
    apt_install(determine_packages(), fatal=True)
    [open_port(port) for port in determine_ports()]


@hooks.hook('upgrade-charm')
@hooks.hook('config-changed')
@restart_on_change(restart_map(), stopstart=True)
def config_changed():
    apt_install(filter_installed_packages(determine_packages()),
                fatal=True)
    if config('prefer-ipv6'):
        setup_ipv6()
        sync_db_with_multi_ipv6_addresses(config('database'),
                                          config('database-user'))

    global CONFIGS
    if openstack_upgrade_available('neutron-server'):
        do_openstack_upgrade(CONFIGS)
    configure_https()
    update_nrpe_config()
    CONFIGS.write_all()
    for r_id in relation_ids('neutron-api'):
        neutron_api_relation_joined(rid=r_id)
    for r_id in relation_ids('neutron-plugin-api'):
        neutron_plugin_api_relation_joined(rid=r_id)
    for r_id in relation_ids('amqp'):
        amqp_joined(relation_id=r_id)
    for r_id in relation_ids('identity-service'):
        identity_joined(rid=r_id)
    [cluster_joined(rid) for rid in relation_ids('cluster')]


@hooks.hook('amqp-relation-joined')
def amqp_joined(relation_id=None):
    relation_set(relation_id=relation_id,
                 username=config('rabbit-user'), vhost=config('rabbit-vhost'))


@hooks.hook('amqp-relation-changed')
@hooks.hook('amqp-relation-departed')
@restart_on_change(restart_map())
def amqp_changed():
    if 'amqp' not in CONFIGS.complete_contexts():
        log('amqp relation incomplete. Peer not ready?')
        return
    CONFIGS.write(NEUTRON_CONF)


@hooks.hook('shared-db-relation-joined')
def db_joined():
    if is_relation_made('pgsql-db'):
        # error, postgresql is used
        e = ('Attempting to associate a mysql database when there is already '
             'associated a postgresql one')
        log(e, level=ERROR)
        raise Exception(e)

    if config('prefer-ipv6'):
        sync_db_with_multi_ipv6_addresses(config('database'),
                                          config('database-user'))
    else:
        host = unit_get('private-address')
        relation_set(database=config('database'),
                     username=config('database-user'),
                     hostname=host)


@hooks.hook('pgsql-db-relation-joined')
def pgsql_neutron_db_joined():
    if is_relation_made('shared-db'):
        # raise error
        e = ('Attempting to associate a postgresql database'
             ' when there is already associated a mysql one')
        log(e, level=ERROR)
        raise Exception(e)

    relation_set(database=config('database'))


@hooks.hook('shared-db-relation-changed')
@restart_on_change(restart_map())
def db_changed():
    if 'shared-db' not in CONFIGS.complete_contexts():
        log('shared-db relation incomplete. Peer not ready?')
        return
    CONFIGS.write_all()


@hooks.hook('pgsql-db-relation-changed')
@restart_on_change(restart_map())
def postgresql_neutron_db_changed():
    CONFIGS.write(NEUTRON_CONF)


@hooks.hook('amqp-relation-broken',
            'identity-service-relation-broken',
            'shared-db-relation-broken',
            'pgsql-db-relation-broken')
def relation_broken():
    CONFIGS.write_all()


@hooks.hook('identity-service-relation-joined')
def identity_joined(rid=None, relation_trigger=False):
    public_url = '{}:{}'.format(canonical_url(CONFIGS, PUBLIC),
                                api_port('neutron-server'))
    admin_url = '{}:{}'.format(canonical_url(CONFIGS, ADMIN),
                               api_port('neutron-server'))
    internal_url = '{}:{}'.format(canonical_url(CONFIGS, INTERNAL),
                                  api_port('neutron-server')
                                  )
    rel_settings = {
        'quantum_service': 'quantum',
        'quantum_region': config('region'),
        'quantum_public_url': public_url,
        'quantum_admin_url': admin_url,
        'quantum_internal_url': internal_url,
    }
    if relation_trigger:
        rel_settings['relation_trigger'] = str(uuid.uuid4())
    relation_set(relation_id=rid, relation_settings=rel_settings)


@hooks.hook('identity-service-relation-changed')
@restart_on_change(restart_map())
def identity_changed():
    if 'identity-service' not in CONFIGS.complete_contexts():
        log('identity-service relation incomplete. Peer not ready?')
        return
    CONFIGS.write(NEUTRON_CONF)
    for r_id in relation_ids('neutron-api'):
        neutron_api_relation_joined(rid=r_id)
    configure_https()


@hooks.hook('neutron-api-relation-joined')
def neutron_api_relation_joined(rid=None):
    base_url = canonical_url(CONFIGS, INTERNAL)
    neutron_url = '%s:%s' % (base_url, api_port('neutron-server'))
    relation_data = {
        'neutron-url': neutron_url,
        'neutron-plugin': config('neutron-plugin'),
    }
    if config('neutron-security-groups'):
        relation_data['neutron-security-groups'] = "yes"
    else:
        relation_data['neutron-security-groups'] = "no"
    relation_set(relation_id=rid, **relation_data)
    # Nova-cc may have grabbed the quantum endpoint so kick identity-service
    # relation to register that its here
    for r_id in relation_ids('identity-service'):
        identity_joined(rid=r_id, relation_trigger=True)


@hooks.hook('neutron-api-relation-changed')
@restart_on_change(restart_map())
def neutron_api_relation_changed():
    CONFIGS.write(NEUTRON_CONF)


@hooks.hook('neutron-plugin-api-relation-joined')
def neutron_plugin_api_relation_joined(rid=None):
    if config('neutron-plugin') == 'nsx':
        relation_data = {
            'nsx-username': config('nsx-username'),
            'nsx-password': config('nsx-password'),
            'nsx-cluster-name': config('nsx-cluster-name'),
            'nsx-tz-uuid': config('nsx-tz-uuid'),
            'nsx-l3-uuid': config('nsx-l3-uuid'),
            'nsx-controllers': config('nsx-controllers'),
        }
    elif config('neutron-plugin') == 'midonet':
        relation_data = {
            'midonet_uri': "http://%s:8080/midonet-api" \
                 % config('controller-ip'),
            'username': config('midonet-username'),
            'password': config('midonet-password'),
            'project_id': config('midonet-projectid')
        }
    else:
        relation_data = {
            'neutron-security-groups': config('neutron-security-groups'),
            'l2-population': get_l2population(),
            'overlay-network-type': get_overlay_network_type(),
        }
    relation_set(relation_id=rid, **relation_data)


@hooks.hook('cluster-relation-joined')
def cluster_joined(relation_id=None):
    for addr_type in ADDRESS_TYPES:
        address = get_address_in_network(
            config('os-{}-network'.format(addr_type))
        )
        if address:
            relation_set(
                relation_id=relation_id,
                relation_settings={'{}-address'.format(addr_type): address}
            )
    if config('prefer-ipv6'):
        private_addr = get_ipv6_addr(exc_list=[config('vip')])[0]
        relation_set(relation_id=relation_id,
                     relation_settings={'private-address': private_addr})


@hooks.hook('cluster-relation-changed',
            'cluster-relation-departed')
@restart_on_change(restart_map(), stopstart=True)
def cluster_changed():
    CONFIGS.write_all()


@hooks.hook('ha-relation-joined')
def ha_joined():
    cluster_config = get_hacluster_config()
    resources = {
        'res_neutron_haproxy': 'lsb:haproxy',
    }
    resource_params = {
        'res_neutron_haproxy': 'op monitor interval="5s"'
    }
    vip_group = []
    for vip in cluster_config['vip'].split():
        if is_ipv6(vip):
            res_neutron_vip = 'ocf:heartbeat:IPv6addr'
            vip_params = 'ipv6addr'
        else:
            res_neutron_vip = 'ocf:heartbeat:IPaddr2'
            vip_params = 'ip'

        iface = (get_iface_for_address(vip) or
                 config('vip_iface'))
        netmask = (get_netmask_for_address(vip) or
                   config('vip_cidr'))

        if iface is not None:
            vip_key = 'res_neutron_{}_vip'.format(iface)
            resources[vip_key] = res_neutron_vip
            resource_params[vip_key] = (
                'params {ip}="{vip}" cidr_netmask="{netmask}" '
                'nic="{iface}"'.format(ip=vip_params,
                                       vip=vip,
                                       iface=iface,
                                       netmask=netmask)
            )
            vip_group.append(vip_key)

    if len(vip_group) >= 1:
        relation_set(groups={'grp_neutron_vips': ' '.join(vip_group)})

    init_services = {
        'res_neutron_haproxy': 'haproxy'
    }
    clones = {
        'cl_nova_haproxy': 'res_neutron_haproxy'
    }
    relation_set(init_services=init_services,
                 corosync_bindiface=cluster_config['ha-bindiface'],
                 corosync_mcastport=cluster_config['ha-mcastport'],
                 resources=resources,
                 resource_params=resource_params,
                 clones=clones)


@hooks.hook('ha-relation-changed')
def ha_changed():
    clustered = relation_get('clustered')
    if not clustered or clustered in [None, 'None', '']:
        log('ha_changed: hacluster subordinate'
            ' not fully clustered: %s' % clustered)
        return
    log('Cluster configured, notifying other services and updating '
        'keystone endpoint configuration')
    for rid in relation_ids('identity-service'):
        identity_joined(rid=rid)
    for rid in relation_ids('neutron-api'):
        neutron_api_relation_joined(rid=rid)


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
