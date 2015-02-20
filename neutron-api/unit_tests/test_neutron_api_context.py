from test_utils import CharmTestCase
from mock import patch
import neutron_api_context as context
import charmhelpers
TO_PATCH = [
    'relation_get',
    'relation_ids',
    'related_units',
    'config',
    'determine_api_port',
    'determine_apache_port'
]


class IdentityServiceContext(CharmTestCase):

    def setUp(self):
        super(IdentityServiceContext, self).setUp(context, TO_PATCH)
        self.relation_get.side_effect = self.test_relation.get
        self.config.side_effect = self.test_config.get
        self.test_config.set('region', 'region457')
        self.test_config.set('prefer-ipv6', False)

    @patch.object(charmhelpers.contrib.openstack.context, 'format_ipv6_addr')
    @patch.object(charmhelpers.contrib.openstack.context, 'context_complete')
    @patch.object(charmhelpers.contrib.openstack.context, 'relation_get')
    @patch.object(charmhelpers.contrib.openstack.context, 'related_units')
    @patch.object(charmhelpers.contrib.openstack.context, 'relation_ids')
    @patch.object(charmhelpers.contrib.openstack.context, 'log')
    def test_ids_ctxt(self, _log, _rids, _runits, _rget, _ctxt_comp,
                      format_ipv6_addr):
        _rids.return_value = 'rid1'
        _runits.return_value = 'runit'
        _ctxt_comp.return_value = True
        id_data = {
            'service_port': 9876,
            'service_host': '127.0.0.4',
            'auth_host': '127.0.0.5',
            'auth_port': 5432,
            'service_tenant': 'ten',
            'service_username': 'admin',
            'service_password': 'adminpass',
        }
        _rget.return_value = id_data
        ids_ctxt = context.IdentityServiceContext()
        self.assertEquals(ids_ctxt()['region'], 'region457')

    @patch.object(charmhelpers.contrib.openstack.context, 'relation_ids')
    @patch.object(charmhelpers.contrib.openstack.context, 'log')
    def test_ids_ctxt_no_rels(self, _log, _rids):
        _rids.return_value = []
        ids_ctxt = context.IdentityServiceContext()
        self.assertEquals(ids_ctxt(), None)


class HAProxyContextTest(CharmTestCase):

    def setUp(self):
        super(HAProxyContextTest, self).setUp(context, TO_PATCH)
        self.determine_api_port.return_value = 9686
        self.determine_apache_port.return_value = 9686
        self.api_port = 9696

    def tearDown(self):
        super(HAProxyContextTest, self).tearDown()

    @patch.object(charmhelpers.contrib.openstack.context, 'relation_ids')
    @patch.object(charmhelpers.contrib.openstack.context, 'log')
    def test_context_No_peers(self, _log, _rids):
        _rids.return_value = []
        hap_ctxt = context.HAProxyContext()
        with patch('__builtin__.__import__'):
            self.assertTrue('units' not in hap_ctxt())

    @patch.object(
        charmhelpers.contrib.openstack.context, 'get_netmask_for_address')
    @patch.object(
        charmhelpers.contrib.openstack.context, 'get_address_in_network')
    @patch.object(charmhelpers.contrib.openstack.context, 'config')
    @patch.object(charmhelpers.contrib.openstack.context, 'local_unit')
    @patch.object(charmhelpers.contrib.openstack.context, 'unit_get')
    @patch.object(charmhelpers.contrib.openstack.context, 'relation_get')
    @patch.object(charmhelpers.contrib.openstack.context, 'related_units')
    @patch.object(charmhelpers.contrib.openstack.context, 'relation_ids')
    @patch.object(charmhelpers.contrib.openstack.context, 'log')
    @patch('__builtin__.__import__')
    @patch('__builtin__.open')
    def test_context_peers(self, _open, _import, _log, _rids, _runits, _rget,
                           _uget, _lunit, _config,  _get_address_in_network,
                           _get_netmask_for_address):
        unit_addresses = {
            'neutron-api-0': '10.10.10.10',
            'neutron-api-1': '10.10.10.11',
        }
        _rids.return_value = ['rid1']
        _runits.return_value = ['neutron-api/0']
        _rget.return_value = unit_addresses['neutron-api-0']
        _lunit.return_value = "neutron-api/1"
        _uget.return_value = unit_addresses['neutron-api-1']
        _config.return_value = None
        _get_address_in_network.return_value = None
        _get_netmask_for_address.return_value = '255.255.255.0'
        service_ports = {'neutron-server': [9696, 9686]}
        self.maxDiff = None
        ctxt_data = {
            'local_host': '127.0.0.1',
            'haproxy_host': '0.0.0.0',
            'local_host': '127.0.0.1',
            'stat_port': ':8888',
            'frontends': {
                '10.10.10.11': {
                    'network': '10.10.10.11/255.255.255.0',
                    'backends': unit_addresses,
                }
            },
            'default_backend': '10.10.10.11',
            'service_ports': service_ports,
            'neutron_bind_port': 9686,
        }
        _import().api_port.return_value = 9696
        hap_ctxt = context.HAProxyContext()
        self.assertEquals(hap_ctxt(), ctxt_data)
        _open.assert_called_with('/etc/default/haproxy', 'w')


