from contrail_fixtures import ContrailFixture
from tcutils.util import retry
from vnc_api.vnc_api import InterfaceRouteTable

class InterfaceRouteTableFixture_v2 (ContrailFixture):

   vnc_class = InterfaceRouteTable

   def __init__ (self, connections, uuid=None, params=None, fixs=None):
       super(InterfaceRouteTableFixture_v2, self).__init__(
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
       obj = self._vnc.get_interface_route_table(self.uuid)
       return obj != None, obj

   def _read (self):
       ret, obj = self._read_vnc_obj()
       if ret:
           self._vnc_obj = obj
       self._obj = self._vnc_obj

   def _create (self):
       self.logger.info('Creating %s' % self)
       with self._api_ctx:
           self.uuid = self._ctrl.create_interface_route_table(
               **self._args)

   def _delete (self):
       self.logger.info('Deleting %s' % self)
       with self._api_ctx:
           self._ctrl.delete_interface_route_table(
               obj=self._obj, uuid=self.uuid)

   def _update (self):
       self.logger.info('Updating %s' % self)
       with self._api_ctx:
           self._ctrl.update_interface_route_table(
               obj=self._obj, uuid=self.uuid, **self.args)

   def verify_on_setup (self):
       #TODO: add verification code
       pass

   def verify_on_cleanup (self):
       #TODO: add verification code
       pass

from tcutils.util import get_random_name

class InterfaceRouteTableFixture (InterfaceRouteTableFixture_v2):

   """ Fixture for backward compatiblity """

   def __init__ (self, connections, **kwargs):
       domain = connections.domain_name
       prj = kwargs.get('project_name') or connections.project_name
       prj_fqn = domain + ':' + prj
       name = kwargs.get('name')

       if name:
           uid = self._check_if_present(connections, name, [domain, prj])
           if uid:
               super(InterfaceRouteTableFixture, self).__init__(connections=connections,
                                           uuid=uid)
               return
       else:
           name = get_random_name('intf-rtb')

       self._params = {
           'type': 'OS::ContrailV2::InterfaceRouteTable',
           'name': kwargs['name'],
       }
       lst = []
       for prf in kwargs['prefixes']:
           lst.append({'prefix': prf})
       if lst:
           self._params['interface_route_tables_routes'] = {'route': lst}
       super(InterfaceRouteTableFixture, self).__init__(
               connections=connections, params=self._params)

   def _check_if_present (self, conn, name, prj_fqn):
       uid = prj_fqn + [name]
       obj = conn.get_orch_ctrl().get_api('vnc').get_interface_route_table(uid)
       if not obj:
           return None
       return uid

   def add_routes (self, prefixes):
       routes = self.vnc_obj.get_interface_route_table_routes()
       route = routes.get_route()
       for prf in prefixes:
           route.append(RouteType(prefix=prf))
       self.vnc_obj.set_interface_route_table_routes(routes)
       self.vnc_api.interface_route_table_update(self.vnc_obj)
       self.update()

   def del_routes (self, prefixes):
       routes = self.vnc_obj.get_interface_route_table_routes()
       route = routes.get_route()
       for prf in prefixes:
           for r in route:
               if r.prefix == prf:
                   route.remove(r)
                   break

   def setUp (self):
       super(InterfaceRouteTableFixture, self).setUp()
       self.vnc_api = self._vnc._vnc # direct handle to vnc library
