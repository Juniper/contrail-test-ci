from contrail_fixtures import ContrailFixture, process_refs

def _v2_args (args, objs):
   fields = [
       ('service_template_refs',),
       ('instance_ip_refs', 'instance_ip_refs_data'),
   ]
   new_args = process_refs(args, fields, objs)
   return new_args

def transform_args (ver, args, topo):
   if 'OS::ContrailV2' in ver:
       return _v2_args(args, topo)
   return args

class SvcInstanceFixture (ContrailFixture):

   def __init__ (self, connections, rid=None, params=None):
       super(SvcInstanceFixture, self).__init__(rid, connections)
       self._args = params

   def get_attr (self, lst):
       if lst == ['fq_name']:
           return self.fq_name
       return None

   def get_resource (self):
       return self.uuid

   def _read (self, rid):
       self._vnc_obj = self._vnc.get_service_instance(rid)
   
   def _create (self):
       rid = self._ctrl.create_service_instance(**self._args)
       self._read(rid)

   def _delete (self):
       self._ctrl.delete_service_instance(self._vnc_obj)

   def _update (self, params):
       pass

   def verify_on_setup ():
       pass

   def verify_on_cleanup ():
       pass