class NeutronCCContextTest(CharmTestCase):

    def setUp(self):
        super(NeutronCCContextTest, self).setUp(context, TO_PATCH)
        self.relation_get.side_effect = self.test_relation.get
        self.config.side_effect = self.test_config.get
        self.api_port = 9696
        self.determine_api_port.return_value = self.api_port
        self.test_config.set('neutron-plugin', 'ovs')
        self.test_config.set('neutron-security-groups', True)
        self.test_config.set('debug', True)
        self.test_config.set('verbose', True)
        self.test_config.set('neutron-external-network', 'bob')
        self.test_config.set('nsx-username', 'bob')
        self.test_config.set('nsx-password', 'hardpass')
        self.test_config.set('nsx-tz-uuid', 'tzuuid')
        self.test_config.set('nsx-l3-uuid', 'l3uuid')
        self.test_config.set('nsx-controllers', 'ctrl1 ctrl2')

    def tearDown(self):
        super(NeutronCCContextTest, self).tearDown()

    @patch.object(context.NeutronCCContext, 'network_manager')
    @patch.object(context.NeutronCCContext, 'plugin')
    @patch('__builtin__.__import__')
    def test_neutroncc_context_no_setting(self, _import, plugin, nm):
        plugin.return_value = None
        ctxt_data = {
            'debug': True,
            'external_network': 'bob',
            'neutron_bind_port': self.api_port,
            'verbose': True,
            'l2_population': True,
            'overlay_network_type': 'gre',
        }
        napi_ctxt = context.NeutronCCContext()
        with patch.object(napi_ctxt, '_ensure_packages'):
            self.assertEquals(ctxt_data, napi_ctxt())

    @patch.object(context.NeutronCCContext, 'network_manager')
    @patch.object(context.NeutronCCContext, 'plugin')
    @patch('__builtin__.__import__')
    def test_neutroncc_context_vxlan(self, _import, plugin, nm):
        plugin.return_value = None
        self.test_config.set('overlay-network-type', 'vxlan')
        ctxt_data = {
            'debug': True,
            'external_network': 'bob',
            'neutron_bind_port': self.api_port,
            'verbose': True,
            'l2_population': True,
            'overlay_network_type': 'vxlan',
        }
        napi_ctxt = context.NeutronCCContext()
        with patch.object(napi_ctxt, '_ensure_packages'):
            self.assertEquals(ctxt_data, napi_ctxt())

    @patch.object(context.NeutronCCContext, 'network_manager')
    @patch.object(context.NeutronCCContext, 'plugin')
    @patch('__builtin__.__import__')
    def test_neutroncc_context_unsupported_overlay(self, _import, plugin, nm):
        plugin.return_value = None
        self.test_config.set('overlay-network-type', 'bobswitch')
        with self.assertRaises(Exception) as context:
            context.NeutronCCContext()

    @patch.object(context.NeutronCCContext, 'network_manager')
    @patch.object(context.NeutronCCContext, 'plugin')
    @patch('__builtin__.__import__')
    def test_neutroncc_context_api_rel(self, _import, plugin, nm):
        nova_url = 'http://127.0.0.10'
        plugin.return_value = None
        self.related_units.return_value = ['unit1']
        self.relation_ids.return_value = ['rid2']
        self.test_relation.set({'nova_url': nova_url,
                                'restart_trigger': 'bob'})
        napi_ctxt = context.NeutronCCContext()
        self.assertEquals(nova_url, napi_ctxt()['nova_url'])
        self.assertEquals('bob', napi_ctxt()['restart_trigger'])
        self.assertEquals(self.api_port, napi_ctxt()['neutron_bind_port'])

    def test_neutroncc_context_manager(self):
        napi_ctxt = context.NeutronCCContext()
        self.assertEquals(napi_ctxt.network_manager, 'neutron')
        self.assertEquals(napi_ctxt.plugin, 'ovs')
        self.assertEquals(napi_ctxt.neutron_security_groups, True)

    def test_neutroncc_context_manager_pkgs(self):
        napi_ctxt = context.NeutronCCContext()
        with patch.object(napi_ctxt, '_ensure_packages') as ep:
            napi_ctxt._ensure_packages()
            ep.assert_has_calls([])

    @patch.object(context.NeutronCCContext, 'network_manager')
    @patch.object(context.NeutronCCContext, 'plugin')
    @patch('__builtin__.__import__')
    def test_neutroncc_context_nsx(self, _import, plugin, nm):
        plugin.return_value = 'nsx'
        self.related_units.return_value = []
        self.test_config.set('neutron-plugin', 'nsx')
        napi_ctxt = context.NeutronCCContext()()
        expect = {
            'nsx_controllers': 'ctrl1,ctrl2',
            'nsx_controllers_list': ['ctrl1', 'ctrl2'],
            'nsx_l3_uuid': 'l3uuid',
            'nsx_password': 'hardpass',
            'nsx_tz_uuid': 'tzuuid',
            'nsx_username': 'bob',
        }
        for key in expect.iterkeys():
            self.assertEquals(napi_ctxt[key], expect[key])
