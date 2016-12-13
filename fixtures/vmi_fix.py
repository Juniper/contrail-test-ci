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
   def _read (self):
       self._vnc_obj = self._vnc.get_virtual_machine_interface(self.uuid)
       self._vnc_obj = self._vnc.get_virtual_machine_interface(self.uuid)
       return self._vnc_obj and self._obj

   def _create (self):
       self.logger.debug('Creating %s' % self)
       self.uuid = self._ctrl.create_virtual_machine_interface(**self._args)

   def _delete (self):
       self.logger.debug('Deleting %s' % self)
       self._ctrl.delete_virtual_machine_interface(obj=self._obj,
                                                   uuid=self.uuid)

   def _update (self):
       self.logger.debug('Updating %s' % self)
       self._ctrl.update_virtual_machine_interface(obj=self._obj,
                                                   uuid=self.uuid,
                                                   **self.args)

   def verify_on_setup (self):
       assert self.vnc_obj, '%s not found' % self
       #TODO: check if more verification is needed

   def verify_on_cleanup (self):
       ret, err = self._verify_not_in_api_server()
       assert ret, err
       #TODO: check if more verification is needed

   @retry(delay=5, tries=6)
   def _verify_not_in_api_server (self):
       if self._vnc.get_virtual_machine_interface(self.uuid):
           return False, '%s not removed' % self
       return True, None
