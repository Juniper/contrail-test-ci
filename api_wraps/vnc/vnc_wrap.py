#TODO: This module replaces fixtures/contrailapi.py
import functools
from vnc_api.vnc_api import *
from tcutils.util import get_random_name, retry

_RESOURCES = {
   'access_control_list':  AccessControlList,
   'alarm':  Alarm,
   'alias_ip':  AliasIp,
   'alias_ip_pool':  AliasIpPool,
   'analytics_node':  AnalyticsNode,
   'api_access_list':  ApiAccessList,
   'bgp_as_a_service_read':  BgpAsAService,
   'bgp_router':  BgpRouter,
   'config_node':  ConfigNode,
   'config_root':  ConfigRoot,
   'customer_attachment':  CustomerAttachment,
   'database_node':  DatabaseNode,
   'discovery_service_assignment':  DiscoveryServiceAssignment,
   'domain':  Domain,
   'dsa_rule':  DsaRule,
   'floating_ip':  FloatingIp,
   'floating_ip_pool':  FloatingIpPool,
   'forwarding_class':  ForwardingClass,
   'global_qos_config':  GlobalQosConfig,
   'global_system_config':  GlobalSystemConfig,
   'global_vrouter_config':  GlobalVrouterConfig,
   'instance_ip':  InstanceIp,
   'interface_route_table':  InterfaceRouteTable,
   'loadbalancer_healthmonitor':  LoadbalancerHealthmonitor,
   'loadbalancer':  Loadbalancer,
   'loadbalancer_listener':  LoadbalancerListener,
   'loadbalancer_member':  LoadbalancerMember,
   'loadbalancer_pool':  LoadbalancerPool,
   'logical_interface':  LogicalInterface,
   'logical_router':  LogicalRouter,
   'namespace':  Namespace,
   'network_ipam':  NetworkIpam,
   'network_policy':  NetworkPolicy,
   'physical_interface':  PhysicalInterface,
   'physical_router':  PhysicalRouter,
   'port_tuple':  PortTuple,
   'project' :  Project,
   'provider_attachment' :  ProviderAttachment,
   'qos_config' :  QosConfig,
   'qos_queue' :  QosQueue,
   'route_aggregate' :  RouteAggregate,
   'route_table' :  RouteTable,
   'route_target' :  RouteTarget,
   'routing_instance' :  RoutingInstance,
   'routing_policy' :  RoutingPolicy,
   'security_group' :  SecurityGroup,
   'service_appliance' :  ServiceAppliance,
   'service_appliance_set' :  ServiceApplianceSet,
   'service_health_check' :  ServiceHealthCheck,
   'service_instance':  ServiceInstance,
   'service_template':  ServiceTemplate,
   'subnet':  Subnet,
   'virtual_DNS':  VirtualDns,
   'virtual_DNS_record':  VirtualDnsRecord,
   'virtual_ip':  VirtualIp,
   'virtual_machine':  VirtualMachine,
   'virtual_machine_interface':  VirtualMachineInterface,
   'virtual_network':  VirtualNetwork,
   'virtual_router':  VirtualRouter,
}

class VncWrap:

   ''' Wrapper class for VNC Api

       Provides create, read, update, delete methods for contrail resources.
       Methods create & update, expect the resource desc (kwargs) to be
       consistent with contrail-schema (i.e, as per contrailv2 heat templates)
   '''

   def __init__ (self, username, password, project_name,
                 server_ip, server_port, auth_server_ip, project_id):
       self._vnc = VncApi(username=username,
                          password=password,
                          tenant_name=project_name,
                          api_server_host=server_ip,
                          api_server_port=server_port,
                          auth_host=auth_server_ip)
       self._project = self._get('project', project_id)
       self._export_fns()

   @retry(delay=1, tries=10)
   def _get_id (self, resource, fqn):
       try:
           return True, self._vnc.fq_name_to_id(resource, fqn)
       except NoIdError:
           return False, None

   def fqn_to_id (self, resource, fqn):
       return self._get_id(resource, fqn)[1]

   @retry(delay=1, tries=10)
   def _get_fqn (self, rid):
       try:
           return True, self._vnc.id_to_fq_name(rid)
       except NoIdError:
           return False, None

   def id_to_fqn (self, rid):
       return self._get_fqn(rid)[1]

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

   def _delete (self, resource, obj=None, uuid=None):
       fn = self._get_vnc_fn(resource, 'delete')
       uuid = uuid or obj.uuid
       try:
           fn(id=uuid)
       except NoIdError:
           pass

   def _set_parent_type (self, resource, kwargs):
       for t in _RESOURCES[resource].parent_types:
           if t.replace('-', '_') in kwargs:
               kwargs['parent_type'] = t
               return
       if 'project' in _RESOURCES[resource].parent_types:
           kwargs['parent_type'] = 'project'
           return
       kwargs['parent_type'] = None

   def _set_fq_name (self, resource, kwargs):
       try:
           name = kwargs['name']
       except KeyError:
           name = get_random_name()
       if kwargs['parent_type']:
           parent_type = kwargs['parent_type'].replace('-', '_')
           try:
               kwargs['fq_name'] = kwargs[parent_type].split(':') + [name]
           except KeyError:
               if parent_type == 'project':
                   kwargs['fq_name'] = self._project.fq_name + [name]
               else:
                   assert False, '%s not specified' % parent_type
       else:
           kwargs['fq_name'] = [name]

   def _create (self, resource, **kwargs):
       fn = self._get_vnc_fn(resource, 'create')
       self._set_parent_type(resource, kwargs)
       if not kwargs.get('fq_name', None):
           self._set_fq_name(resource, kwargs)
       if not kwargs.get('uuid', None):
           kwargs['uuid'] = None
       obj = _RESOURCES[resource].from_dict(**kwargs)
       obj._pending_field_updates.update(
               _RESOURCES[resource].ref_fields)
       return fn(obj)

   def _update (self, resource, obj=None, uuid=None, **kwargs):
       fn = self._get_vnc_fn(resource, 'update')
       obj = obj or self._get(resource, uuid)       
       if not kwargs:
           return fn(obj)
       self._set_parent_type(resource, kwargs)
       kwargs['fq_name'] = obj.fq_name
       kwargs['uuid'] = obj.uuid
       obj_upd = _RESOURCES[resource].from_dict(**kwargs)
       obj_upd._pending_field_updates.update(
                   _RESOURCES[resource].ref_fields)
       return fn(obj_upd)

   def _export_fns (self):
       for r in _RESOURCES:
           setattr(self, 'get_%s' % r, functools.partial(self._get, r))
           setattr(self, 'create_%s' % r, functools.partial(self._create, r))
           setattr(self, 'update_%s' % r, functools.partial(self._update, r))
           setattr(self, 'delete_%s' % r, functools.partial(self._delete, r))

   def is_supported_type (self, arg):
       return arg in ['ContrailV2']

