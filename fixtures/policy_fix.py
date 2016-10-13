from contrail_fixtures import ContrailFixture

def transform_args (ver, args, topo):
   return args

class PolicyFixture (ContrailFixture):

   def __init__(self, connections, rid=None, params=None):
       super(PolicyFixture, self).__init__(rid, connections)
       self._args = params

   def get_attr (self, lst):
       if lst == ['fq_name']:
           return self.fq_name
       return None

   def get_resource (self):
       return self.uuid

   def _read (self, rid):
       self._obj = self._ctrl.get_network_policy(rid)
       self._vnc_obj = self._vnc.get_network_policy(rid)
   
   def _create (self):
       rid = self._ctrl.create_network_policy(**self._args)
       self._read(rid)

   def _delete (self):
       self._ctrl.delete_network_policy(self._obj)

   def _update (self, params):
       self._args.update(params)
       rid = self._vnc_obj.uuid
       self._ctrl.update_network_policy(self._obj, **self._args)
       self._read(rid)

   def verify_on_setup ():
       pass

   def verify_on_cleanup ():
       pass
