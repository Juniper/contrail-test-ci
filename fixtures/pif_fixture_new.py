#TODO: replaces pif_fixture.py
from contrail_fixtures import ContrailFixture
from tcutils.util import retry
from vnc_api.vnc_api import PhysicalInterface

class PhysicalInterfaceFixture (ContrailFixture):

   vnc_class = PhysicalInterface

   def __init__ (self, connections, uuid=None, params=None, fixs=None):
       super(PhysicalInterfaceFixture_v2, self).__init__(
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
       obj = self._vnc.get_physical_interface(self.uuid)
       return obj != None, obj

   def _read (self):
       ret, obj = self._read_vnc_obj()
       if ret:
           self._vnc_obj = obj
       self._obj = self._vnc_obj

   def _create (self):
       self.logger.info('Creating %s' % self)
       with self._api_ctx:
           self.uuid = self._ctrl.create_physical_interface(
               **self._args)

   def _delete (self):
       self.logger.info('Deleting %s' % self)
       with self._api_ctx:
           self._ctrl.delete_physical_interface(
               obj=self._obj, uuid=self.uuid)

   def _update (self):
       self.logger.info('Updating %s' % self)
       with self._api_ctx:
           self._ctrl.update_physical_interface(
               obj=self._obj, uuid=self.uuid, **self.args)

   def verify_on_setup (self):
       #TODO: add verification code
       pass

   def verify_on_cleanup (self):
       #TODO: add verification code
       pass
