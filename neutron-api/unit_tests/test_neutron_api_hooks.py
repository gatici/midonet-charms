from mock import MagicMock, patch, call
from test_utils import CharmTestCase


with patch('charmhelpers.core.hookenv.config') as config:
    config.return_value = 'neutron'
    import neutron_api_utils as utils

_reg = utils.register_configs
_map = utils.restart_map

utils.register_configs = MagicMock()
utils.restart_map = MagicMock()

import neutron_api_hooks as hooks
hooks.hooks._config_save = False

hooks.hooks._config_save = False

utils.register_configs = _reg
utils.restart_map = _map

TO_PATCH = [
    'api_port',
    'apt_update',
    'apt_install',
    'canonical_url',
    'config',
    'CONFIGS',
    'check_call',
    'configure_installation_source',
    'determine_packages',
    'determine_ports',
    'do_openstack_upgrade',
    'execd_preinstall',
    'filter_installed_packages',
    'get_l2population',
    'get_overlay_network_type',
    'is_relation_made',
    'log',
    'open_port',
    'openstack_upgrade_available',
    'relation_get',
    'relation_ids',
    'relation_set',
    'unit_get',
    'get_iface_for_address',
    'get_netmask_for_address',
    'get_address_in_network',
    'update_nrpe_config',
]
NEUTRON_CONF_DIR = "/etc/neutron"

NEUTRON_CONF = '%s/neutron.conf' % NEUTRON_CONF_DIR

from random import randrange


