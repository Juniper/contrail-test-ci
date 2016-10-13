from contrail_fixtures import ContrailFixture, process_refs

def _v2_args (args, objs):
   fields = [
       ('service_health_check_refs',),
       ('routing_instance_refs', 'routing_instance_refs_data'),
       ('security_group_refs',),
       ('physical_interface_refs',),
       ('port_tuple_refs',),
       ('interface_route_table_refs',),
       ('virtual_machine_inteface_refs',),
       ('virtual_network_refs',),
       ('virtual_machine_refs',),
       ('qos_config_refs',),
   ]
   new_args = process_refs(args, fields, objs)
   return new_args

def transform_args (ver, args, topo):
   if 'OS::ContrailV2::' in ver:
       return _v2_args(args, topo)
   return args

class PortFixture (ContrailFixture):

   def __init__ (self, connections, rid=None, params=None):
       super(PortFixture, self).__init__(rid, connections)
       self._args = params

   def get_attr (self, lst):
       if lst == ['fq_name']:
           return self.fq_name
       return None

   def get_resource (self):
       return self.uuid

   def _read (self, rid):
       self._vnc_obj = self._vnc.get_virtual_machine_interface(rid)
   
   def _create (self):
       rid = self._ctrl.create_virtual_machine_interface(**self._args)
       self._read(rid)
       pass

   def _delete (self):
       self._ctrl.delete_virtual_machine_interface(self._vnc_obj)

   def _update (self, params):
       pass

   def verify_on_setup ():
       pass

   def verify_on_cleanup ():
       pass
