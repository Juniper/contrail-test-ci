import fixtures
import time
import sys
import re
from project_test import *
from tcutils.util import *
import json
from vnc_api.vnc_api import *
from contrail_fixtures import *
import copy
from tcutils.agent.vna_introspect_utils import *
import inspect
try:
    from webui_test import *
except ImportError:
    pass

class BgpaasFixture(fixtures.Fixture):

    def __init__(self,project_name,connections,service_name,vn_fixture,vm_fixture,
		   bgp_vm_peer_ip,asn,bgp_exported_routes_list):

        self.bgp_exported_routes_list = bgp_exported_routes_list
        self.bgp_vm_peer_ip = bgp_vm_peer_ip
        self.service_name = service_name
        self.vn_fixture = vn_fixture
        self.vm_fixture = vm_fixture
        self.asn          = asn
        self.connections = connections
        self.agent_inspect = self.connections.agent_inspect
        self.cn_inspect = self.connections.cn_inspect
        self.analytics_obj = self.connections.analytics_obj
        self.quantum_h = self.connections.quantum_h
        self.api_s_inspect = self.connections.api_server_inspect
        self.vnc_lib = self.connections.vnc_lib
        self.domain_name = self.connections.domain_name
        self.project_name = project_name
        self.project_fq_name = [self.domain_name,self.project_name]
        self.logger = self.connections.inputs.logger
        self.already_present = False
        self.verify_is_run = False
  
    def setUp(self):
        super(BgpaasFixture, self).setUp()
        self.create()
  
    def create(self):
        self.project_obj = self.connections.vnc_lib_fixture.get_project_obj()
        #if self.uuid:
        #    return self.read()
        self._create_bgpaas()

    def attach_vmi(self,vmi_obj):

        inst_ips = vmi_obj.get_instance_ip_back_refs()
        ip_obj = self.connections.vnc_lib.instance_ip_read(id=inst_ips[0]['uuid'])
        self.bgpaas_obj.set_bgpaas_ip_address(ip_obj.get_instance_ip_address()) # get instance IP attached to vmi.
        self.bgpaas_obj.add_virtual_machine_interface(vmi_obj) # vSRX VMI
        self.connections.vnc_lib.bgp_as_a_service_update(self.bgpaas_obj)

    def _create_bgpaas(self):

        self.bgpaas_obj = BgpAsAService(name=self.service_name,parent_obj=self.project_obj)
        self.bgpaas_obj.set_autonomous_system(self.asn)
        self.bgpaas_obj.set_display_name(self.service_name)
        bgp_addr_fams = AddressFamilies(['inet','inet6'])
        bgp_sess_attrs = BgpSessionAttributes(address_families=bgp_addr_fams,hold_time=300)
        self.bgpaas_obj.set_bgpaas_session_attributes(bgp_sess_attrs)
        self.bgpaas_obj_uuid = self.connections.vnc_lib.bgp_as_a_service_create(self.bgpaas_obj)
        self.logger.info('Created BGPaas Object:%s'%self.bgpaas_obj_uuid)

    def cleanUp(self):
        super(BgpaasFixture, self).cleanUp()
        self.delete()

    @retry(delay=10, tries=20)
    def verify_bgpaas_in_control_nodes(self):

        result = True
        cn_nodes = self.cn_inspect.keys()
        for cn in cn_nodes:
            cn_bgp_neighbors = self.cn_inspect[cn].get_cn_bgp_neigh_entry()
            peer_info = None
            self.logger.info("cn_node:"+cn)
            self.logger.info("cn_inspect:",self.cn_inspect[cn])
            self.logger.info("cn_bgp_neighbors: "+cn_bgp_neighbors)
            for cn_bgp_neighbor in cn_bgp_neighbors:
               if cn_bgp_neighbor['state'] != 'Established' and \
                      cn_bgp_neighbor['peer_id'] == self.bgp_vm_peer_ip:
                  result = result and False
                  self.logger.error(
                      'With Peer %s peering is not Established. Current State %s ' %
                      (cn_bgp_neighbor['peer_id'], cn_bgp_neighbor['state']))
                  continue
	       elif cn_bgp_neighbor['peer_id'] == self.bgp_vm_peer_ip :
                  self.logger.info(
                      'With Peer %s peering is Established.' %
                      (cn_bgp_neighbor['peer_id'] ))
                  peer_info = cn_bgp_neighbor
            if not peer_info:
               continue
            vn_fq_name = self.vn_fixture.vn_fq_name.split(":")
            rt_name = self.vn_fixture.vn_fq_name + ":" + vn_fq_name[-1] + ".inet.0"
            rt_name_exist = False
            for rt in peer_info['routing_tables']:
                if rt['name'] == rt_name:
	           rt_name_exist = True
            route_seen = False
            for route_bgp in self.bgp_exported_routes_list:
                if rt_name_exist:
                   route_table = self.cn_inspect[cn].get_cn_route_table(rt_name)
	           for route in route_table['routes']:
                       self.logger.info("Route:%s"%route['prefix'])
	               if route['prefix']  == route_bgp:
                          route_seen = True
                if route_seen:        
                   self.logger.info('Route %s from BGPaas is seen in CN'%route_bgp) 		
                else:
                   self.logger.error('Route %s from BGPaas is NOT seen in CN'%route_bgp)
                   result = result and False
        return result


    @retry(delay=5, tries=10)
    def verify_bgpaas_in_api_server(self):
        self.api_verification_flag = True
        import pdb;pdb.set_trace()
        self.api_s_bgpaas_obj = self.api_s_inspect.get_cs_vn(
            domain=self.domain_name, project=self.project_name,
            vn=self.vn_name, refresh=True)

    def verify_bgpaas_in_opserver(self):
        '''Verify vn in the opserver'''

        self.logger.debug("Verifying the vn in opserver")
        res = self.analytics_obj.verify_bgpaas_link(self.vn_fixture.vn_fq_name,
                                self.vm_fixture.vmi_ids[self.vn_fixture.vn_fq_name])
        self.op_verification_flag = res
        return res


    def verify_on_setup(self):

        result = True

        #if not self.verify_bgpaas_in_api_server():
        #    result = result and False
        #    self.logger.error(
        #        "One or more verifications in API Server for BGPaaS %s failed" % (self.vn_name))
        #    return result

        if not self.verify_bgpaas_in_control_nodes():
            result = result and False
            self.logger.error(
                "One or more verifications in Control-nodes for BGPaaS failed")
            sys.exit()
            return result

        return result
        
        if not self.verify_bgpaas_in_opserver():
            result = result and False
            self.logger.error("E:BGPaas info NOT seen in OpServer")
            #self.logger.error(
            #    "One or more verifications in OpServer for BGPaaS %s failed" % (self.))
            return result
        else:
            self.logger.debug("D:BGPaas info seen in OpServer")
            self.logger.info("I:BGPaas info seen in OpServer")
        return result

        if self.inputs.verify_thru_gui():
            self.webui.verify_bgpaas(self)

        if not self.verify_bgpaas_in_agent():
            result = result and False
            self.logger.error('One or more verifications in agent for BGPaaS %s'
                'failed' % (self.vn_name))

        self.verify_is_run = True
        self.verify_result = result
        return result
    # end verify

    def delete(self, verify=False):
           self.logger.info('Deleting BGPaas Object: ' + self.bgpaas_obj_uuid )
           self.connections.vnc_lib.bgp_as_a_service_delete(id=self.bgpaas_obj_uuid)