class NeutronAPIHooksTests(CharmTestCase):

    def setUp(self):
        super(NeutronAPIHooksTests, self).setUp(hooks, TO_PATCH)

        self.config.side_effect = self.test_config.get
        self.relation_get.side_effect = self.test_relation.get
        self.test_config.set('openstack-origin', 'distro')
        self.test_config.set('neutron-plugin', 'ovs')

    def _fake_relids(self, rel_name):
        return [randrange(100) for _count in range(2)]

    def _call_hook(self, hookname):
        hooks.hooks.execute([
            'hooks/{}'.format(hookname)])

    def test_install_hook(self):
        _pkgs = ['foo', 'bar']
        _ports = [80, 81, 82]
        _port_calls = [call(port) for port in _ports]
        self.determine_packages.return_value = _pkgs
        self.determine_ports.return_value = _ports
        self._call_hook('install')
        self.configure_installation_source.assert_called_with(
            'distro'
        )
        self.apt_update.assert_called_with()
        self.apt_install.assert_has_calls([
            call(_pkgs, fatal=True),
        ])
        self.open_port.assert_has_calls(_port_calls)
        self.assertTrue(self.execd_preinstall.called)

    @patch.object(hooks, 'configure_https')
    def test_config_changed(self, conf_https):
        self.openstack_upgrade_available.return_value = True
        self.relation_ids.side_effect = self._fake_relids
        _n_api_rel_joined = self.patch('neutron_api_relation_joined')
        _n_plugin_api_rel_joined =\
            self.patch('neutron_plugin_api_relation_joined')
        _amqp_rel_joined = self.patch('amqp_joined')
        _id_rel_joined = self.patch('identity_joined')
        _id_cluster_joined = self.patch('cluster_joined')
        self._call_hook('config-changed')
        self.assertTrue(_n_api_rel_joined.called)
        self.assertTrue(_n_plugin_api_rel_joined.called)
        self.assertTrue(_amqp_rel_joined.called)
        self.assertTrue(_id_rel_joined.called)
        self.assertTrue(_id_cluster_joined.called)
        self.assertTrue(self.CONFIGS.write_all.called)
        self.assertTrue(self.do_openstack_upgrade.called)
        self.assertTrue(self.apt_install.called)

    def test_amqp_joined(self):
        self._call_hook('amqp-relation-joined')
        self.relation_set.assert_called_with(
            username='neutron',
            vhost='openstack',
            relation_id=None
        )

    def test_amqp_changed(self):
        self.CONFIGS.complete_contexts.return_value = ['amqp']
        self._call_hook('amqp-relation-changed')
        self.assertTrue(self.CONFIGS.write.called_with(NEUTRON_CONF))

    def test_amqp_departed(self):
        self._call_hook('amqp-relation-departed')
        self.assertTrue(self.CONFIGS.write.called_with(NEUTRON_CONF))

    def test_db_joined(self):
        self.is_relation_made.return_value = False
        self.unit_get.return_value = 'myhostname'
        self._call_hook('shared-db-relation-joined')
        self.relation_set.assert_called_with(
            username='neutron',
            database='neutron',
            hostname='myhostname',
        )

    def test_db_joined_with_postgresql(self):
        self.is_relation_made.return_value = True

        with self.assertRaises(Exception) as context:
            hooks.db_joined()
        self.assertEqual(context.exception.message,
                         'Attempting to associate a mysql database when there '
                         'is already associated a postgresql one')

    def test_postgresql_db_joined(self):
        self.unit_get.return_value = 'myhostname'
        self.is_relation_made.return_value = False
        self._call_hook('pgsql-db-relation-joined')
        self.relation_set.assert_called_with(
            database='neutron',
        )

    def test_postgresql_joined_with_db(self):
        self.is_relation_made.return_value = True

        with self.assertRaises(Exception) as context:
            hooks.pgsql_neutron_db_joined()
        self.assertEqual(context.exception.message,
                         'Attempting to associate a postgresql database when'
                         ' there is already associated a mysql one')

    def test_shared_db_changed(self):
        self.CONFIGS.complete_contexts.return_value = ['shared-db']
        self._call_hook('shared-db-relation-changed')
        self.assertTrue(self.CONFIGS.write_all.called)

    def test_shared_db_changed_partial_ctxt(self):
        self.CONFIGS.complete_contexts.return_value = []
        self._call_hook('shared-db-relation-changed')
        self.assertFalse(self.CONFIGS.write_all.called)

    def test_pgsql_db_changed(self):
        self._call_hook('pgsql-db-relation-changed')
        self.assertTrue(self.CONFIGS.write.called)

    def test_amqp_broken(self):
        self._call_hook('amqp-relation-broken')
        self.assertTrue(self.CONFIGS.write_all.called)

    def test_identity_joined(self):
        self.canonical_url.return_value = 'http://127.0.0.1'
        self.api_port.return_value = '9696'
        self.test_config.set('region', 'region1')
        _neutron_url = 'http://127.0.0.1:9696'
        _endpoints = {
            'quantum_service': 'quantum',
            'quantum_region': 'region1',
            'quantum_public_url': _neutron_url,
            'quantum_admin_url': _neutron_url,
            'quantum_internal_url': _neutron_url,
        }
        self._call_hook('identity-service-relation-joined')
        self.relation_set.assert_called_with(
            relation_id=None,
            relation_settings=_endpoints
        )

    def test_identity_changed_partial_ctxt(self):
        self.CONFIGS.complete_contexts.return_value = []
        _api_rel_joined = self.patch('neutron_api_relation_joined')
        self.relation_ids.side_effect = self._fake_relids
        self._call_hook('identity-service-relation-changed')
        self.assertFalse(_api_rel_joined.called)

    @patch.object(hooks, 'configure_https')
    def test_identity_changed(self, conf_https):
        self.CONFIGS.complete_contexts.return_value = ['identity-service']
        _api_rel_joined = self.patch('neutron_api_relation_joined')
        self.relation_ids.side_effect = self._fake_relids
        self._call_hook('identity-service-relation-changed')
        self.assertTrue(self.CONFIGS.write.called_with(NEUTRON_CONF))
        self.assertTrue(_api_rel_joined.called)

    def test_neutron_api_relation_no_id_joined(self):
        host = 'http://127.0.0.1'
        port = 1234
        _id_rel_joined = self.patch('identity_joined')
        self.relation_ids.side_effect = self._fake_relids
        self.canonical_url.return_value = host
        self.api_port.return_value = port
        self.is_relation_made = False
        neutron_url = '%s:%s' % (host, port)
        _relation_data = {
            'neutron-plugin': 'ovs',
            'neutron-url': neutron_url,
            'neutron-security-groups': 'no',
        }
        self._call_hook('neutron-api-relation-joined')
        self.relation_set.assert_called_with(
            relation_id=None,
            **_relation_data
        )
        self.assertTrue(_id_rel_joined.called)
        self.test_config.set('neutron-security-groups', True)
        self._call_hook('neutron-api-relation-joined')
        _relation_data['neutron-security-groups'] = 'yes'
        self.relation_set.assert_called_with(
            relation_id=None,
            **_relation_data
        )

    def test_neutron_api_relation_joined(self):
        host = 'http://127.0.0.1'
        port = 1234
        self.canonical_url.return_value = host
        self.api_port.return_value = port
        self.is_relation_made = True
        neutron_url = '%s:%s' % (host, port)
        _relation_data = {
            'neutron-plugin': 'ovs',
            'neutron-url': neutron_url,
            'neutron-security-groups': 'no',
        }
        self._call_hook('neutron-api-relation-joined')
        self.relation_set.assert_called_with(
            relation_id=None,
            **_relation_data
        )

    def test_neutron_api_relation_changed(self):
        self.CONFIGS.complete_contexts.return_value = ['shared-db']
        self._call_hook('neutron-api-relation-changed')
        self.assertTrue(self.CONFIGS.write.called_with(NEUTRON_CONF))

    def test_neutron_api_relation_changed_incomplere_ctxt(self):
        self.CONFIGS.complete_contexts.return_value = []
        self._call_hook('neutron-api-relation-changed')
        self.assertTrue(self.CONFIGS.write.called_with(NEUTRON_CONF))

    def test_neutron_plugin_api_relation_joined_nol2(self):
        _relation_data = {
            'neutron-security-groups': False,
            'l2-population': False,
            'overlay-network-type': 'vxlan',
        }
        self.get_l2population.return_value = False
        self.get_overlay_network_type.return_value = 'vxlan'
        self._call_hook('neutron-plugin-api-relation-joined')
        self.relation_set.assert_called_with(
            relation_id=None,
            **_relation_data
        )

    def test_cluster_changed(self):
        self._call_hook('cluster-relation-changed')
        self.assertTrue(self.CONFIGS.write_all.called)

    @patch.object(hooks, 'get_hacluster_config')
    def test_ha_joined(self, _get_ha_config):
        _ha_config = {
            'vip': '10.0.0.1',
            'vip_cidr': '24',
            'vip_iface': 'eth0',
            'ha-bindiface': 'eth1',
            'ha-mcastport': '5405',
        }
        vip_params = 'params ip="%s" cidr_netmask="255.255.255.0" nic="%s"' % \
                     (_ha_config['vip'], _ha_config['vip_iface'])
        _get_ha_config.return_value = _ha_config
        self.get_iface_for_address.return_value = 'eth0'
        self.get_netmask_for_address.return_value = '255.255.255.0'
        _relation_data = {
            'init_services': {'res_neutron_haproxy': 'haproxy'},
            'corosync_bindiface': _ha_config['ha-bindiface'],
            'corosync_mcastport': _ha_config['ha-mcastport'],
            'resources': {
                'res_neutron_eth0_vip': 'ocf:heartbeat:IPaddr2',
                'res_neutron_haproxy': 'lsb:haproxy'
            },
            'resource_params': {
                'res_neutron_eth0_vip': vip_params,
                'res_neutron_haproxy': 'op monitor interval="5s"'
            },
            'clones': {'cl_nova_haproxy': 'res_neutron_haproxy'}
        }
        self._call_hook('ha-relation-joined')
        self.relation_set.assert_called_with(
            **_relation_data
        )

    @patch.object(hooks, 'get_hacluster_config')
    def test_ha_joined_no_bound_ip(self, _get_ha_config):
        _ha_config = {
            'vip': '10.0.0.1',
            'ha-bindiface': 'eth1',
            'ha-mcastport': '5405',
        }
        vip_params = 'params ip="10.0.0.1" cidr_netmask="21" nic="eth120"'
        _get_ha_config.return_value = _ha_config
        self.test_config.set('vip_iface', 'eth120')
        self.test_config.set('vip_cidr', '21')
        self.get_iface_for_address.return_value = None
        self.get_netmask_for_address.return_value = None
        _relation_data = {
            'init_services': {'res_neutron_haproxy': 'haproxy'},
            'corosync_bindiface': _ha_config['ha-bindiface'],
            'corosync_mcastport': _ha_config['ha-mcastport'],
            'resources': {
                'res_neutron_eth120_vip': 'ocf:heartbeat:IPaddr2',
                'res_neutron_haproxy': 'lsb:haproxy'
            },
            'resource_params': {
                'res_neutron_eth120_vip': vip_params,
                'res_neutron_haproxy': 'op monitor interval="5s"'
            },
            'clones': {'cl_nova_haproxy': 'res_neutron_haproxy'}
        }
        self._call_hook('ha-relation-joined')
        self.relation_set.assert_called_with(
            **_relation_data
        )

    @patch.object(hooks, 'get_hacluster_config')
    def test_ha_joined_with_ipv6(self, _get_ha_config):
        self.test_config.set('prefer-ipv6', 'True')
        _ha_config = {
            'vip': '2001:db8:1::1',
            'vip_cidr': '64',
            'vip_iface': 'eth0',
            'ha-bindiface': 'eth1',
            'ha-mcastport': '5405',
        }
        vip_params = 'params ipv6addr="%s" ' \
                     'cidr_netmask="ffff.ffff.ffff.ffff" ' \
                     'nic="%s"' % \
                     (_ha_config['vip'], _ha_config['vip_iface'])
        _get_ha_config.return_value = _ha_config
        self.get_iface_for_address.return_value = 'eth0'
        self.get_netmask_for_address.return_value = 'ffff.ffff.ffff.ffff'
        _relation_data = {
            'init_services': {'res_neutron_haproxy': 'haproxy'},
            'corosync_bindiface': _ha_config['ha-bindiface'],
            'corosync_mcastport': _ha_config['ha-mcastport'],
            'resources': {
                'res_neutron_eth0_vip': 'ocf:heartbeat:IPv6addr',
                'res_neutron_haproxy': 'lsb:haproxy'
            },
            'resource_params': {
                'res_neutron_eth0_vip': vip_params,
                'res_neutron_haproxy': 'op monitor interval="5s"'
            },
            'clones': {'cl_nova_haproxy': 'res_neutron_haproxy'}
        }
        self._call_hook('ha-relation-joined')
        self.relation_set.assert_called_with(
            **_relation_data
        )

    def test_ha_changed(self):
        self.test_relation.set({
            'clustered': 'true',
        })
        self.relation_ids.side_effect = self._fake_relids
        _n_api_rel_joined = self.patch('neutron_api_relation_joined')
        _id_rel_joined = self.patch('identity_joined')
        self._call_hook('ha-relation-changed')
        self.assertTrue(_n_api_rel_joined.called)
        self.assertTrue(_id_rel_joined.called)

    def test_ha_changed_not_clustered(self):
        self.test_relation.set({
            'clustered': None,
        })
        self.relation_ids.side_effect = self._fake_relids
        _n_api_rel_joined = self.patch('neutron_api_relation_joined')
        _id_rel_joined = self.patch('identity_joined')
        self._call_hook('ha-relation-changed')
        self.assertFalse(_n_api_rel_joined.called)
        self.assertFalse(_id_rel_joined.called)

    def test_configure_https(self):
        self.CONFIGS.complete_contexts.return_value = ['https']
        self.relation_ids.side_effect = self._fake_relids
        _id_rel_joined = self.patch('identity_joined')
        hooks.configure_https()
        self.check_call.assert_called_with(['a2ensite',
                                           'openstack_https_frontend'])
        self.assertTrue(_id_rel_joined.called)

    def test_configure_https_nohttps(self):
        self.CONFIGS.complete_contexts.return_value = []
        self.relation_ids.side_effect = self._fake_relids
        _id_rel_joined = self.patch('identity_joined')
        hooks.configure_https()
        self.check_call.assert_called_with(['a2dissite',
                                           'openstack_https_frontend'])
        self.assertTrue(_id_rel_joined.called)
