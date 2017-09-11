import test_v1
from tcutils.wrappers import preposttest_wrapper
from tcutils.util import get_random_name, get_random_cidr, get_random_cidrs
from common import resource_handler
from common.base import GenericTestBase

from vnc_api.vnc_api import IpamDnsAddressType, IpamType, VirtualDnsType
from vdns_fixture_new import VdnsFixture
from ipam_fixture import IPAMFixture


tmpl = {
   'heat_template_version': '2015-10-15',
   'outputs': {
       'ipam_id': {'value': {'get_resource': 'ipam_test'}},
       'vdns_id': {'value': {'get_resource': 'vdns_test'}},
       'vdns_record_id': {'value': {'get_resource': 'vdns_record_test'}}
   },
   'parameters': {
       'domain': {'type': 'string'},
       'ipam_name': {'type': 'string'},
       'ipam_subnet_method': {'type': 'string'},
       'ipam_method': {'type': 'string'},
       'dns_method': {'type': 'string'},
       'dns_name': {'type': 'string'},
       'vdns_name': {'type': 'string'},
       'vDNS_refs': {'type': 'string'},
       'vdns_domain_name': {'type': 'string'},
       'record_order': {'type': 'string'},
       'ttl': {'type': 'number'},
       'externally_visible': {'type': 'boolean'},
       'reverse_resolution': {'type': 'boolean'},
   },
    'resources' : {
        'ipam_test': {
            'type': 'OS::ContrailV2::NetworkIpam',
            'depends_on': ['vdns_test'],
            'properties': { 
                'name': { 'get_param': 'ipam_name' },
                'ipam_subnet_method': { 'get_param': 'ipam_subnet_method' },
                'network_ipam_mgmt':
                    { 'network_ipam_mgmt_ipam_method': { 'get_param': 'ipam_method' },
                     'network_ipam_mgmt_ipam_dns_method': { 'get_param': 'dns_method' },
                     'network_ipam_mgmt_ipam_dns_server':
                        {'network_ipam_mgmt_ipam_dns_server_virtual_dns_server_name': { 'get_param': 'dns_name' }},
                     },
                'virtual_DNS_refs': [{ 'get_param': 'vDNS_refs' }]
                #'project': { 'get_param': 'project' }
            }
        },
        'vdns_test': {
            'type': 'OS::ContrailV2::VirtualDns',
            'properties': { 
                'virtual_DNS_data':
                    {
                        'virtual_DNS_data_domain_name': { 'get_param': 'vdns_domain_name' },
                        'virtual_DNS_data_record_order': { 'get_param': 'record_order' },
                        'virtual_DNS_data_default_ttl_seconds': { 'get_param': 'ttl' },
                        'virtual_DNS_data_external_visible': { 'get_param': 'externally_visible' },
                        'virtual_DNS_data_reverse_resolution': { 'get_param': 'reverse_resolution' },
                    },
                'name' : { 'get_param': 'vdns_name' },
                'domain': 'default-domain'
            }
        }
    }
}

env = {
   'parameters': {
       'domain': 'default-domain',
       'ipam_name': 'IPAMTest',
       'ipam_subnet_method': "user-defined-subnet",
       'ipam_method': "dhcp",
       'dns_method': "virtual-dns-server",
       'dns_name': "default-domain:VDNSTest",
       'vdns_name': "VDNSTest",
       'vDNS_refs': "default-domain:VDNSTest",
       'vdns_domain_name': "juniper.net",
       'record_order': "random",
       'ttl': 100,
       'externally_visible': False,
       'reverse_resolution': False,
   }
}

class Tests (test_v1.BaseTestCase_v1):

   @classmethod
   def setUpClass (cls):
       super(Tests, cls).setUpClass()
       cls.testmode = 'vnc'

   @classmethod
   def tearDownClass (cls):
       super(Tests, cls).tearDownClass()

   @preposttest_wrapper
   def test1 (self):
       objs = resource_handler.create(self, tmpl, env)
       resource_handler.verify_on_setup(objs)
       #env['parameters']['vn1_subnet1_dhcp'] = False
       #env['parameters']['vn1_subnet2_prefix'] = '1.1.1.0'
       #env['parameters']['vn1_subnet2_prefixlen'] = 24
       #objs = resource_handler.update(self, objs, tmpl, env)
       return True

class TestwithHeat (Tests):

   @classmethod
   def setUpClass(cls):
       super(TestwithHeat, cls).setUpClass()
       cls.testmode = 'heat'

class TestwithVnc (Tests):

   @classmethod
   def setUpClass (cls):
       super(TestwithVnc, cls).setUpClass()
       cls.testmode = 'vnc'

class TestOldStyle (GenericTestBase):

   @classmethod
   def setUpClass (cls):
       super(TestOldStyle, cls).setUpClass()
       cls.testmode = 'vnc'

   @classmethod
   def tearDownClass(cls):
       super(TestOldStyle, cls).tearDownClass()

   @preposttest_wrapper
   def test1 (self):
        dns_server_name = get_random_name('VDNSTest')
        domain_name = 'juniper.net'
        cname_rec = 'vm1-test-alias'
        ttl = 1000
        ipam_name = get_random_name('IPAMTest')
        dns_data = VirtualDnsType(
            domain_name=domain_name, dynamic_records_from_client=True,
            default_ttl_seconds=ttl, record_order='fixed', reverse_resolution=True)
        vdns_fixt1 = self.useFixture(VdnsFixture(self.connections,
                                                 vdns_name=dns_server_name,
                                                 dns_data=dns_data))
        #result, msg = vdns_fixt1.verify_on_setup()
        #self.assertTrue(result, msg)
        
        dns_server = IpamDnsAddressType(
            virtual_dns_server_name=vdns_fixt1.fq_name_str)
        ipam_mgmt_obj = IpamType(
            ipam_dns_method='virtual-dns-server', ipam_dns_server=dns_server)
        ipam_fixt1 = self.useFixture(IPAMFixture(connections=self.connections,
                                                ipam_name = ipam_name,
                                                ipamtype=ipam_mgmt_obj))
        #result, msg = ipam_fixt1.verify_on_setup()
        #self.assertTrue(result, msg)
