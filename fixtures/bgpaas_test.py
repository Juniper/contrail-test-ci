import fixtures
import time
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

    def __init__(self,project_name,connections,vm_fixture,service_name,asn):

        self.vm_fixture   = vm_fixture
        self.service_name = service_name
        self.asn          = asn
        self.connections = connections
        self.agent_inspect = self.connections.agent_inspect
        self.cn_inspect = self.connections.cn_inspect
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

    def _create_bgpaas(self):

        result = True
        bgpaas_obj = BgpAsAService(name=self.service_name,parent_obj=self.project_obj)
        vmi = None
        vmi_ids = self.vm_fixture.get_vmi_ids()
        for k,vmi_id in vmi_ids.iteritems():
            vmi_obj  = self.connections.vnc_lib.virtual_machine_interface_read(id=vmi_id)
            networks = vmi_obj.get_virtual_network_refs()[0]['to']
            def_dom,t_name,netname = networks
            if re.search('BGP',netname):
               vmi = vmi_obj
               break
            else:
               continue
        if vmi:
            inst_ips = vmi.get_instance_ip_back_refs()
            ip_obj = self.connections.vnc_lib.instance_ip_read(id=inst_ips[0]['uuid'])
            bgpaas_obj.add_virtual_machine_interface(vmi) # vSRX VMI
            bgpaas_obj.set_autonomous_system(self.asn)
            bgpaas_obj.set_display_name(self.service_name)
            bgpaas_obj.set_bgpaas_ip_address(ip_obj.get_instance_ip_address()) # get instance IP attached to vmi.
            bgp_addr_fams = AddressFamilies(['inet','inet6'])
            bgp_sess_attrs = BgpSessionAttributes(address_families=bgp_addr_fams,hold_time=300)
            bgpaas_obj.set_bgpaas_session_attributes(bgp_sess_attrs)
            self.bgpaas_obj = self.connections.vnc_lib.bgp_as_a_service_create(bgpaas_obj)
            self.logger.info('Created BGPaas Object')

            time.sleep(60)

            cn_nodes = self.cn_inspect.keys()
            cn = cn_nodes[0]
            cn_bgp_neighbors = self.cn_inspect[cn].get_cn_bgp_neigh_entry()
            peer_info = None
            for cn_bgp_neighbor in cn_bgp_neighbors:
               if cn_bgp_neighbor['state'] != 'Established':
                  result = result and False
                  self.logger.error(
                      'With Peer %s peering is not Established. Current State %s ' %
                      (cn_bgp_neighbor['peer_id'], cn_bgp_neighbor['state']))
                  continue
	       if cn_bgp_neighbor['peer_id'] == '1.3.0.3' :
                  self.logger.info(
                      'With Peer %s peering is Established.' %
                      (cn_bgp_neighbor['peer_id'] ))
                  peer_info = cn_bgp_neighbor
            rt_name = None
            if peer_info:
               for rt in peer_info['routing_tables']:
                   if re.search('Private_BGP_Addnl',rt['name']):
		      rt_name = rt['name']	
            route_seen = False
            if rt_name:
               route_table = self.cn_inspect[cn].get_cn_route_table(rt_name)
	       for route in route_table['routes']:
	           if route['prefix']  == '3.1.1.5/32':
                      route_seen = True
            if route_seen:        
               self.logger.info('Route 3.1.1.5/32 from BGPaas is seen in CN') 		
            else:
               self.logger.error('Route 3.1.1.5/32 from BGPaas is NOT seen in CN') 		
               result = result and False
            return result

    def cleanUp(self):
        super(BgpaasFixture, self).cleanUp()
        self.delete()

    def delete(self, verify=False):
           self.logger.info('Deleting BGPaas Object: ' + self.bgpaas_obj )
           self.connections.vnc_lib.bgp_as_a_service_delete(id=self.bgpaas_obj)
