from contrail_fixtures import ContrailFixture
from tcutils.util import retry
from vnc_api.vnc_api import VirtualMachineInterface
import fixture

class PortFixture_v2 (ContrailFixture):

   vnc_class = VirtualMachineInterface

   def __init__ (self, connections, uuid=None, params=None, fixs=None):
       super(PortFixture_v2, self).__init__(
           uuid=uuid,
           connections=connections,
           params=params,
           fixs=fixs)
       # Note: Add type specific initialization

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
       obj = self._vnc.get_virtual_machine_interface(self.uuid)
       return obj != None, obj

   @retry(delay=1, tries=5)
   def _read_orch_obj (self):
       with self._api_ctx:
           obj = self._ctrl.get_virtual_machine_interface(self.uuid)
       return obj != None, obj

   def _read (self):
       ret, obj = self._read_vnc_obj()
       if ret:
           self._vnc_obj = obj
       ret, obj = self._read_orch_obj()
       if ret:
           self._obj = obj

   def _create (self):
       self.logger.info('Creating %s' % self)
       with self._api_ctx:
           self.uuid = self._ctrl.create_virtual_machine_interface(
               **self._args)

   def _delete (self):
       self.logger.info('Deleting %s' % self)
       with self._api_ctx:
           self._ctrl.delete_virtual_machine_interface(
               obj=self._obj, uuid=self.uuid)

   def _update (self):
       self.logger.info('Updating %s' % self)
       with self._api_ctx:
           self._ctrl.update_virtual_machine_interface(
               obj=self._obj, uuid=self.uuid, **self.args)

   def verify_on_setup (self):
       assert_on_setup(self._verify_in_api_server())

   def verify_on_cleanup (self):
       assert_on_setup(self._verify_in_api_server())

   def _verify_in_api_server (self):
       vmi = self.api_inspect_h.get_cs_vmi(self.uuid)
       if not vmi:
           msg = 'Unable to fetch VMI from API server'
           return False, msg
       if self._profile:
           bindings = vmi.get_bindings()
           if bindings['profile'] != json.dumps(self._profile):
               msg = 'VMI binding profile doesnt match' % (self._profile,
                       bindings['profile'])
               return False, msg
       return True, None

   def _verify_not_in_api_server (self):
       if self.api_inspect_h.get_cs_vmi(self.uuid, True)
           msg = 'VMI still present in API server'
           return False, msg
       return True, None

import uuid
from tcutils.util import get_random_name
from instance_ip_fixture import InstanceIpFixture

