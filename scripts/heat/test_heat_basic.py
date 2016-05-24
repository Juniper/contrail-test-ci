# Need to import path to test/fixtures and test/scripts/
# Ex : export PYTHONPATH='$PATH:/root/test/fixtures/:/root/test/scripts/'
#
# To run tests, you can do 'python -m testtools.run tests'. To run specific tests,
# You can do 'python -m testtools.run -l tests'
# Set the env variable PARAMS_FILE to point to your ini file. Else it will try to pick params.ini in PWD
#
import os
import sys
import test
from tcutils.wrappers import preposttest_wrapper

try:
    from heat_test import *
    from base import BaseHeatTest

    class TestHeat(BaseHeatTest):

        @classmethod
        def setUpClass(cls):
            super(TestHeat, cls).setUpClass()

        @classmethod
        def tearDownClass(cls):
            super(TestHeat, cls).tearDownClass()

        @test.attr(type=['sanity', 'ci_sanity'])
        @preposttest_wrapper
        def test_heat_stacks_list(self):
            '''
            Validate installation of heat
            This test issues a command to list all the heat-stacks
            '''
            self.stacks = self.useFixture(
                HeatFixture(connections=self.connections,
                            username=self.inputs.username,
                            password=self.inputs.password,
                            project_fq_name=self.inputs.project_fq_name,
                            inputs=self.inputs, cfgm_ip=self.inputs.cfgm_ip,
                            openstack_ip=self.inputs.openstack_ip))
            stacks_list = self.stacks.list_stacks()
            self.logger.info(
                'The following are the stacks currently : %s' % stacks_list)
        # end test_heat_stacks_list

        @test.attr(type=['sanity'])
        @preposttest_wrapper
        def test_svc_creation_with_heat(self):
            '''
            Validate creation of a in-network-nat service chain using heat
            '''
            vn_list = []
            right_net_fix, r_hs_obj = self.config_vn(stack_name='right_net')
            left_net_fix, l_h_obj = self.config_vn(stack_name='left_net')
            vn_list = [left_net_fix, right_net_fix]
            vms = []
            vms = self.config_vms(vn_list)
            svc_template = self.config_svc_template(stack_name='st', mode='in-network')
            svc_instance, si_hs_obj = self.config_svc_instance(
                'si', svc_template, vn_list)
            si_fq_name = (':').join(svc_instance.si_fq_name)
            svc_rules = []
            svc_rules.append(self.config_svc_rule(si_fq_names=[si_fq_name], src_vns=[left_net_fix], dst_vns=[right_net_fix]))
            if self.inputs.get_af() == 'v6':
                svc_rules.append(self.config_svc_rule(proto='icmp6', si_fq_names=[si_fq_name], src_vns=[left_net_fix], dst_vns=[right_net_fix]))
            svc_chain = self.config_svc_chain(svc_rules, vn_list, [l_h_obj, r_hs_obj])
            time.sleep(10)
            assert vms[0].ping_with_certainty(vms[1].vm_ip, expectation=True)
        # end test_svc_creation_with_heat

    class TestHeatv2(TestHeat):
        @classmethod
        def setUpClass(cls):
            super(TestHeatv2, cls).setUpClass()
            cls.heat_api_version = 2
            cls.pt_based_svc = True

        @test.attr(type=['sanity', 'suite1'])
        @preposttest_wrapper
        def test_svc_creation_with_heat(self):
            super(TestHeatv2, self).test_svc_creation_with_heat()

except ImportError:
    print 'Missing Heat Client. Will skip tests'
