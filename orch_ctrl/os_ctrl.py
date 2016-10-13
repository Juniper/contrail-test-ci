class OpenstackControl (object):

   ''' Single openstack-contrail cluster setup
   '''

   def __init__ (self, **kwargs):
       self._apis = {}
       self._args = kwargs
       self._select = 'orch' # api route selector
       self._supported = ['orch', 'heat', 'vnc', 'openstack']
       self._hijack = { # overides user selected api route
           'create_virtual_machine': 'openstack',
           'get_virtual_machine': 'openstack',
           'delete_virtual_machine': 'openstack',
       }

   def __getattr__ (self, fn):

       ''' Procedure to route api calls
           Attempt user selected api-route, if method not found
           fallback to vnc.
       '''

       if fn == '__repr__':
           return self
       if fn in self._hijack:
          return getattr(self.get_api(self._hijack[fn]), fn)
       try:
           api = self._apis[self._select]
       except KeyError: 
           api = self.get_api(self._select)
       try:
           return getattr(api, fn)
       except AttributeError:
           return getattr(self.get_api('vnc'), fn)

   @property
   def select_api (self):
       return self._select

   @select_api.setter
   def select_api (self, api):
       assert api in self._supported, 'Unsupported api %s' % api
       self._select = api

   def get_api (self, api, args=None):
       assert api in self._supported, 'Unsupported api %s' % api
       try:
           return self._apis[api]
       except:
           fn = getattr(self, '_get_' + api + '_api')
           args = args or self._args
           self._apis[api] = fn(args)
           return self._apis[api]

   def _get_heat_api (self, args):
       from api_wraps.heat.heat_wrap import HeatWrap
       return HeatWrap(username=args['username'],
                       password=args['password'],
                       project_name=args['project_name'],
                       server_ip=args['openstack_ip'],
                       auth_url=args['auth_url'],
                       logger=args['logger'])

   def _get_vnc_api (self, args):
       from api_wraps.vnc.vnc_wrap import VncWrap
       return VncWrap(username=args['username'],
                      password=args['password'],
                      project_name=args['project_name'],
                      project_id=args['project_id'],
                      server_ip=args['api_server_ip'],
                      server_port=args['api_server_port'],
                      auth_server_ip=args['auth_ip'],
                      logger=args['logger'])

   def _get_openstack_api (self, args):
       from api_wraps.openstack.os_wrap import OpenstackWrap
       return OpenstackWrap(username=args['username'],
                            password=args['password'],
                            project_id=args['project_id'],
                            project_name=args['project_name'],
                            auth_url=args['auth_url'],
                            endpoint_type=args['endpoint'],
                            region_name=args['region'],
                            logger=args['logger'])

   def _get_orch_api (self, args):
       return self.get_api('openstack', args)