class PortFixture (PortFixture_v2):

   """ Fixture for backward compatiblity """

   def __init__ (self, connections, **kwargs):
       domain = connections.domain_name
       prj = kwargs.get('project_name') or connections.project_name
       prj_fqn = domain + ':' + prj
       name = str(uuid.uuid4())
       self._api = kwargs.get('api_type', 'neutron')
       self._vn_id = kwargs['vn_id']

       if self._api == 'contrail':
           self._construct_contrail_params(name, prj_fqn, kwargs)
           if 'fixed_ips' in kwargs:
               self._fixed_ips = kwargs['fixed_ips']
       else:
           self._construct_quantum_params(name, prj_fqn, kwargs)
       super(PortFixture, self).__init__(
               connections=connections, params=self._params)

   def _create_fixed_ips (self):
       lst = []
       for ip in getattr(self, '_fixed_ips'):
           args = {
               'type': 'OS::ContrailV2::InstanceIp',
               'name': get_random_name(),
               'subnet_uuid': kwargs['subnet_id'],
               'virtual_machine_interface_refs': [self.uuid],
               'virtual_network_refs': [self._vn_id],
           }
           if 'ip_address' in ip:
               args['instance_ip_address'] = ip['ip_address']
           args['instance_ip_secondary'] = ip.get('instance_ip_secondary',
                                                   False)
           fix = self.useFixture(InstanceIpFixture(
               connections=self.connections,
               params=args))
           lst.append(fix)
       self._fixed_ips = lst

   def setUp (self):
       super(PortFixture, self).setUp()
       self.vnc_api = self._vnc._vnc # direct handle to vnc library
       self._create_fixed_ips()

   def _construct_contrail_params (self, name, prj_fqn, kwargs):
       self._params = {
           'type': 'OS::ContrailV2::VirtualMachineInterface',
           'name': name,
           'project': prj_fqn,
           'virtual_network_refs': [kwargs['vn_id']],
       }
       if 'mac_address' in kwargs:
           self._params['virtual_machine_interface_mac_addresses'] = {
               'mac_address': [kwargs['mac_address']],
           }
       if 'vlan_id' in kwargs:
           dd = self._params.get('virtual_machine_interface_properties', {})
           dd['sub_interface_vlan_tag'] = int(kwargs['vlan_id'])
           self._params['virtual_machine_interface_properties'] = dd
       if 'parent_vmi' in kwargs:
           self._params['virtual_machine_interface_refs'] = [\
                   kwargs['parent_vmi']]
       if 'binding_profile' in kwargs:
           k = kwargs['binding_profile'].keys()[0]
           v = kwargs['binding_profile'].values()[0]
           self._params['virtual_machine_interface_bindings'] = {
               'key_value_pair': [{'key': 'profile',
                                   'value': str(kwargs['binding_profile'])}]
           }
       if 'security_groups' in kwargs:
           self._params['security_group_refs'] = kwargs['security_groups']
       if 'extra_dhcp_opts' in kwargs:
           pass #TODO

   def _construct_quantum_params (self, name, prj_fqn, kwargs):
       self._params = {
           'type': 'OS::Neutron::Port',
           'name': name,
           'network_id': kwargs['vn_id'],
       }
       if 'mac_address' in kwargs:
           self._params['mac_address'] = kwargs['mac_address']
       if 'security_groups' in kwargs:
           self._params['security_groups'] = kwargs['security_groups']
       if 'binding_profile' in kwargs:
           self._params['binding:profile'] = kwargs['binding_profile']
       if 'fixed_ips' in kwargs:
           self._params['fixed_ips'] = kwargs['fixed_ips']
       if 'extra_dhcp_opts' in kwargs:
           self._params['extra_dhcp_opts'] = kwargs['extra_dhcp_opts']

   def add_fat_flow (self, fat_flow_config):
       '''
       fat_flow_config: dictionary of format {'proto':<string>,'port':<int>}
       '''
       proto_type = ProtocolType(protocol=fat_flow_config['proto'],
               port=fat_flow_config['port'])
       fat = self.vnc_obj.get_virtual_machine_interface_fat_flow_protocols()
       if fat:
           fat.fat_flow_protocol.append(proto_type)
       else:
           fat = FatFlowProtocols(fat_flow_protocol=[proto_type])
           self.vnc_obj.set_virtual_machine_interface_fat_flow_protocols(fat)
       self.vnc_api.virtual_machine_interface_update(self.vnc_obj)
       self.update()
       return True

   def remove_fat_flow (self, fat_flow_config):
       '''
       fat_flow_config: dictionary of format {'proto':<string>,'port':<int>}
       '''
       fat = self.vnc_obj.get_virtual_machine_interface_fat_flow_protocols()
       if fat:
           for config in fat.fat_flow_protocol:
               if config.protocol == fat_flow_config['proto'] and \
                       config.port == fat_flow_config['port']:
                   break
           else:
               config = None
       if config:
           fat.fat_flow_protocol.remove(config)
           self.vnc_obj.set_virtual_machine_interface_fat_flow_protocols(fat)
           self.vnc_api.virtual_machine_interface_update(self.vnc_obj)
           self.update()
       return True

   def add_interface_route_table (self, intf_route_table_obj):
       '''
       Adds interface static routes to a port

       Args:
       intf_route_table_obj:  InterfaceRouteTable instance
       '''
       self.vnc_obj.add_interface_route_table(intf_route_table_obj)
       self.vnc_api.virtual_machine_interface_update(self.vnc_obj)
       self.update()

   def del_interface_route_table(self, intf_route_table_uuid):
       '''Unbind intf_route_table_obj from port
       intf_route_table_obj is InterfaceRouteTable instance
       '''
       self.vnc_obj.del_interface_route_table(intf_route_table_uuid)
       self.vnc_api.virtual_machine_interface_update(self.vnc_obj)
       self.update()
