import test_v1
import re
from common.connections import ContrailConnections
from common import isolated_creds
from vm_test import VMFixture
from vn_test import VNFixture
from bgpaas_test import BgpaasFixture

class BaseBGPaasTest(test_v1.BaseTestCase_v1):

    @classmethod
    def setUpClass(cls):
        super(BaseBGPaasTest, cls).setUpClass()
        cls.inputs.set_af('v4')
        cls.orch = cls.connections.orch
        cls.quantum_h= cls.connections.quantum_h
        cls.nova_h = cls.connections.nova_h
        cls.vnc_lib= cls.connections.vnc_lib
        cls.agent_inspect= cls.connections.agent_inspect
        cls.cn_inspect= cls.connections.cn_inspect
        cls.analytics_obj=cls.connections.analytics_obj
        cls.api_s_inspect = cls.connections.api_server_inspect
    #end setUpClass

    @classmethod
    def tearDownClass(cls):
        super(BaseBGPaasTest, cls).tearDownClass()
    #end tearDownClass 

    def create_bgpaas_obj(self,vn_fixture,vm_fixture,service_name,
                            bgp_vm_peer_ip,asn,bgp_exported_routes_list):
        return self.useFixture(
		BgpaasFixture(
		    project_name=self.inputs.project_name,
		    connections=self.connections,
                    vn_fixture=vn_fixture,
		    vm_fixture = vm_fixture,
		    service_name = service_name,
                    bgp_vm_peer_ip = bgp_vm_peer_ip,
                    asn = asn,
                    bgp_exported_routes_list = bgp_exported_routes_list ))
    def create_vn(self, *args, **kwargs):
        return self.useFixture(
                VNFixture(project_name=self.inputs.project_name,
                          connections=self.connections,
                          inputs=self.inputs,
                          *args, **kwargs
                          ))

    def create_vm(self, vn_fixture=None, image_name='ubuntu', *args, **kwargs):
        if vn_fixture:
            vn_obj = vn_fixture.obj
        else:
            vn_obj = None
        return self.useFixture(
                VMFixture(
                    project_name=self.inputs.project_name,
                    connections=self.connections,
                    vn_obj=vn_obj,
                    image_name=image_name,
                    *args, **kwargs
                    ))


