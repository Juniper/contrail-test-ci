import copy

class OsSubnetMixin:

   ''' Mixin class implements CRUD methods for Subnet
   '''

   def create_subnet (self, **kwargs):
       args = copy.deepcopy(kwargs)
       if args['type'] == 'openstack':
           del args['type']
       else:
           raise Exception("Unimplemented")
       subnet = self._qh.create_subnet({'subnet': args})
       return subnet['subnet']['id']

   def get_subnet (self, uuid):
       return self._qh.show_subnet(uuid)

   def delete_subnet (self, obj=None, uuid=None):
       uuid = uuid or obj['subnet']['id']
       return self._qh.delete_subnet(uuid)

   def update_subnet (self, obj=None, uuid=None, **kwargs):
       args = copy.deepcopy(kwargs)
       uuid = uuid or obj['subnet']['id']
       if args['type'] == 'openstack':
           del args['type']
       else:
           raise Exception("Unimplemented")
       self._qh.update_subnet(uuid, {'subnet':args})
