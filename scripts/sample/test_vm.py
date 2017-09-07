import test_v1
from tcutils.wrappers import preposttest_wrapper
from tcutils.util import get_random_name, get_random_cidr, get_random_cidrs
from common import resource_handler
from common.base import GenericTestBase

tmpl = {
    'heat_template_version': '2015-10-15',
    'outputs': {
        'vn1_id': {'value': {'get_attr': ['vn1', 'fq_name']}},
        'vm1_id': {'value': {'get_resource': 'vm1'}},
   },
    'parameters': {
        'domain': {'type': 'string'},
        'ipam': {'type': 'string'},
        'vn1_name': {'type': 'string'},
        'vn1_subnet1_prefix': {'type': 'string'},
        'vn1_subnet1_prefixlen': {'type': 'number'},
        'vn1_subnet1_dhcp': {'type': 'boolean'},
        'vn1_subnet2_prefix': {'type': 'string'},
        'vn1_subnet2_prefixlen': {'type': 'number'},
        'vm1_name': {'type': 'string'},
        'image': {'type': 'string'},
        'flavor': {'type': 'string'}
    },
    'resources': {
        'vn1': {
            'type': 'OS::ContrailV2::VirtualNetwork',
            'properties': {
                'name': {'get_param': 'vn1_name'},
                'network_ipam_refs': [{'get_param': 'ipam'}],
                'network_ipam_refs_data': [{
                    'network_ipam_refs_data_ipam_subnets': [{
                        'network_ipam_refs_data_ipam_subnets_subnet': {
                            'network_ipam_refs_data_ipam_subnets_subnet_ip_prefix': {
                                'get_param': 'vn1_subnet1_prefix',
                            },
                            'network_ipam_refs_data_ipam_subnets_subnet_ip_prefix_len': {
                                'get_param': 'vn1_subnet1_prefixlen',
                            },
                        },
                        'network_ipam_refs_data_ipam_subnets_addr_from_start' : True,
                        'network_ipam_refs_data_ipam_subnets_enable_dhcp': {
                            'get_param': 'vn1_subnet1_dhcp',
                        },
                     },{
                        'network_ipam_refs_data_ipam_subnets_subnet': {
                            'network_ipam_refs_data_ipam_subnets_subnet_ip_prefix': {
                               'get_param': 'vn1_subnet2_prefix',
                            },
                            'network_ipam_refs_data_ipam_subnets_subnet_ip_prefix_len': {
                               'get_param': 'vn1_subnet2_prefixlen',
                            },
                        },
                        'network_ipam_refs_data_ipam_subnets_addr_from_start' : True,
                        'network_ipam_refs_data_ipam_subnets_enable_dhcp': True,
                    }]
                }],
            }
        },
        'vm1': {
            'type': 'OS::Nova::Server',
            'depends_on': ['vn1'],
            'properties': {
                'name': {'get_param': 'vm1_name'},
                'image' : { "get_param" :  "image" },
                'flavor' : { "get_param" : "flavor" },
                'networks' : [
                    {'network': { "get_resource" : "vn1"}}
                    #{"port": { "get_resource" : "vmi1"}}
                ]
            }
        }
    }
}
''' 'vmi1' : {
    "type" : "OS::ContrailV2::VirtualMachineInterface",
    "properties" : {
        "name" : { "get_param" : "vmi1_name" },
        "virtual_network_refs" : [{ "list_join" : [':', { "get_attr" : [ "vn1" , "fq_name" ] } ] }]
    }
} '''

env = {
    'parameters': {
        'domain': 'default-domain',
        'ipam': 'default-domain:default-project:default-network-ipam',
        'vn1_name': get_random_name('vn1'),
        'vn1_subnet1_prefix': '1001::',
        'vn1_subnet1_prefixlen': 64,
        'vn1_subnet1_dhcp': True,
        'vn1_subnet2_prefix': '101.101.101.0',
        'vn1_subnet2_prefixlen': 24,
        'vm1_name': get_random_name('vm1'),
        'flavor': 'contrail_flavor_tiny',
        'image': 'cirros',
        #'vmi1_name': get_random_name('vmi1'),
   }
}

class Tests (test_v1.BaseTestCase_v1):

   @classmethod
   def setUpClass (cls):
       super(Tests, cls).setUpClass()

   @classmethod
   def tearDownClass (cls):
       super(Tests, cls).tearDownClass()

   @preposttest_wrapper
   def test1 (self):
       objs = resource_handler.create(self, tmpl, env)
       resource_handler.verify_on_setup(objs)
       #objs = resource_handler.update(self, objs, tmpl, env)
       #resource_handler.verify_on_setup(objs)
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

class TestwithOrch (Tests):

   @classmethod
   def setUpClass (cls):
       super(TestwithOrch, cls).setUpClass()
       cls.testmode = 'orch'

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
       vn1 = self.create_vn(vn_name=get_random_name('vn1'),
               vn_subnets=get_random_cidrs('dual'),
               option='quantum')
       vm1 = self.create_vm(vn_fixture=vn1, vm_name=get_random_name('vm1'))
       vn1.verify_on_setup()
       vm1.verify_on_setup()
       return True
