from contrail_fixtures import ContrailFixture

def transform_args (ver, args, topo):
   return args

class PortTupleFixture (ContrailFixture):

   def __init__ (self, connections, rid=None, params=None):
       super(PortTupleFixture, self).__init__(rid, connections)
       self._args = params

   def get_attr (self, lst):
       if lst == ['fq_name']:
           return self.fq_name
       return None

   def get_resource (self):
       return self.uuid

   def _read (self, rid):
       self._vnc_obj = self._vnc.get_port_tuple(rid)

   def _create (self):
       rid = self._ctrl.create_port_tuple(**self._args)
       self._read(rid)

   def _delete (self):
       self._ctrl.delete_port_tuple(self._vnc_obj)
       pass

   def _update (self, params):
       pass

   def verify_on_setup ():
       pass

   def verify_on_cleanup ():
       pass
