import test_v1
from tcutils.wrappers import preposttest_wrapper
from tcutils.util import get_random_name, get_random_cidr, get_random_cidrs
from common import resource_handler
from common.base import GenericTestBase
from policy_fixture import PolicyFixture

tmpl = {
   'heat_template_version': '2015-10-15',
   'outputs': {
       'vn1_id': {'value': {'get_attr': ['vn1', 'fq_name']}},
       'vn2_id': {'value': {'get_resource': 'vn2'}},
       'policy_id': {'value': {'get_resource': 'policy'}},
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
       'vn2_name': {'type': 'string'},
       'vn2_subnet1_prefix': {'type': 'string'},
       'vn2_subnet1_af': {'type': 'number'},
       'vn2_subnet2_prefix': {'type': 'string'},
       'vn2_subnet2_af': {'type': 'number'},
       'policy_name': {'type': 'string'},
       'simple_action': {'type': 'string'},
       'protocol': {'type': 'string'},
       'src_port_end': {'type': 'number'},
       'src_port_start': {'type': 'number'},
       'direction': {'type': 'string'},
       'dst_port_end': {'type': 'number'},
       'dst_port_start': {'type': 'number'}
   },
   'resources': {
       'vn1': {
           'type': 'OS::ContrailV2::VirtualNetwork',
           'depends_on': ['policy'],
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
               'network_policy_refs': [{'list_join': [':', {'get_attr': ['policy', 'fq_name']}]},],
               'network_policy_refs_data': [{
                   'network_policy_refs_data_sequence': {
                       'network_policy_refs_data_sequence_major': 0,
                       'network_policy_refs_data_sequence_minor': 0
                   },
               }],
           }
       },
       'vn2': {
           'type': 'OS::Neutron::Net',
           'depends_on': ['policy'],
           'properties': {
               'name': {'get_param': 'vn2_name'},
               'value_specs': {
                   'contrail:policys': [{'get_attr' : ['policy', 'fq_name']}],
               },
           }
       },
       'vn2_subnet1': {
           'type': 'OS::Neutron::Subnet',
           'depends_on': ['vn2'],
           'properties': {
               'network_id': {'get_resource': 'vn2'},
               'cidr': {'get_param': 'vn2_subnet1_prefix'},
               'ip_version': {'get_param': 'vn2_subnet1_af'},
           }
       },
       'vn2_subnet2': {
           'type': 'OS::Neutron::Subnet',
           'depends_on': ['vn2'],
           'properties': {
               'network_id': {'get_resource': 'vn2'},
               'cidr': {'get_param': 'vn2_subnet2_prefix'},
               'ip_version': {'get_param': 'vn2_subnet2_af'},
           }
       },
       'policy': {
           'type': 'OS::ContrailV2::NetworkPolicy',
           'properties': {
               'name': {'get_param': 'policy_name'},
               'network_policy_entries': {
                   'network_policy_entries_policy_rule': [{
                       'network_policy_entries_policy_rule_direction': {
                           'get_param': 'direction'
                       },
                       'network_policy_entries_policy_rule_protocol': {
                           'get_param': 'protocol'
                       },
                       'network_policy_entries_policy_rule_src_ports': [{
                           'network_policy_entries_policy_rule_src_ports_start_port': {'get_param': 'src_port_start'},
                           'network_policy_entries_policy_rule_src_ports_end_port': {'get_param': 'src_port_end'},
                       }],
                       'network_policy_entries_policy_rule_dst_ports': [{
                           'network_policy_entries_policy_rule_dst_ports_start_port': {'get_param': 'dst_port_start'},
                           'network_policy_entries_policy_rule_dst_ports_end_port': {'get_param': 'dst_port_end'},
                       }],
                       'network_policy_entries_policy_rule_src_addresses': [{
                           'network_policy_entries_policy_rule_src_addresses_virtual_network': {'get_resource': 'vn1'}
                       }],
                       'network_policy_entries_policy_rule_dst_addresses': [{
                           'network_policy_entries_policy_rule_dst_addresses_virtual_network': {'get_resource': 'vn2'}
                       }],
                       'network_policy_entries_policy_rule_action_list': {
                           'network_policy_entries_policy_rule_action_list_simple_action': {'get_param': 'simple_action'},
                       },
                   }]
               }
           }
       },
   }
}

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
       'vn2_name': get_random_name('vn2'),
       'vn2_subnet1_prefix': '2001::/64',
       'vn2_subnet1_af': 6,
       'vn2_subnet2_prefix': '201.201.201.0/24',
       'vn2_subnet2_af': 4,
       'policy_name': 'pol1',
       'simple_action': 'pass',
       'protocol': 'icmp',
       'src_port_end': -1,
       'src_port_start': -1,
       'direction': '<>',
       'dst_port_end': -1,
       'dst_port_start': -1,
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
       vn1 = self.create_vn(vn_name='vn1',
               vn_subnets=get_random_cidrs('dual'),
               option='quantum')
       vn2 = self.create_vn(vn_name='vn2',
               vn_subnets=get_random_cidrs('v4'),
               option='contrail')
       rule1 = {
               'direction' : '<>',
               'protocol' : 'icmp',
               'simple_action' : 'pass',
               'source_network': 'vn1',
               'dest_network': 'vn2',
               }
       rule2 = {
               'direction' : '<>',
               'protocol' : 'udp',
               'simple_action' : 'pass',
               'source_network': 'vn1',
               'dest_network': 'vn2',
               'src_ports' : (80,100),
               'dst_ports' : (10,20),
               }
       icmp = self.useFixture(PolicyFixture(policy_name='pol1',
           connections=self.connections,
           rules_list=[rule1],
           api=True,
           ))
       udp = self.useFixture(PolicyFixture(policy_name='pol2',
           connections=self.connections,
           rules_list=[rule2]
           ))
       vn1.bind_policies([icmp.fq_name, udp.fq_name])
       vn2.bind_policies([icmp.fq_name, udp.fq_name])
       icmp.verify_on_setup()
       udp.verify_on_setup()
       vn1.verify_on_setup()
       vn2.verify_on_setup()
       vn1.unbind_policies()
       vn2.unbind_policies()
       return True
