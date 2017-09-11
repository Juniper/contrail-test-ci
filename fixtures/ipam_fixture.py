#TODO: check ref to IPAMFixture
from contrail_fixtures import ContrailFixture
from tcutils.util import retry
from vnc_api.vnc_api import NetworkIpam

class IPAMFixture_v2 (ContrailFixture):

   vnc_class = NetworkIpam

   def __init__ (self, connections, uuid=None, params=None, fixs=None):
       super(IPAMFixture_v2, self).__init__(
           uuid=uuid,
           connections=connections,
           params=params,
           fixs=fixs)
       self.cn_inspect = connections.cn_inspect
       self.api_s_inspect = connections.api_server_inspect
       self.agent_inspect = connections.agent_inspect

   def get_attr (self, lst):
       if lst == ['fq_name']:
           return self.fq_name
       return None

   def get_resource (self):
       return self.uuid

   def __str__ (self):
       #TODO: __str__
       if self._args:
           info = ''
       else:
           info = ''
       return '%s:%s' % (self.type_name, info)

   @retry(delay=1, tries=5)
   def _read_vnc_obj (self):
       obj = self._vnc.get_network_ipam(self.uuid)
       found = 'not' if not obj else ''
       self.logger.debug('%s %s found in api-server' % (self, found))
       return obj != None, obj

   def _read (self):
       ret, obj = self._read_vnc_obj()
       if ret:
           self._vnc_obj = obj
       self._obj = self._vnc_obj

   def _create (self):
       self.logger.info('Creating %s' % self)
       self.uuid = self._ctrl.create_network_ipam(
           **self._args)

   def _delete (self):
       self.logger.info('Deleting %s' % self)
       self._ctrl.delete_network_ipam(
           obj=self._obj, uuid=self.uuid)

   def _update (self):
       self.logger.info('Updating %s' % self)
       self._ctrl.update_network_ipam(
           obj=self._obj, uuid=self.uuid, **self.args)

   def verify_on_setup (self):
       self.assert_on_setup(*self._verify_in_api_server())
       self.assert_on_setup(*self._verify_in_control_nodes())

   def verify_on_cleanup (self):
       self.assert_on_cleanup(*self._verify_not_in_api_server())
       self.assert_on_cleanup(*self._verify_not_in_control_nodes())

   def _verify_in_api_server (self):
       if not self._read_vnc_obj()[0]:
           msg= '%s not found in api-server' % self
           self.logger.error(msg)
           return False, msg
       return True, None

   @retry(delay=5, tries=6)
   def _verify_not_in_api_server (self):
       if self._vnc.get_network_ipam(self.uuid):
           msg = '%s not removed from api-server' % self
           self.logger.error(msg)
           return False, msg
       self.logger.debug('%s removed from api-server' % self)
       return True, None

   @retry(delay=5, tries=3)
   def _verify_in_control_nodes (self):
       project, ipam = self.fq_name[1:]
       fqname = self.fq_name_str
       for cn in self.inputs.bgp_ips:
           obj = self.cn_inspect[cn].get_cn_config_ipam(
                ipam=ipam, project=project)
           if not obj:
               msg = 'Control-node %s does not have IPAM %s' % (cn, ipam)
               self.logger.error(msg)
               return False, msg
           if fqname not in obj['node_name']:
               msg = 'IFMAP View of Control-node does not have IPAM %s' % fqname
               self.logger.error(msg)
               return False, msg
       self.logger.debug('%s fonud in control node' % self)
       return True, None

   @retry(delay=5, tries=10)
   def _verify_not_in_control_nodes(self):
       fqname = self.fq_name_str
       project, ipam = self.fq_name[1:]
       ri_name = fqname + ':' + self.name
       for cn in self.inputs.bgp_ips:
           if self.cn_inspect[cn].get_cn_routing_instance(ri_name=ri_name):
               msg = "RI for IPAM %s is still found in Control-node %s" % (self.name, cn)
               self.logger.error(msg)
               return False, msg
           if self.cn_inspect[cn].get_cn_config_ipam(ipam=ipam, project=project):
               msg = "Control-node config DB still has IPAM %s" % ipam
               self.logger.error(msg)
               return False, msg

       self.logger.debug("IPAM:%s is not found in control node" % ipam)
       return True, None


from tcutils.util import get_random_name
from vnc_api.vnc_api import IpamType
                            
class IPAMFixture (IPAMFixture_v2):

   ''' Fixture for backward compatiblity '''

   #TODO:
   def __init__ (self, connections,
                 **kwargs):
       domain = connections.domain_name
       prj = kwargs.get('project_name') or connections.project_name
       prj_fqn = domain + ':' + prj
       name = kwargs.get('ipam_name')
       self._api = kwargs.get('option', 'contrail')
       self.inputs = connections.inputs
       
       if name:
           uid = self._check_if_present(connections, name, [domain, prj])
           if uid:
               super(IPAMFixture, self).__init__(connections=connections,
                                               uuid=uid)
               return
       else:
           name = get_random_name(prj)
       self._construct_contrail_params(name, prj_fqn, kwargs)
       super(IPAMFixture, self).__init__(connections=connections,
                                       params=self._params)

   def _check_if_present (self, conn, name, prj_fqn):
       uid = prj_fqn + [name]
       obj = conn.get_orch_ctrl().get_api('vnc').get_network_ipam(uid)
       if not obj:
           return None
       return uid

   def setUp (self):
       super(IPAMFixture, self).setUp()

   def cleanUp (self):
       super(IPAMFixture, self).cleanUp()

   def _construct_contrail_params (self, name, prj_fqn, kwargs):
       self._params = {
           'type': 'OS::ContrailV2::NetworkIpam',
           'name' : name,
           'project': prj_fqn,
       }
       self._params['network_ipam_mgmt'] = {}
       
       network_ipam_mgmt = kwargs.get('ipamtype') or IpamType("dhcp")
       self._params['network_ipam_mgmt']['ipam_method'] = network_ipam_mgmt.ipam_method 
       self._params['network_ipam_mgmt']['ipam_dns_method'] = network_ipam_mgmt.ipam_dns_method

       if self._params['network_ipam_mgmt']['ipam_dns_method'] == 'virtual-dns-server':
           self._params['network_ipam_mgmt']['ipam_dns_server']= {'virtual_dns_server_name' : \
                                        network_ipam_mgmt.ipam_dns_server.virtual_dns_server_name}
           self._params['virtual_DNS_refs'] = [network_ipam_mgmt.ipam_dns_server.virtual_dns_server_name]
            
