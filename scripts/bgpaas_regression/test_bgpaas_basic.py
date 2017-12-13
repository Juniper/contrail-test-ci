import traffic_tests
from vn_test import *
from bgpaas_test import *
from vm_test import *
from floating_ip import *
from policy_test import *
from user_test import UserFixture
from multiple_vn_vm_test import *
from tcutils.wrappers import preposttest_wrapper
sys.path.append(os.path.realpath('tcutils/pkgs/Traffic'))
from traffic.core.stream import Stream
from traffic.core.profile import create, ContinuousProfile
from traffic.core.helpers import Host
from traffic.core.helpers import Sender, Receiver
from base import BaseBGPaasTest
from common import isolated_creds
import inspect
import time
from tcutils.commands import ssh, execute_cmd, execute_cmd_out
from tcutils.util import get_subnet_broadcast
from tcutils.util import skip_because
import test

class TestBasicBGPaaS(BaseBGPaasTest):

    @classmethod
    def setUpClass(cls):
        super(TestBasicBGPaaS, cls).setUpClass()

    @classmethod
    def tearDownClass(cls):
        super(TestBasicBGPaaS, cls).tearDownClass()

    def runTest(self):
        pass
    #end runTes


    @test.attr(type=['sanity','ci_sanity','vcenter', 'suite1'])
    @preposttest_wrapper
    def test_bgpaas_vm_add_delete(self):
        '''
        Description:  Test to BGPaas.
        Test steps:
		1. Create VN ctest_Private_BGP_Addnl_VN0 with subnet 1.3.0.0/16.
		2. Create VN ctest_Private_VSRX_MX_VN0 with subnet 2.3.0.0/16.
		3. Bring up vSRX VM with VMI1 in ctest_Private_BGP_Addnl_VN0 and VMI2 in ctest_Private_VSRX_MX_VN0.
		4. Bring up client VM bgpass-v6-vm in ctest_Private_BGP_Addnl_VN0.
		5. Configure BGPaas object with asn 652.
		6. Attach VMI ,which is in ctest_Private_BGP_Addnl_VN0 network ( where the client VM was spawned ), of vSRX VM to the bgpaas object.
		7. From the client VM , verify if the BGP exported IP 3.1.1.5 is pingable.

        Pass criteria: BGP advertised ip 3.1.1.5 should be pingable from the client VM
        Maintainer : vageesant@juniper.net
        '''

        project_obj = self.vnc_lib.project_read(id=self.project.get_uuid())

        vn1_fixture = self.create_vn(vn_name='ctest_Private_BGP_Addnl_VN0',subnets=['1.3.0.0/16'])
        vn2_fixture = self.create_vn(vn_name='ctest_Private_VSRX_MX_VN0',subnets=['2.3.0.0/16'])
        vn_obj = self.vnc_lib.virtual_network_read(id=vn1_fixture.vn_id)
        vn_obj.get_virtual_network_properties()
        vn_obj_properties = vn_obj.get_virtual_network_properties() or VirtualNetworkType()
        vn_obj_properties.set_forwarding_mode("l2_l3")
        vn_obj.set_virtual_network_properties(vn_obj_properties)
        self.vnc_lib.virtual_network_update(vn_obj)
        assert vn1_fixture.verify_on_setup()
        assert vn2_fixture.verify_on_setup()
        vm1_fixture = self.create_vm(vn_ids=[vn1_fixture.uuid,vn2_fixture.uuid],
                                     vm_name=get_random_name('bgp_vm'),image_name='vSRX')
        vm2_fixture = self.create_vm(vn_fixture=vn1_fixture,
                                     vm_name=get_random_name('vm1'),image_name='bgpass-v6-vm')

        assert vm1_fixture.verify_on_setup()
        for i in xrange(5) :
            vm_up = vm2_fixture.verify_on_setup() 
            if vm_up :
               break

        if not vm_up :
           assert "vSRX VM is not up"

	service_name = "bgpaas.router"
        asn   = "652"

        bgpaas_fixture = self.create_bgpaas_obj(vn_fixture=vn1_fixture,vm_fixture=vm1_fixture,service_name=service_name,bgp_vm_peer_ip="1.3.0.3",asn=asn,bgp_exported_routes_list=["3.1.1.5/32"])

        vmi_ids = vm1_fixture.get_vmi_ids()
        bgp_vn_fq_name = vn1_fixture.vn_fq_name.split(":")

        bgpaas_vmi_obj = None
        for k,vmi_id in vmi_ids.iteritems():
            vmi_obj  = self.connections.vnc_lib.virtual_machine_interface_read(id=vmi_id)
            network_fq_name = vmi_obj.get_virtual_network_refs()[0]['to']
            if network_fq_name == bgp_vn_fq_name: 
               bgpaas_vmi_obj = vmi_obj
               break
            else:
               continue
        if bgpaas_vmi_obj:
           bgpaas_fixture.attach_vmi(bgpaas_vmi_obj)

        assert bgpaas_fixture.verify_on_setup()

        self.logger.info("Verify ping to BGP exported IP: 3.1.1.5")
        for i in xrange(10):
            ping_status = vm2_fixture.ping_with_certainty(
                '3.1.1.5', expectation=True)
            if ping_status:
               break
        result_msg = "vm ping test result to vm %s is: %s" % (
            "3.1.1.5", ping_status)
        self.logger.info(result_msg)
        return True
