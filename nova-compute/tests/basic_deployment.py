#!/usr/bin/python

import amulet
import time

from charmhelpers.contrib.openstack.amulet.deployment import (
    OpenStackAmuletDeployment
)

from charmhelpers.contrib.openstack.amulet.utils import (
    OpenStackAmuletUtils,
    DEBUG, # flake8: noqa
    ERROR
)

# Use DEBUG to turn on debug logging
u = OpenStackAmuletUtils(ERROR)


class NovaBasicDeployment(OpenStackAmuletDeployment):
    """Amulet tests on a basic nova compute deployment."""

    def __init__(self, series=None, openstack=None, source=None, stable=False):
        """Deploy the entire test environment."""
        super(NovaBasicDeployment, self).__init__(series, openstack, source, stable)
        self._add_services()
        self._add_relations()
        self._configure_services()
        self._deploy()
        self._initialize_tests()

    def _add_services(self):
        """Add services

           Add the services that we're testing, where nova-compute is local,
           and the rest of the service are from lp branches that are
           compatible with the local charm (e.g. stable or next).
           """
        this_service = {'name': 'nova-compute'}
        other_services = [{'name': 'mysql'}, {'name': 'rabbitmq-server'},
                          {'name': 'nova-cloud-controller'}, {'name': 'keystone'},
                          {'name': 'glance'}]
        super(NovaBasicDeployment, self)._add_services(this_service,
                                                       other_services)

    def _add_relations(self):
        """Add all of the relations for the services."""
        relations = {
          'nova-compute:image-service': 'glance:image-service',
          'nova-compute:shared-db': 'mysql:shared-db',
          'nova-compute:amqp': 'rabbitmq-server:amqp',
          'nova-cloud-controller:shared-db': 'mysql:shared-db',
          'nova-cloud-controller:identity-service': 'keystone:identity-service',
          'nova-cloud-controller:amqp': 'rabbitmq-server:amqp',
          'nova-cloud-controller:cloud-compute': 'nova-compute:cloud-compute',
          'nova-cloud-controller:image-service': 'glance:image-service',
          'keystone:shared-db': 'mysql:shared-db',
          'glance:identity-service': 'keystone:identity-service',
          'glance:shared-db': 'mysql:shared-db',
          'glance:amqp': 'rabbitmq-server:amqp'
        }
        super(NovaBasicDeployment, self)._add_relations(relations)

    def _configure_services(self):
        """Configure all of the services."""
        nova_config = {'config-flags': 'auto_assign_floating_ip=False',
                       'enable-live-migration': 'False'}
        keystone_config = {'admin-password': 'openstack',
                           'admin-token': 'ubuntutesting'}
        configs = {'nova-compute': nova_config, 'keystone': keystone_config}
        super(NovaBasicDeployment, self)._configure_services(configs)

    def _initialize_tests(self):
        """Perform final initialization before tests get run."""
        # Access the sentries for inspecting service units
        self.mysql_sentry = self.d.sentry.unit['mysql/0']
        self.keystone_sentry = self.d.sentry.unit['keystone/0']
        self.rabbitmq_sentry = self.d.sentry.unit['rabbitmq-server/0']
        self.nova_compute_sentry = self.d.sentry.unit['nova-compute/0']
        self.nova_cc_sentry = self.d.sentry.unit['nova-cloud-controller/0']
        self.glance_sentry = self.d.sentry.unit['glance/0']

        # Let things settle a bit before moving forward
        time.sleep(30)

        # Authenticate admin with keystone
        self.keystone = u.authenticate_keystone_admin(self.keystone_sentry,
                                                      user='admin',
                                                      password='openstack',
                                                      tenant='admin')

        # Authenticate admin with glance endpoint
        self.glance = u.authenticate_glance_admin(self.keystone)

        # Create a demo tenant/role/user
        self.demo_tenant = 'demoTenant'
        self.demo_role = 'demoRole'
        self.demo_user = 'demoUser'
        if not u.tenant_exists(self.keystone, self.demo_tenant):
            tenant = self.keystone.tenants.create(tenant_name=self.demo_tenant,
                                                  description='demo tenant',
                                                  enabled=True)
            self.keystone.roles.create(name=self.demo_role)
            self.keystone.users.create(name=self.demo_user,
                                       password='password',
                                       tenant_id=tenant.id,
                                       email='demo@demo.com')

        # Authenticate demo user with keystone
        self.keystone_demo = \
            u.authenticate_keystone_user(self.keystone, user=self.demo_user,
                                         password='password',
                                         tenant=self.demo_tenant)

        # Authenticate demo user with nova-api
        self.nova_demo = u.authenticate_nova_user(self.keystone,
                                                  user=self.demo_user,
                                                  password='password',
                                                  tenant=self.demo_tenant)

    def test_services(self):
        """Verify the expected services are running on the corresponding
           service units."""
        commands = {
            self.mysql_sentry: ['status mysql'],
            self.rabbitmq_sentry: ['sudo service rabbitmq-server status'],
            self.nova_compute_sentry: ['status nova-compute',
                                       'status nova-network',
                                       'status nova-api'],
            self.nova_cc_sentry: ['status nova-api-ec2',
                                  'status nova-api-os-compute',
                                  'status nova-objectstore',
                                  'status nova-cert',
                                  'status nova-scheduler'],
            self.keystone_sentry: ['status keystone'],
            self.glance_sentry: ['status glance-registry', 'status glance-api']
        }
        if self._get_openstack_release() >= self.precise_grizzly:
            commands[self.nova_cc_sentry] = ['status nova-conductor']

        ret = u.validate_services(commands)
        if ret:
            amulet.raise_status(amulet.FAIL, msg=ret)

    def test_service_catalog(self):
        """Verify that the service catalog endpoint data is valid."""
        endpoint_vol = {'adminURL': u.valid_url,
                        'region': 'RegionOne',
                        'publicURL': u.valid_url,
                        'internalURL': u.valid_url}
        endpoint_id = {'adminURL': u.valid_url,
                       'region': 'RegionOne',
                       'publicURL': u.valid_url,
                       'internalURL': u.valid_url}
        if self._get_openstack_release() >= self.precise_folsom:
            endpoint_vol['id'] = u.not_null
            endpoint_id['id'] = u.not_null
        expected = {'s3': [endpoint_vol], 'compute': [endpoint_vol],
                    'ec2': [endpoint_vol], 'identity': [endpoint_id]}
        actual = self.keystone_demo.service_catalog.get_endpoints()

        ret = u.validate_svc_catalog_endpoint_data(expected, actual)
        if ret:
            amulet.raise_status(amulet.FAIL, msg=ret)

    def test_openstack_compute_api_endpoint(self):
        """Verify the openstack compute api (osapi) endpoint data."""
        endpoints = self.keystone.endpoints.list()
        admin_port = internal_port = public_port = '8774'
        expected = {'id': u.not_null,
                    'region': 'RegionOne',
                    'adminurl': u.valid_url,
                    'internalurl': u.valid_url,
                    'publicurl': u.valid_url,
                    'service_id': u.not_null}

        ret = u.validate_endpoint_data(endpoints, admin_port, internal_port,
                                       public_port, expected)
        if ret:
            message = 'osapi endpoint: {}'.format(ret)
            amulet.raise_status(amulet.FAIL, msg=message)

    def test_ec2_api_endpoint(self):
        """Verify the EC2 api endpoint data."""
        endpoints = self.keystone.endpoints.list()
        admin_port = internal_port = public_port = '8773'
        expected = {'id': u.not_null,
                    'region': 'RegionOne',
                    'adminurl': u.valid_url,
                    'internalurl': u.valid_url,
                    'publicurl': u.valid_url,
                    'service_id': u.not_null}

        ret = u.validate_endpoint_data(endpoints, admin_port, internal_port,
                                       public_port, expected)
        if ret:
            message = 'EC2 endpoint: {}'.format(ret)
            amulet.raise_status(amulet.FAIL, msg=message)

    def test_s3_api_endpoint(self):
        """Verify the S3 api endpoint data."""
        endpoints = self.keystone.endpoints.list()
        admin_port = internal_port = public_port = '3333'
        expected = {'id': u.not_null,
                    'region': 'RegionOne',
                    'adminurl': u.valid_url,
                    'internalurl': u.valid_url,
                    'publicurl': u.valid_url,
                    'service_id': u.not_null}

        ret = u.validate_endpoint_data(endpoints, admin_port, internal_port,
                                       public_port, expected)
        if ret:
            message = 'S3 endpoint: {}'.format(ret)
            amulet.raise_status(amulet.FAIL, msg=message)

    def test_nova_shared_db_relation(self):
        """Verify the nova-compute to mysql shared-db relation data"""
        unit = self.nova_compute_sentry
        relation = ['shared-db', 'mysql:shared-db']
        expected = {
            'private-address': u.valid_ip,
            'nova_database': 'nova',
            'nova_username': 'nova',
            'nova_hostname': u.valid_ip
        }

        ret = u.validate_relation_data(unit, relation, expected)
        if ret:
            message = u.relation_error('nova-compute shared-db', ret)
            amulet.raise_status(amulet.FAIL, msg=message)

    def test_mysql_shared_db_relation(self):
        """Verify the mysql to nova-compute shared-db relation data"""
        unit = self.mysql_sentry
        relation = ['shared-db', 'nova-compute:shared-db']
        expected = {
            'private-address': u.valid_ip,
            'nova_password': u.not_null,
            'db_host': u.valid_ip
        }

        ret = u.validate_relation_data(unit, relation, expected)
        if ret:
            message = u.relation_error('mysql shared-db', ret)
            amulet.raise_status(amulet.FAIL, msg=message)

    def test_nova_amqp_relation(self):
        """Verify the nova-compute to rabbitmq-server amqp relation data"""
        unit = self.nova_compute_sentry
        relation = ['amqp', 'rabbitmq-server:amqp']
        expected = {
            'username': 'nova',
            'private-address': u.valid_ip,
            'vhost': 'openstack'
        }

        ret = u.validate_relation_data(unit, relation, expected)
        if ret:
            message = u.relation_error('nova-compute amqp', ret)
            amulet.raise_status(amulet.FAIL, msg=message)

    def test_rabbitmq_amqp_relation(self):
        """Verify the rabbitmq-server to nova-compute amqp relation data"""
        unit = self.rabbitmq_sentry
        relation = ['amqp', 'nova-compute:amqp']
        expected = {
            'private-address': u.valid_ip,
            'password': u.not_null,
            'hostname': u.valid_ip
        }

        ret = u.validate_relation_data(unit, relation, expected)
        if ret:
            message = u.relation_error('rabbitmq amqp', ret)
            amulet.raise_status(amulet.FAIL, msg=message)

    def test_nova_cloud_compute_relation(self):
        """Verify the nova-compute to nova-cc cloud-compute relation data"""
        unit = self.nova_compute_sentry
        relation = ['cloud-compute', 'nova-cloud-controller:cloud-compute']
        expected = {
            'private-address': u.valid_ip,
        }

        ret = u.validate_relation_data(unit, relation, expected)
        if ret:
            message = u.relation_error('nova-compute cloud-compute', ret)
            amulet.raise_status(amulet.FAIL, msg=message)

    def test_nova_cc_cloud_compute_relation(self):
        """Verify the nova-cc to nova-compute cloud-compute relation data"""
        unit = self.nova_cc_sentry
        relation = ['cloud-compute', 'nova-compute:cloud-compute']
        expected = {
            'volume_service': 'cinder',
            'network_manager': 'flatdhcpmanager',
            'ec2_host': u.valid_ip,
            'private-address': u.valid_ip,
            'restart_trigger': u.not_null
        }
        if self._get_openstack_release() == self.precise_essex:
            expected['volume_service'] = 'nova-volume'

        ret = u.validate_relation_data(unit, relation, expected)
        if ret:
            message = u.relation_error('nova-cc cloud-compute', ret)
            amulet.raise_status(amulet.FAIL, msg=message)

    def test_z_restart_on_config_change(self):
        """Verify that the specified services are restarted when the config
           is changed.

           Note(coreycb): The method name with the _z_ is a little odd
           but it forces the test to run last.  It just makes things
           easier because restarting services requires re-authorization.
           """
        # NOTE(coreycb): Skipping failing test on essex until resolved.
        #                config-flags don't take effect on essex.
        if self._get_openstack_release() == self.precise_essex:
            u.log.error("Skipping failing test until resolved")
            return

        services = ['nova-compute', 'nova-api', 'nova-network']
        self.d.configure('nova-compute', {'config-flags': 'verbose=False'})

        time = 20
        for s in services:
            if not u.service_restarted(self.nova_compute_sentry, s,
                                       '/etc/nova/nova.conf', sleep_time=time):
                self.d.configure('nova-compute', {'config-flags': 'verbose=True'})
                msg = "service {} didn't restart after config change".format(s)
                amulet.raise_status(amulet.FAIL, msg=msg)
            time = 0

        self.d.configure('nova-compute', {'config-flags': 'verbose=True'})

    def test_nova_config(self):
        """Verify the data in the nova config file."""
        # NOTE(coreycb): Currently no way to test on essex because config file
        #                has no section headers.
        if self._get_openstack_release() == self.precise_essex:
            return

        unit = self.nova_compute_sentry
        conf = '/etc/nova/nova.conf'
        rabbitmq_relation = self.rabbitmq_sentry.relation('amqp',
                                                          'nova-compute:amqp')
        glance_relation = self.glance_sentry.relation('image-service',
                                                   'nova-compute:image-service')
        mysql_relation = self.mysql_sentry.relation('shared-db',
                                                    'nova-compute:shared-db')
        db_uri = "mysql://{}:{}@{}/{}".format('nova',
                                              mysql_relation['nova_password'],
                                              mysql_relation['db_host'],
                                              'nova')

        expected = {'dhcpbridge_flagfile': '/etc/nova/nova.conf',
                    'dhcpbridge': '/usr/bin/nova-dhcpbridge',
                    'logdir': '/var/log/nova',
                    'state_path': '/var/lib/nova',
                    'lock_path': '/var/lock/nova',
                    'force_dhcp_release': 'True',
                    'libvirt_use_virtio_for_bridges': 'True',
                    'verbose': 'True',
                    'use_syslog': 'False',
                    'ec2_private_dns_show_ip': 'True',
                    'api_paste_config': '/etc/nova/api-paste.ini',
                    'enabled_apis': 'ec2,osapi_compute,metadata',
                    'auth_strategy': 'keystone',
                    'compute_driver': 'libvirt.LibvirtDriver',
                    'sql_connection': db_uri,
                    'rabbit_userid': 'nova',
                    'rabbit_virtual_host': 'openstack',
                    'rabbit_password': rabbitmq_relation['password'],
                    'rabbit_host': rabbitmq_relation['hostname'],
                    'glance_api_servers': glance_relation['glance-api-server'],
                    'flat_interface': 'eth1',
                    'network_manager': 'nova.network.manager.FlatDHCPManager',
                    'volume_api_class': 'nova.volume.cinder.API',
                    'verbose': 'True'}

        ret = u.validate_config_data(unit, conf, 'DEFAULT', expected)
        if ret:
            message = "nova config error: {}".format(ret)
            amulet.raise_status(amulet.FAIL, msg=message)

    def test_image_instance_create(self):
        """Create an image/instance, verify they exist, and delete them."""
        # NOTE(coreycb): Skipping failing test on essex until resolved. essex
        #                nova API calls are getting "Malformed request url (HTTP
        #                400)".
        if self._get_openstack_release() == self.precise_essex:
            u.log.error("Skipping failing test until resolved")
            return

        image = u.create_cirros_image(self.glance, "cirros-image")
        if not image:
            amulet.raise_status(amulet.FAIL, msg="Image create failed")

        instance = u.create_instance(self.nova_demo, "cirros-image", "cirros",
                                     "m1.tiny")
        if not instance:
            amulet.raise_status(amulet.FAIL, msg="Instance create failed")

        found = False
        for instance in self.nova_demo.servers.list():
            if instance.name == 'cirros':
                found = True
                if instance.status != 'ACTIVE':
                    msg = "cirros instance is not active"
                    amulet.raise_status(amulet.FAIL, msg=message)

        if not found:
            message = "nova cirros instance does not exist"
            amulet.raise_status(amulet.FAIL, msg=message)

        u.delete_image(self.glance, image)
        u.delete_instance(self.nova_demo, instance)
