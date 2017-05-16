import copy
from tcutils.util import is_v6

def _extract_subnet_from_network_ipam (data):
   ip = data['subnet']
   subnet = {}
   subnet['cidr'] = ip['ip_prefix'] + '/' + str(ip['ip_prefix_len'])
   subnet['ip_version'] = 6 if is_v6(subnet['cidr']) else 4
   if 'dns_nameservers' in data:
       subnet['dns_nameservers'] = data['dns_nameservers']
   if 'enable_dhcp' in data:
       subnet['enable_dhcp'] = data['enable_dhcp']
   if 'default_gateway' in data:
       subnet['gateway_ip'] = data['default_gateway']
   if 'allocation_pools' in data:
       lst = []
       for pool in data['allocation_pools']:
           lst.append({'allocation_pool_start': pool['start'],
                       'allocation_pool_end': pool['end']})
       subnet['allocation_pools'] = lst
   if 'host_routes' in data:
       lst = []
       for hr in data['host_routes']['route']:
           lst.append({'route_destination': hr['prefix'],
                       'route_nexthop': hr['next_hop']})
       subnet['host_routes'] = lst
   return subnet

def _extract_attrs_for_create (kwargs):
   net_args = {
       'name': kwargs['name'],
   }
   # TODO: How to pass contrail-specific attrs
   # TODO: 'network_ipam_refs_data_host_routes' is ignored for now since
   #       host routes are also present under
   #       'network_ipam_refs_subnets_host_routes'

   if 'port_security_enabled' in kwargs:
       net_args['port_security_enabled'] = kwargs['port_security_enabled']
   if 'is_shared' in kwargs:
       net_args['shared'] = kwargs['is_shared']
   if 'network_policy_refs' in kwargs:
       net_args['contrail:policys'] = [ref['to'] for ref in \
               kwargs['network_policy_refs']]
       
   subnets = []
   for ipam in kwargs['network_ipam_refs']:
       to = ipam['to']
       for subnet in ipam['attr']['ipam_subnets']:
           subnets.append(_extract_subnet_from_network_ipam(subnet))
   return net_args, subnets

def _extract_attrs_for_update (kwargs, network, subnets):
   # TODO: How to pass contrail-specific attrs
   # TODO: 'network_ipam_refs_data_host_routes' is ignored for now since
   #       host routes are also present under
   #       'network_ipam_refs_subnets_host_routes'
   net_args = {}
   if 'port_security_enabled' in kwargs:
       net_args['port_security_enabled'] = kwargs['port_security_enabled']
   if 'is_shared' in kwargs:
       net_args['shared'] = kwargs['is_shared']
   if 'network_policy_refs' in kwargs:
       net_args['contrail:policys'] = [ref['to'] for ref in \
               kwargs['network_policy_refs']]

   to_add = []
   to_del = []
   to_upd = []
   tracked_cidrs = []
   for subnet in subnets:
       found = False
       for ipam in kwargs['network_ipam_refs']:
           to = ipam['to']
           if found:
               break
           for data in ipam['attr']['ipam_subnets']:
               cidr = data['subnet']['ip_prefix'] + '/' + \
                           str(data['subnet']['ip_prefix_len'])
               if subnet['cidr'] == cidr:
                   new_args = _extract_subnet_from_network_ipam(data)
                   new_args['id'] = subnet['id']
                   del new_args['cidr']
                   del new_args['ip_version']
                   to_upd.append(new_args)
                   tracked_cidrs.append(cidr)
                   found = True
                   break
       if not found:
           to_del.append(subnet['id'])

   for ipam in kwargs['network_ipam_refs']:
       to = ipam['to']
       for data in ipam['attr']['ipam_subnets']:
           cidr = data['subnet']['ip_prefix'] + '/' + \
                       str(data['subnet']['ip_prefix_len'])
           if cidr in tracked_cidrs:
               continue
           to_add.append(_extract_subnet_from_network_ipam(data))

   return net_args, to_add, to_del, to_upd

class OsVnMixin:

   ''' Mixin class implements CRUD methods for Virtual-Network
   '''

   def create_virtual_network (self, **kwargs):
       args = copy.deepcopy(kwargs)
       vn_args = None
       add_subnets = None
       if args['type'] == 'openstack':
           del args['type']
           vn_args = args
           if 'value_specs' in vn_args:
               for k, v in vn_args['value_specs'].items():
                   vn_args[k] = v
               del vn_args['value_specs']
       else:
           vn_args, add_subnets = _extract_attrs_for_create(kwargs)
       net = self._qh.create_network({'network': vn_args})
       if add_subnets:
           for subnet in add_subnets:
               subnet['network_id'] = net['network']['id']
               self.create_subnet(type='openstack', **subnet)
       return net['network']['id']

   def get_virtual_network (self, uuid):
       return self._qh.show_network(uuid)

   def delete_virtual_network (self, obj=None, uuid=None):
       uuid = uuid or obj['network']['id']
       #TODO: what happends to subnets associated with this VN
       return self._qh.delete_network(uuid)

   def update_virtual_network (self, obj=None, uuid=None, **kwargs):
       args = copy.deepcopy(kwargs)
       uuid = uuid or obj['network']['id']
       vn_args = None
       add_subnets = None
       del_subnets = None
       if args['type'] == 'openstack':
           del args['type']
           vn_args = args
       else:
           cur_subnets = []
           for subnet_id in self._qh.show_network(uuid,
                   fields='subnets')['network']['subnets']:
               cur_subnets.append(self._qh.show_subnet(
                   subnet_id)['subnet'])
           vn_args, add_subnets, del_subnets, upd_subnets = \
                   _extract_attrs_for_update(args, obj['network'],
                           cur_subnets)
           if vn_args:
               self._qh.update_network(uuid, {'network':vn_args})
       for subnet in add_subnets:
           subnet['network_id'] = uuid
           self.create_subnet(type='openstack', **subnet)
       for subnet in del_subnets:
           self.delete_subnet(uuid=subnet)
       for subnet in upd_subnets:
           subnet_id = subnet['id']
           del subnet['id']
           self.update_subnet(subnet_id, type='openstack', **subnet)
