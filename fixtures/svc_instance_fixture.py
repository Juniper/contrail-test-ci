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
       self.api_inspect = connections.api_server_inspect

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

   @retry(delay=2, tries=10)
   def _read_vnc_obj (self):
       obj = self._vnc.get_service_instance(self.uuid)
       found = 'not' if not obj else ''
       self.logger.debug('%s %s found in api-server' % (self, found))
       return obj != None, obj

   def _read (self):
       ret, obj = self._read_vnc_obj()
       if ret:
           self._vnc_obj = obj
       self._obj = self._vnc_obj

   def _create (self):
       self.logger.info('Creating %s' % self)
       self.uuid = self._ctrl.create_service_instance(
           **self._args)

   def _delete (self):
       self.logger.info('Deleting %s' % self)
       self._ctrl.delete_service_instance(
           obj=self._obj, uuid=self.uuid)

   def _update (self):
       self.logger.info('Updating %s' % self)
       self._ctrl.update_service_instance(
           obj=self._obj, uuid=self.uuid, **self.args)

   def verify_on_setup (self):
       self.assert_on_setup(*self._verify_in_api_server())
       self.assert_on_setup(*self._verify_st())
       self.assert_on_setup(*self._verify_pt())
       #TODO: check if more verification is needed

   def verify_on_cleanup (self):
       self.assert_on_cleanup(*self._verify_not_in_api_server())
       #TODO: check if more verification is needed

   def _verify_in_api_server (self):
       if not self._read_vnc_obj()[0]:
           return False, '%s not found in api-server' % self
       return True, None

   @retry(delay=5, tries=6)
   def _verify_not_in_api_server (self):
       if self._vnc.get_service_instance(self.uuid):
           msg = '%s not removed from api-server' % self
           self.logger.debug(msg)
           return False, msg
       self.logger.debug('%s removed from api-server' % self)
       return True, None

   @retry(delay=2, tries=10)
   def _verify_st (self):
       project, si = self.fq_name[1:]
       self.cs_si = self.api_inspect.get_cs_si(project=project, si=si,
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
