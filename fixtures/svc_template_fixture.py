from contrail_fixtures import ContrailFixture
from tcutils.util import retry
from vnc_api.vnc_api import ServiceTemplate

class SvcTemplateFixture (ContrailFixture):

   vnc_class = ServiceTemplate

   def __init__ (self, connections, uuid=None, params=None, fixs=None):
       super(SvcTemplateFixture, self).__init__(
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
           info = self._args['name']
       else:
           info = self.uuid
       return '%s:%s' % (self.type_name, info)

   @retry(delay=1, tries=5)
   def _read (self):
       self._vnc_obj = self._vnc.get_service_template(self.uuid)
       # no orchestrator has api for service-template, retain vnc obj
       self._obj = self._vnc_obj
       return self._vnc_obj and self._obj

   def _create (self):
       self.logger.debug('Creating %s' % self)
       if self.inputs.availability_zone:
           self.args['service_template_properties']\
                    ['availability_zone_enable'] = self.inputs.availability_zone

       self.uuid = self._ctrl.create_service_template(**self.args)

   def _delete (self):
       self.logger.debug('Deleting %s' % self)
       self._ctrl.delete_service_template(obj=self._obj, uuid=self.uuid)

   def _update (self):
       self.logger.debug('Updating %s' % self)
       self._ctrl.update_service_template(obj=self._obj, uuid=self.uuid,
                                          **self.args)

   @property
   def version (self):
       if self._args:
           return self._args['service_template_properties']['version']
       else:
           return self.vnc_obj.service_template_properties.version

   def verify_on_setup (self):
       assert self.vnc_obj, '%s not found' % self

       if self._args:
           ver = self._vnc_obj.service_template_properties.version
           exp_ver = self._args['service_template_properties']['version']
           msg = '%s version mismatch expected:%d got:%d' % (self, exp_ver, ver)
           assert ver==exp_ver, msg
       #TODO: check if more verification is needed

   def verify_on_cleanup (self):
       ret, err = self._verify_not_in_api_server()
       assert ret, err
       #TODO: check with more verification is required

   @retry(delay=5, tries=6)
   def _verify_not_in_api_server (self):
       if self._vnc.get_service_template(self.uuid):
           return False, '%s not removed' % self
       return True, None
