
from mock import MagicMock, patch
from collections import OrderedDict
import charmhelpers.contrib.openstack.templating as templating

templating.OSConfigRenderer = MagicMock()

with patch('charmhelpers.core.hookenv.config') as config:
    config.return_value = 'neutron'
    import neutron_api_utils as nutils

from test_utils import (
    CharmTestCase,
    patch_open,
)

import charmhelpers.core.hookenv as hookenv


TO_PATCH = [
    'apt_install',
    'apt_update',
    'apt_upgrade',
    'b64encode',
    'config',
    'configure_installation_source',
    'get_os_codename_install_source',
    'log',
    'neutron_plugin_attribute',
    'os_release',
]


def _mock_npa(plugin, attr, net_manager=None):
    plugins = {
        'ovs': {
            'config': '/etc/neutron/plugins/ml2/ml2_conf.ini',
            'driver': 'neutron.plugins.ml2.plugin.Ml2Plugin',
            'contexts': [],
            'services': ['neutron-plugin-openvswitch-agent'],
            'packages': [['neutron-plugin-openvswitch-agent']],
            'server_packages': ['neutron-server',
                                'neutron-plugin-ml2'],
            'server_services': ['neutron-server']
        },
    }
    return plugins[plugin][attr]


class TestNeutronAPIUtils(CharmTestCase):
    def setUp(self):
        super(TestNeutronAPIUtils, self).setUp(nutils, TO_PATCH)
        self.config.side_effect = self.test_config.get
        self.test_config.set('region', 'region101')
        self.neutron_plugin_attribute.side_effect = _mock_npa
        self.os_release.side_effect = 'trusty'

    def tearDown(self):
        # Reset cached cache
        hookenv.cache = {}

    def test_api_port(self):
        port = nutils.api_port('neutron-server')
        self.assertEqual(port, nutils.API_PORTS['neutron-server'])

    def test_determine_packages(self):
        pkg_list = nutils.determine_packages()
        expect = nutils.BASE_PACKAGES
        expect.extend(['neutron-server', 'neutron-plugin-ml2'])
        self.assertItemsEqual(pkg_list, expect)

    def test_determine_ports(self):
        port_list = nutils.determine_ports()
        self.assertItemsEqual(port_list, [9696])

    @patch('os.path.exists')
    def test_resource_map(self, _path_exists):
        _path_exists.return_value = False
        _map = nutils.resource_map()
        confs = [nutils.NEUTRON_CONF, nutils.NEUTRON_DEFAULT,
                 nutils.APACHE_CONF]
        [self.assertIn(q_conf, _map.keys()) for q_conf in confs]
        self.assertTrue(nutils.APACHE_24_CONF not in _map.keys())

    @patch('os.path.exists')
    def test_resource_map_apache24(self, _path_exists):
        _path_exists.return_value = True
        _map = nutils.resource_map()
        confs = [nutils.NEUTRON_CONF, nutils.NEUTRON_DEFAULT,
                 nutils.APACHE_24_CONF]
        [self.assertIn(q_conf, _map.keys()) for q_conf in confs]
        self.assertTrue(nutils.APACHE_CONF not in _map.keys())

    @patch('os.path.exists')
    def test_restart_map(self, mock_path_exists):
        mock_path_exists.return_value = False
        _restart_map = nutils.restart_map()
        ML2CONF = "/etc/neutron/plugins/ml2/ml2_conf.ini"
        expect = OrderedDict([
            (nutils.NEUTRON_CONF, {
                'services': ['neutron-server'],
            }),
            (nutils.NEUTRON_DEFAULT, {
                'services': ['neutron-server'],
            }),
            (ML2CONF, {
                'services': ['neutron-server'],
            }),
            (nutils.APACHE_CONF, {
                'services': ['apache2'],
            }),
            (nutils.HAPROXY_CONF, {
                'services': ['haproxy'],
            }),
        ])
        self.assertItemsEqual(_restart_map, expect)

    @patch('os.path.exists')
    def test_register_configs(self, mock_path_exists):
        mock_path_exists.return_value = False

        class _mock_OSConfigRenderer():
            def __init__(self, templates_dir=None, openstack_release=None):
                self.configs = []
                self.ctxts = []

            def register(self, config, ctxt):
                self.configs.append(config)
                self.ctxts.append(ctxt)

        templating.OSConfigRenderer.side_effect = _mock_OSConfigRenderer
        _regconfs = nutils.register_configs()
        confs = ['/etc/neutron/neutron.conf',
                 '/etc/default/neutron-server',
                 '/etc/neutron/plugins/ml2/ml2_conf.ini',
                 '/etc/apache2/sites-available/openstack_https_frontend',
                 '/etc/haproxy/haproxy.cfg']
        self.assertItemsEqual(_regconfs.configs, confs)

    @patch('os.path.isfile')
    def test_keystone_ca_cert_b64_no_cert_file(self, _isfile):
        _isfile.return_value = False
        cert = nutils.keystone_ca_cert_b64()
        self.assertEquals(cert, None)

    @patch('os.path.isfile')
    def test_keystone_ca_cert_b64(self, _isfile):
        _isfile.return_value = True
        with patch_open() as (_open, _file):
            nutils.keystone_ca_cert_b64()
            self.assertTrue(self.b64encode.called)

    def test_do_openstack_upgrade(self):
        self.config.side_effect = self.test_config.get
        self.test_config.set('openstack-origin', 'cloud:trusty-juno')
        self.os_release.side_effect = 'icehouse'
        self.get_os_codename_install_source.return_value = 'juno'
        configs = MagicMock()
        nutils.do_openstack_upgrade(configs)
        self.log.assert_called()
        self.configure_installation_source.assert_called_with(
            'cloud:trusty-juno'
        )
        self.apt_update.assert_called_with(fatal=True)
        dpkg_opts = [
            '--option', 'Dpkg::Options::=--force-confnew',
            '--option', 'Dpkg::Options::=--force-confdef',
        ]
        self.apt_upgrade.assert_called_with(options=dpkg_opts,
                                            fatal=True,
                                            dist=True)
        pkgs = nutils.BASE_PACKAGES
        pkgs.sort()
        self.apt_install.assert_called_with(packages=pkgs,
                                            options=dpkg_opts,
                                            fatal=True)
        configs.set_release.assert_called_with(openstack_release='juno')
