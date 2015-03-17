import itertools
import tempfile

import nova_compute_utils as utils

from mock import (
    patch,
    MagicMock,
    call
)
from test_utils import (
    CharmTestCase,
    patch_open
)


TO_PATCH = [
    'config',
    'os_release',
    'log',
    'neutron_plugin_attribute',
    'related_units',
    'relation_ids',
    'relation_get',
    'mkdir',
    'install_alternative'
]

OVS_PKGS = [
    ['quantum-plugin-openvswitch-agent'],
    ['openvswitch-datapath-dkms'],
]

OVS_PKGS_FLAT = list(itertools.chain.from_iterable(OVS_PKGS))


class NovaComputeUtilsTests(CharmTestCase):

    def setUp(self):
        super(NovaComputeUtilsTests, self).setUp(utils, TO_PATCH)
        self.config.side_effect = self.test_config.get

    @patch.object(utils, 'network_manager')
    def test_determine_packages_nova_network(self, net_man):
        net_man.return_value = 'flatdhcpmanager'
        self.relation_ids.return_value = []
        result = utils.determine_packages()
        ex = utils.BASE_PACKAGES + [
            'nova-api',
            'nova-network',
            'nova-compute-kvm'
        ]
        self.assertEquals(ex, result)

    @patch.object(utils, 'neutron_plugin')
    @patch.object(utils, 'network_manager')
    def test_determine_packages_quantum(self, net_man, n_plugin):
        self.neutron_plugin_attribute.return_value = OVS_PKGS
        net_man.return_value = 'quantum'
        n_plugin.return_value = 'ovs'
        self.relation_ids.return_value = []
        result = utils.determine_packages()
        ex = utils.BASE_PACKAGES + OVS_PKGS_FLAT + ['nova-compute-kvm']
        self.assertEquals(ex, result)

    @patch.object(utils, 'neutron_plugin')
    @patch.object(utils, 'network_manager')
    def test_determine_packages_quantum_ceph(self, net_man, n_plugin):
        self.neutron_plugin_attribute.return_value = OVS_PKGS
        net_man.return_value = 'quantum'
        n_plugin.return_value = 'ovs'
        self.relation_ids.return_value = ['ceph:0']
        result = utils.determine_packages()
        ex = (utils.BASE_PACKAGES + OVS_PKGS_FLAT +
              ['ceph-common', 'nova-compute-kvm'])
        self.assertEquals(ex, result)

    @patch.object(utils, 'network_manager')
    def test_resource_map_nova_network_no_multihost(self, net_man):
        self.skipTest('skipped until contexts are properly mocked')
        self.test_config.set('multi-host', 'no')
        net_man.return_value = 'FlatDHCPManager'
        result = utils.resource_map()
        ex = {
            '/etc/default/libvirt-bin': {
                'contexts': [],
                'services': ['libvirt-bin']
            },
            '/etc/libvirt/qemu.conf': {
                'contexts': [],
                'services': ['libvirt-bin']
            },
            '/etc/nova/nova-compute.conf': {
                'contexts': [],
                'services': ['nova-compute']
            },
            '/etc/nova/nova.conf': {
                'contexts': [],
                'services': ['nova-compute']
            },
        }
        self.assertEquals(ex, result)

    @patch.object(utils, 'network_manager')
    def test_resource_map_nova_network(self, net_man):

        self.skipTest('skipped until contexts are properly mocked')
        net_man.return_value = 'FlatDHCPManager'
        result = utils.resource_map()
        ex = {
            '/etc/default/libvirt-bin': {
                'contexts': [], 'services': ['libvirt-bin']
            },
            '/etc/libvirt/qemu.conf': {
                'contexts': [],
                'services': ['libvirt-bin']
            },
            '/etc/nova/nova-compute.conf': {
                'contexts': [],
                'services': ['nova-compute']
            },
            '/etc/nova/nova.conf': {
                'contexts': [],
                'services': ['nova-compute', 'nova-api', 'nova-network']
            }
        }
        self.assertEquals(ex, result)

    @patch.object(utils, 'neutron_plugin')
    @patch.object(utils, 'network_manager')
    def test_resource_map_quantum_ovs(self, net_man, _plugin):
        self.skipTest('skipped until contexts are properly mocked.')
        net_man.return_value = 'Quantum'
        _plugin.return_value = 'ovs'
        result = utils.resource_map()
        ex = {
            '/etc/default/libvirt-bin': {
                'contexts': [],
                'services': ['libvirt-bin']
            },
            '/etc/libvirt/qemu.conf': {
                'contexts': [],
                'services': ['libvirt-bin']
            },
            '/etc/nova/nova-compute.conf': {
                'contexts': [],
                'services': ['nova-compute']
            },
            '/etc/nova/nova.conf': {
                'contexts': [],
                'services': ['nova-compute']
            },
            '/etc/quantum/plugins/openvswitch/ovs_quantum_plugin.ini': {
                'contexts': [],
                'services': ['quantum-plugin-openvswitch-agent']
            },
            '/etc/quantum/quantum.conf': {
                'contexts': [],
                'services': ['quantum-plugin-openvswitch-agent']}
        }

        self.assertEquals(ex, result)

    @patch.object(utils, 'neutron_plugin')
    @patch.object(utils, 'network_manager')
    def test_resource_map_neutron_ovs_plugin(self, net_man, _plugin):
        self.skipTest('skipped until contexts are properly mocked.')
        self.is_relation_made = True
        net_man.return_value = 'Neutron'
        _plugin.return_value = 'ovs'
        result = utils.resource_map()
        self.assertTrue('/etc/neutron/neutron.conf' not in result)

    def fake_user(self, username='foo'):
        user = MagicMock()
        user.pw_dir = '/home/' + username
        return user

    @patch('__builtin__.open')
    @patch('pwd.getpwnam')
    def test_public_ssh_key_not_found(self, getpwnam, _open):
        _open.side_effect = Exception
        getpwnam.return_value = self.fake_user('foo')
        self.assertEquals(None, utils.public_ssh_key())

    @patch('pwd.getpwnam')
    def test_public_ssh_key(self, getpwnam):
        getpwnam.return_value = self.fake_user('foo')
        with patch_open() as (_open, _file):
            _file.read.return_value = 'mypubkey'
            result = utils.public_ssh_key('foo')
        self.assertEquals(result, 'mypubkey')

    def test_import_authorized_keys_missing_data(self):
        self.relation_get.return_value = None
        with patch_open() as (_open, _file):
            utils.import_authorized_keys(user='foo')
            self.assertFalse(_open.called)

    @patch('pwd.getpwnam')
    def _test_import_authorized_keys_base(self, getpwnam, prefix=None,
                                          auth_key_path='/home/foo/.ssh/'
                                                        'authorized_keys'):
        getpwnam.return_value = self.fake_user('foo')
        self.relation_get.side_effect = [
            3,          # relation_get('known_hosts_max_index')
            'k_h_0',    # relation_get_('known_hosts_0')
            'k_h_1',    # relation_get_('known_hosts_1')
            'k_h_2',    # relation_get_('known_hosts_2')
            3,          # relation_get('authorized_keys_max_index')
            'auth_0',   # relation_get('authorized_keys_0')
            'auth_1',   # relation_get('authorized_keys_1')
            'auth_2',   # relation_get('authorized_keys_2')
        ]

        ex_open = [
            call('/home/foo/.ssh/known_hosts', 'wb'),
            call(auth_key_path, 'wb')
        ]
        ex_write = [
            call('k_h_0\n'),
            call('k_h_1\n'),
            call('k_h_2\n'),
            call('auth_0\n'),
            call('auth_1\n'),
            call('auth_2\n')
        ]

        with patch_open() as (_open, _file):
            utils.import_authorized_keys(user='foo', prefix=prefix)
            self.assertEquals(ex_open, _open.call_args_list)
            self.assertEquals(ex_write, _file.write.call_args_list)
            authkey_root = 'authorized_keys_'
            known_hosts_root = 'known_hosts_'
            if prefix:
                authkey_root = prefix + '_authorized_keys_'
                known_hosts_root = prefix + '_known_hosts_'
            expected_relations = [
                call(known_hosts_root + 'max_index'),
                call(known_hosts_root + '0'),
                call(known_hosts_root + '1'),
                call(known_hosts_root + '2'),
                call(authkey_root + 'max_index'),
                call(authkey_root + '0'),
                call(authkey_root + '1'),
                call(authkey_root + '2')
                ]
            self.assertEquals(sorted(self.relation_get.call_args_list),
                              sorted(expected_relations))

    def test_import_authorized_keys_noprefix(self):
        self._test_import_authorized_keys_base()

    def test_import_authorized_keys_prefix(self):
        self._test_import_authorized_keys_base(prefix='bar')

    def test_import_authorized_keys_authkeypath(self):
        nonstandard_path = '/etc/ssh/user-authorized-keys/{username}'
        self.test_config.set('authorized-keys-path', nonstandard_path)
        self._test_import_authorized_keys_base(
            auth_key_path='/etc/ssh/user-authorized-keys/foo')

    @patch('subprocess.check_call')
    def test_import_keystone_cert_missing_data(self, check_call):
        self.relation_get.return_value = None
        with patch_open() as (_open, _file):
            utils.import_keystone_ca_cert()
            self.assertFalse(_open.called)
        self.assertFalse(check_call.called)

    @patch.object(utils, 'check_call')
    def test_import_keystone_cert(self, check_call):
        self.relation_get.return_value = 'Zm9vX2NlcnQK'
        with patch_open() as (_open, _file):
            utils.import_keystone_ca_cert()
            _open.assert_called_with(utils.CA_CERT_PATH, 'wb')
            _file.write.assert_called_with('foo_cert\n')
        check_call.assert_called_with(['update-ca-certificates'])

    @patch.object(utils, 'ceph_config_file')
    @patch('charmhelpers.contrib.openstack.templating.OSConfigRenderer')
    @patch.object(utils, 'quantum_enabled')
    @patch.object(utils, 'resource_map')
    def test_register_configs(self, resource_map, quantum, renderer,
                              mock_ceph_config_file):
        quantum.return_value = False
        self.os_release.return_value = 'havana'
        fake_renderer = MagicMock()
        fake_renderer.register = MagicMock()
        renderer.return_value = fake_renderer
        ctxt1 = MagicMock()
        ctxt2 = MagicMock()
        rsc_map = {
            '/etc/nova/nova.conf': {
                'services': ['nova-compute'],
                'contexts': [ctxt1],
            },
            '/etc/nova/nova-compute.conf': {
                'services': ['nova-compute'],
                'contexts': [ctxt2],
            },
        }
        resource_map.return_value = rsc_map
        with tempfile.NamedTemporaryFile() as tmpfile:
            mock_ceph_config_file.return_value = tmpfile.name
            utils.register_configs()
            renderer.assert_called_with(
                openstack_release='havana', templates_dir='templates/')
            ex_reg = [
                call('/etc/nova/nova-compute.conf', [ctxt2]),
                call('/etc/nova/nova.conf', [ctxt1])
            ]
            self.assertEquals(fake_renderer.register.call_args_list, ex_reg)

    @patch.object(utils, 'check_call')
    def test_enable_shell(self, _check_call):
        utils.enable_shell('dummy')
        _check_call.assert_called_with(['usermod', '-s', '/bin/bash', 'dummy'])

    @patch.object(utils, 'check_call')
    def test_disable_shell(self, _check_call):
        utils.disable_shell('dummy')
        _check_call.assert_called_with(['usermod', '-s', '/bin/false',
                                        'dummy'])
