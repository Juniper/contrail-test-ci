import test_v1
from vn_test import VNFixture
from vm_test import VMFixture
from policy_test import PolicyFixture
from floating_ip import FloatingIPFixture
from tcutils.commands import ssh, execute_cmd, execute_cmd_out
from tcutils.util import *
from contrailapi import ContrailVncApi
from common.base import GenericTestBase
from common.policy.config import ConfigPolicy, AttachPolicyFixture
from common.neutron.base import BaseNeutronTest
from vnc_api.vnc_api import *

class BaseDSNAT(BaseNeutronTest):

    @classmethod
    def setUpClass(cls):
        super(BaseDSNAT, cls).setUpClass()
        cls.project_name = cls.inputs.project_name
        cls.quantum_h= cls.connections.quantum_h
        cls.orch = cls.connections.orch
        cls.nova_h = cls.connections.nova_h
        cls.vnc_lib= cls.connections.vnc_lib
        cls.agent_inspect= cls.connections.agent_inspect
        cls.cn_inspect= cls.connections.cn_inspect
        cls.analytics_obj=cls.connections.analytics_obj
    #end setUpClass

    @classmethod
    def tearDownClass(cls):
        super(BaseDSNAT, cls).tearDownClass()
    # end tearDownClass

    def is_test_applicable(self):
        self.logger.info("Executing the function %s", self._testMethodName)
        basic_tc = ['test_dsnat_global_config', 'test_dsnat_basic']
        if self._testMethodName not in basic_tc:
            if len(self.inputs.compute_ips) < 2:
                return (False, 'Required minimum two compute nodes')
        return (True, None)

    def configure_port_translation_pool(self, **kwargs):
        protocol = kwargs.get('protocol', None)
        port_count = kwargs.get('port_count', '')
        start_port = kwargs.get('start_port', 0)
        end_port = kwargs.get('end_port', 0)
        pp = self.vnc_h.port_translation_pool(protocol, port_count, start_port, end_port)
        self.vnc_h.set_port_translation_pool(pp)
        return pp

    def create_vn_enable_fabric_snat(self):
        '''
           create a virtual network , enable SNAT and verify routing instance for SNAT flag
           return the VN object
        '''
        vn_name = get_random_name('dsnat_vn')
        vn_subnets = [get_random_cidr()]
        vn_fix = self.create_vn(vn_name, vn_subnets)
        assert vn_fix.verify_on_setup()
        self.vnc_h.set_fabric_snat(vn_fix.uuid)
        assert self.verify_routing_instance_snat(vn_fix)
        return vn_fix

    def set_vn_forwarding_mode(self, vn_fix, forwarding_mode="default"):
        vn_fix = self.vnc_h.virtual_network_read(id=vn_fix.uuid)
        vni_obj_properties = vn_fix.get_virtual_network_properties(
            ) or VirtualNetworkType()
        vni_obj_properties.set_forwarding_mode(forwarding_mode)
        vn_fix.set_virtual_network_properties(vni_obj_properties)
        self.vnc_h.virtual_network_update(vn_fix)

    def verify_port_translation_pool(self, expected_pp):
        actual_pps = self.vnc_h.get_port_translation_pools()
        for actual_pp in actual_pps.port_translation_pool:
            self.logger.info('Verifies that configured port translation pool %s,\
                is same as actual %s' %(expected_pp, actual_pp))
            return expected_pp == actual_pp

    def get_ip_fabric_vn_fixture(self):
        fabric_vn =  self.vnc_h.virtual_network_read(fq_name=['default-domain', 'default-project', 'ip-fabric'])
        fabric_vn.vn_fq_name = fabric_vn.get_fq_name_str()
        fabric_vn.vn_name = fabric_vn.name
        fabric_vn.policy_objs = []
        return fabric_vn

    def verify_routing_instance_snat(self, vn_fix):
        '''
            Verify the routing instance fabric SNAT flag is same as its virtual network flag
        '''       
        for ri in vn_fix.api_s_routing_instance['routing_instances']:
            ri_obj = self.vnc_h.routing_instance_read(id=ri['routing-instance']['uuid'])
            if ri_obj.routing_instance_fabric_snat != self.vnc_h.get_fabric_snat(vn_fix.uuid):
                self.logger.error("Fabric SNAT has not been set in the routing instance ")
                return False
        return True
            
    def verify_fabric_ip_as_floating_ip(self, vm_fix, vn_fq_name):
        '''
            Function to verify the fabric IP associated to the VMI of the VM , with SNAT enabled
        '''
        for fip in vm_fix.tap_intf[vn_fq_name]['fip_list']:
            if fip['ip_addr'] == vm_fix.vm_node_ip:
                return True
        self.logger.error("With SNAT enabled for the VN %s, fabric ip is not assigned as FIP ip to the VMI", vn_fq_name)
        return False

    def create_floatingip(self, floating_vn):
        fip_pool_name = get_random_name('dsnat_fip')
        fip_fixture = self.useFixture(
            FloatingIPFixture(
                project_name=self.inputs.project_name,
                inputs=self.inputs,
                connections=self.connections,
                pool_name=fip_pool_name,
                vn_id=floating_vn.vn_id))
        assert fip_fixture.verify_on_setup()
        return fip_fixture

    def config_policy(self, policy_name, rules):
        """Configures policy."""
        use_vnc_api = getattr(self, 'use_vnc_api', None)
        # create policy
        policy_fix = self.useFixture(PolicyFixture(
            policy_name=policy_name, rules_list=rules,
            inputs=self.inputs, connections=self.connections,
            api=use_vnc_api))
        return policy_fix

    def attach_policy_to_vn(self, policy_fix, vn_fix, policy_type=None):
        policy_attach_fix = self.useFixture(AttachPolicyFixture(
            self.inputs, self.connections, vn_fix, policy_fix, policy_type))
        return policy_attach_fix

    def detach_policy_from_vn(self, policy_fix, vn_fix):
        vn_obj = self.vnc_h.virtual_network_read(id=vn_fix.uuid)
        policy_obj = self.vnc_h.network_policy_read(id=policy_fix.get_id())
        vn_obj.del_network_policy(policy_obj)
        self.vnc_h.virtual_network_update(vn_obj)

    def create_policy_attach_to_vn(self, vn_fixture, rules):
        policy_name = get_random_name('test-dsnat')
        policy_fix = self.config_policy(policy_name, rules)
        return self.attach_policy_to_vn(policy_fix, vn_fixture)

    def create_interface_route_table(self, prefixes):
        intf_route_table_obj = self.vnc_h.create_route_table(
            prefixes = prefixes,
            parent_obj=self.project.project_obj)
        return intf_route_table_obj

