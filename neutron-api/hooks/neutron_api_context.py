from charmhelpers.core.hookenv import (
    config,
    relation_ids,
    related_units,
    relation_get,
)
from charmhelpers.contrib.openstack import context
from charmhelpers.contrib.hahelpers.cluster import (
    determine_api_port,
    determine_apache_port,
)


def get_l2population():
    plugin = config('neutron-plugin')
    return config('l2-population') if plugin == "ovs" else False


def get_overlay_network_type():
    overlay_net = config('overlay-network-type')
    if overlay_net not in ['vxlan', 'gre']:
        raise Exception('Unsupported overlay-network-type')
    return overlay_net


class ApacheSSLContext(context.ApacheSSLContext):

    interfaces = ['https']
    external_ports = []
    service_namespace = 'neutron'

    def __call__(self):
        # late import to work around circular dependency
        from neutron_api_utils import determine_ports
        self.external_ports = determine_ports()
        return super(ApacheSSLContext, self).__call__()


class IdentityServiceContext(context.IdentityServiceContext):

    def __call__(self):
        ctxt = super(IdentityServiceContext, self).__call__()
        if not ctxt:
            return
        ctxt['region'] = config('region')
        return ctxt


class NeutronCCContext(context.NeutronContext):
    interfaces = []

    @property
    def network_manager(self):
        return 'neutron'

    @property
    def plugin(self):
        return config('neutron-plugin')

    @property
    def neutron_security_groups(self):
        return config('neutron-security-groups')

    @property
    def neutron_l2_population(self):
        return get_l2population()

    @property
    def neutron_overlay_network_type(self):
        return get_overlay_network_type()

    # Do not need the plugin agent installed on the api server
    def _ensure_packages(self):
        pass

    # Do not need the flag on the api server
    def _save_flag_file(self):
        pass

    def __call__(self):
        from neutron_api_utils import api_port
        ctxt = super(NeutronCCContext, self).__call__()
        if config('neutron-plugin') == 'nsx':
            ctxt['nsx_username'] = config('nsx-username')
            ctxt['nsx_password'] = config('nsx-password')
            ctxt['nsx_tz_uuid'] = config('nsx-tz-uuid')
            ctxt['nsx_l3_uuid'] = config('nsx-l3-uuid')
            if 'nsx-controllers' in config():
                ctxt['nsx_controllers'] = \
                    ','.join(config('nsx-controllers').split())
                ctxt['nsx_controllers_list'] = \
                    config('nsx-controllers').split()
        ctxt['l2_population'] = self.neutron_l2_population
        ctxt['overlay_network_type'] = self.neutron_overlay_network_type
        ctxt['external_network'] = config('neutron-external-network')
        ctxt['verbose'] = config('verbose')
        ctxt['debug'] = config('debug')
        ctxt['neutron_bind_port'] = \
            determine_api_port(api_port('neutron-server'),
                               singlenode_mode=True)
        for rid in relation_ids('neutron-api'):
            for unit in related_units(rid):
                rdata = relation_get(rid=rid, unit=unit)
                cell_type = rdata.get('cell_type')
                ctxt['nova_url'] = rdata.get('nova_url')
                ctxt['restart_trigger'] = rdata.get('restart_trigger')
                # If there are multiple nova-cloud-controllers joined to this
                # service in a cell deployment then ignore the non-api cell
                # ones
                if cell_type and not cell_type == "api":
                    continue
                if ctxt['nova_url']:
                    return ctxt
        return ctxt


class HAProxyContext(context.HAProxyContext):
    interfaces = ['ceph']

    def __call__(self):
        '''
        Extends the main charmhelpers HAProxyContext with a port mapping
        specific to this charm.
        Also used to extend nova.conf context with correct api_listening_ports
        '''
        from neutron_api_utils import api_port
        ctxt = super(HAProxyContext, self).__call__()

        # Apache ports
        a_neutron_api = determine_apache_port(api_port('neutron-server'),
                                              singlenode_mode=True)

        port_mapping = {
            'neutron-server': [
                api_port('neutron-server'), a_neutron_api]
        }

        ctxt['neutron_bind_port'] = determine_api_port(
            api_port('neutron-server'),
            singlenode_mode=True,
        )

        # for haproxy.conf
        ctxt['service_ports'] = port_mapping
        return ctxt
