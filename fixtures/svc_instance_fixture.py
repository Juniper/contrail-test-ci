from contrail_fixtures import ContrailFixture
from tcutils.util import retry
from vnc_api.vnc_api import ServiceInstance

class SvcInstanceFixture (ContrailFixture):

   vnc_class = ServiceInstance

   def __init__ (self, connections, uuid=None, params=None, fixs=None):
       super(SvcInstanceFixture, self).__init__(
           uuid=uuid,
           connections=connections,
           params=params,
           fixs=fixs)
       self.api_s_inspect = connections.api_server_inspect

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

   @retry(delay=2, tries=10)
   def _read (self):
       self._vnc_obj = self._vnc.get_service_instance(self.uuid)
       # no orchestrator has api for service-instance, retain vnc obj
       self._obj = self._vnc_obj
       return self._vnc_obj and self._obj

   def _create (self):
       self.logger.debug('Creating %s' % self)
       if self.inputs.availability_zone:
           self.args['service_instance_properties']\
                    ['availability_zone'] = self.inputs.availability_zone

       self.uuid = self._ctrl.create_service_instance(**self._args)

   def _delete (self):
       self.logger.debug('Deleting %s' % self)
       self._ctrl.delete_service_instance(obj=self._obj, uuid=self.uuid)

   def _update (self):
       self.logger.debug('Updating %s' % self)
       self._ctrl.update_service_instance(obj=self._obj, uuid=self.uuid,
                                          **self.args)

   def verify_on_setup (self):
       assert self.vnc_obj, '%s not found' % self
       ret, err = self._verify_st()
       assert ret, err
       ret, err = self._verify_pt()
       assert ret, err
       #TODO: check if more verification is needed

   def verify_on_cleanup (self):
       ret, err = self._verify_not_in_api_server()
       assert ret, err
       #TODO: check if more verification is needed

   @retry(delay=2, tries=10)
   def _verify_st (self):
       project, si = self.fq_name[1:]
       self.cs_si = self.api_s_inspect.get_cs_si(project=project, si=si,
                                                  refresh=True)
       try:
           st_refs = self.cs_si['service-instance']['service_template_refs']
       except KeyError:
           st_refs = None
       if not st_refs:
           errmsg = "%s has no service template refs" % self
           return False, errmsg

       self.st_fix = self.fixs['id-map'][st_refs[0]['uuid']]
       if self._args:
           expected = set([st['to'][-1]
                           for st in self._args['service_template_refs']])
           got = set([st_ref['to'][-1] for st_ref in st_refs])
           if expected - got:
               errmsg = "%s fails service template ref check" % self
               return False, errmsg
       return True, None

   @retry(delay=5, tries=5)
   def _verify_pt (self):
       try:
           pt_refs = self.cs_si['service-instance']['port_tuples']
       except KeyError:
           pt_refs = None
       if not pt_refs:
           errmsg = "%s has no port tuple refs" % self
           return False, errmsg
       return True, None

   @retry(delay=5, tries=6)
   def _verify_not_in_api_server (self):
       if self._vnc.get_service_instance(self.uuid):
           return False, '%s not removed' % self
       return True, None
