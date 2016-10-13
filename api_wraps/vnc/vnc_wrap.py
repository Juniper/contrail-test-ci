import functools
from vnc_api.vnc_api import *
from tcutils.util import get_random_name

_RESOURCES = {
   'virtual_network': {
       'type': VirtualNetwork,
       'parent_type': 'project',
       'refs': ['network_policy_refs', 'network_ipam_refs',
                'route_table_refs', 'qos_config_refs']
   },
   'network_policy': {
       'type': NetworkPolicy,
       'parent_type': 'project',
       'refs': []
   },
   'service_instance': {
       'type': ServiceInstance,
       'parent_type': 'project',
       'refs': ['service_template_refs', 'instance_ip_refs']
   },
   'service_template': {
       'type': ServiceTemplate,
       'parent_type': 'domain',
       'refs': ['service_appliance_set_refs']
   },
   'port_tuple': {
       'type': PortTuple,
       'parent_type': 'service-instance',
       'refs': []
   },
   'instance_ip': {
       'type': InstanceIp,
       'parent_type': None,
       'refs': ['physical_router_refs', 'virtual_machine_interface_refs',
                'virtual_network_refs']
   },
   'virtual_machine_interface': {
       'type': VirtualMachineInterface,
       'parent_type': 'project',
       'refs': ['service_health_check_refs',
                'routing_instance_refs', 'security_group_refs',
                'physical_interface_refs', 'port_tuple_refs',
                'interface_route_table_refs',
                'virtual_machine_inteface_refs', 'virtual_network_refs',
                'virtual_machine_refs', 'qos_config_refs']
   },
   'virtual_machine': {
       'type': VirtualMachine,
       'parent_type': 'project',
       'refs': ['service_health_check_refs', 'routing_instance_refs',
                'security_group_refs', 'physical_interface_refs',
                'port_tuple_refs', 'interface_route_table_refs',
                'virtual_machine_interface_refs', 'virtual_network_refs',
                'virtual_machine_refs', 'qos_config_refs']
   },
   #TODO: add entries for other resources
}

class VncWrap:

   def __init__ (self, **kwargs):
       self._vnc = VncApi(username=kwargs['username'],
                          password=kwargs['password'],
                          tenant_name=kwargs['project_name'],
                          api_server_host=kwargs['server_ip'],
                          api_server_port=kwargs['server_port'],
                          auth_host=kwargs['auth_server_ip'])
       self._project = self._get('project', kwargs['project_id'])
       self._export_fns()

   def _get_vnc_fn (self, resource, ops):
       fn_name = resource + '_' + ops
       fn = getattr(self._vnc, fn_name, None)
       assert fn, "No %s in VNC api" % fn_name
       return fn

   def _get (self, resource, fq_name_or_id):
       fn = self._get_vnc_fn(resource, 'read')
       try:
           return fn(fq_name=fq_name_or_id)
       except NoIdError:
           try:
               return fn(id=fq_name_or_id)
           except NoIdError:
               return None

   def _delete (self, resource, obj):
       fn = self._get_vnc_fn(resource, 'delete')
       try:
           fn(id=obj.uuid)
       except NoIdError:
           pass

   def _make_fq_name (self, resource, kwargs):
       try:
           name = kwargs['name']
       except KeyError:
           name = get_random_name()
       parent_type = _RESOURCES[resource]['parent_type']
       if parent_type is None:
           return [name]
       elif parent_type == 'project':
           return self._project.fq_name + [name]
       elif parent_type in ['domain', 'service-instance']:
           parent_type = parent_type.replace('-', '_')
           return kwargs[parent_type].split(':') + [name]
       else:
           assert False, 'Unknown parent_type (%s) for %s' % (parent_type,
                                                              resource)

   def _create (self, resource, **kwargs):
       fn = self._get_vnc_fn(resource, 'create')
       if not kwargs.get('fq_name', None):
           kwargs['fq_name'] = self._make_fq_name(resource, kwargs)
       if not kwargs.get('uuid', None):
           kwargs['uuid'] = None
       kwargs['parent_type'] = _RESOURCES[resource]['parent_type']
       obj = _RESOURCES[resource]['type'].from_dict(**kwargs)
       obj._pending_field_updates.update(_RESOURCES[resource]['refs'])
       return fn(obj)

   def _update (self, resource, obj, **kwargs):
       fn = self._get_vnc_fn(resource, 'update')
       kwargs['fq_name'] = obj.fq_name
       kwargs['uuid'] = obj.uuid
       kwargs['parent_type'] = _RESOURCES[resource]['parent_type']
       obj_upd = _RESOURCES[resource]['type'].from_dict(**kwargs)
       obj_upd._pending_field_updates.update(_RESOURCES[resource]['refs'])
       return fn(obj_upd)

   def _export_fns (self):
       for r in _RESOURCES:
           setattr(self, 'get_%s' % r, functools.partial(self._get, r))
           setattr(self, 'create_%s' % r, functools.partial(self._create, r))
           setattr(self, 'update_%s' % r, functools.partial(self._update, r))
           setattr(self, 'delete_%s' % r, functools.partial(self._delete, r))
