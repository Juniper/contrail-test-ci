from contrail_fixtures import ContrailFixture, process_refs

def _v2_args (args, objs):
   fields = [
       ('network_ipam_refs', 'network_ipam_refs_data'),
       ('network_policy_refs', 'network_policy_refs_data'),
       ('route_table_refs',),
       ('qos_config_refs',),
   ]
   new_args = process_refs(args, fields, objs)
   return new_args

def transform_args (ver, args, topo):
   if 'OS::ContrailV2::' in ver:
       return _v2_args(args, topo)
   return args

class VNFixture (ContrailFixture):

   def __init__ (self, connections, rid=None, params=None):
       super(VNFixture, self).__init__(rid, connections)
       self._args = params

   def get_attr (self, lst):
       if lst == ['fq_name']:
           return self.fq_name
       return None

   def get_resource (self):
       return self.uuid

   def _read (self, rid):
       self._obj = self._ctrl.get_virtual_network(rid)
       self._vnc_obj = self._vnc.get_virtual_network(rid)

   def _create (self):
       rid = self._ctrl.create_virtual_network(**self._args)
       self._read(rid)

   def _delete (self):
       self._ctrl.delete_virtual_network(self._obj)

   def _update (self, params):
       pass

   def verify_on_setup ():
       pass

   def verify_on_cleanup ():
       pass
