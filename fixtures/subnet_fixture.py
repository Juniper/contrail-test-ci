from contrail_fixtures import ContrailFixture
from tcutils.util import retry
from vnc_api.vnc_api import Subnet

class SubnetFixture (ContrailFixture):

   vnc_class = Subnet

   def __init__ (self, connections, uuid=None, params=None, fixs=None):
       super(SubnetFixture, self).__init__(
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
       obj = self._vnc.get_subnet(self.uuid)
       found = 'not' if not obj else ''
       self.logger.debug('%s %s found in api-server' % (self, found))
       return obj != None, obj

   @retry(delay=1, tries=5)
   def _read_orch_obj (self):
       with self._api_ctx:
           obj = self._ctrl.get_subnet(self.uuid)
       found = 'not' if not obj else ''
       self.logger.debug('%s %s found in orchestrator' % (self, found))
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
           self.uuid = self._ctrl.create_subnet(
               **self._args)

   def _delete (self):
       self.logger.info('Deleting %s' % self)
       with self._api_ctx:
           self._ctrl.delete_subnet(
               obj=self._obj, uuid=self.uuid)

   def _update (self):
       self.logger.info('Updating %s' % self)
       with self._api_ctx:
           self._ctrl.update_subnet(
               obj=self._obj, uuid=self.uuid, **self.args)

   def verify_on_setup (self):
       #TODO: check if more verification is needed
       pass

   def verify_on_cleanup (self):
       #TODO: check if more verification is needed
       pass
