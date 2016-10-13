from contrail_fixtures import ContrailFixture, process_refs

def _v2_args (args, objs):
   fields = [
       ('physical_router_refs',),
       ('virtual_machine_interface_refs',),
       ('virtual_network_refs',),
   ]
   new_args = process_refs(args, fields, objs)
   return new_args

def transform_args (ver, args, topo):
   if 'OS::ContrailV2::' in ver:
       return _v2_args(args, topo)
   return args

class InstanceIpFixture (ContrailFixture):

   def __init__ (self, connections, rid=None, params=None):
       super(InstanceIpFixture, self).__init__(rid, connections)
       self._args = params

   def get_attr (self, lst):
       if lst == ['fq_name']:
           return self.fq_name
       return None

   def get_resource (self):
       return self.uuid

   def _read (self, rid):
       self._vnc_obj = self._vnc.get_instance_ip(rid)
   
   def _create (self):
       rid = self._ctrl.create_instance_ip(**self._args)
       self._read(rid)

   def _delete (self):
       self._ctrl.delete_instance_ip(self._vnc_obj)

   def _update (self, params):
       pass

   def verify_on_setup ():
       pass

   def verify_on_cleanup ():
       pass
