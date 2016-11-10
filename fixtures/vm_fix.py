from tcutils.util import retry
from contrail_fixtures import ContrailFixture

class VMFixture (ContrailFixture):

   def __init__ (self, connections, rid=None, params=None):
       super(VMFixture, self).__init__(rid, connections)
       self._args = params

   def get_attr (self, lst):
       if lst == ['fq_name']:
           return self.fq_name
       return None

   def get_resource (self):
       return self.uuid

   @retry(delay=1, tries=5)
   def _read (self, rid):
       self._obj = self._ctrl.get_virtual_machine(rid)
       self._vnc_obj = self._vnc.get_virtual_machine(rid)
       return self._vnc_obj and self._obj

   def _create (self):
       rid = self._ctrl.create_virtual_machine(**self._args)
       self._read(rid)

   def _delete (self):
       self._ctrl.delete_virtual_machine(self._obj)

   def _update (self, params):
       pass

   def verify_on_setup ():
       pass

   def verify_on_cleanup ():
       pass
