#TODO integrate with port_fixture.py
from contrail_fixtures import ContrailFixture
from tcutils.util import retry
from vnc_api.vnc_api import VirtualMachineInterface

class PortFixture (ContrailFixture):

   vnc_class = VirtualMachineInterface

   def __init__ (self, connections, uuid=None, params=None, fixs=None):
       super(PortFixture, self).__init__(
           uuid=uuid,
           connections=connections,
           params=params,
           fixs=fixs)

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
       found = 'not' if not obj else ''
       self.logger.debug('%s %s found in api-server' % (self, found))
       return obj != None, obj

   @retry(delay=1, tries=5)
   def _read_orch_obj (self):
       obj = self._ctrl.get_virtual_machine_interface(self.uuid)
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
       self.uuid = self._ctrl.create_virtual_machine_interface(
           **self._args)

   def _delete (self):
       self.logger.info('Deleting %s' % self)
       self._ctrl.delete_virtual_machine_interface(
           obj=self._obj, uuid=self.uuid)

   def _update (self):
       self.logger.info('Updating %s' % self)
       self._ctrl.update_virtual_machine_interface(
           obj=self._obj, uuid=self.uuid, **self.args)

   def verify_on_setup (self):
       self.assert_on_setup(*self._verify_in_api_server())
       self.assert_on_setup(*self._verify_in_orch())
       #TODO: check if more verification is needed

   def verify_on_cleanup (self):
       self.assert_on_cleanup(*self._verify_not_in_api_server())
       self.assert_on_cleanup(*self._verify_not_in_orch())
       #TODO: check if more verification is needed

   def _verify_in_api_server (self):
       if not self._read_vnc_obj()[0]:
           return False, '%s not found in api-server' % self
       return True, None

   @retry(delay=5, tries=6)
   def _verify_not_in_api_server (self):
       if self._vnc.get_virtual_machine_interface(self.uuid):
           msg = '%s not removed from api-server' % self
           self.logger.debug(msg)
           return False, msg
       self.logger.debug('%s removed from api-server' % self)
       return True, None

   def _verify_in_orch (self):
       if not self._read_orch_obj()[0]:
           return False, '%s not found in orchestrator' % self
       return True, None

   @retry(delay=5, tries=6)
   def _verify_not_in_orch (self):
       if self._ctrl.get_virtual_machine_interface(self.uuid):
           msg = '%s not removed from orchestrator' % self
           self.logger.debug(msg)
           return False, msg
       self.logger.debug('%s removed from orchestrator' % self)
       return True, None
