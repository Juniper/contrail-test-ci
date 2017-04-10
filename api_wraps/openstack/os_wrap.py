#TODO: This module replaces 
# fixtures/openstack.py
# fixtures/nova.py
# fixtures/quantum.py
# common/openstack_libs.py
import os
import ast

try:
   from neutronclient.neutron import client as neuc
   from novaclient import client as novac
   from novaclient import exceptions as novaException

   class OpenstackWrap:

       ''' Wrapper class for Openstack Apis.

           This class wraps/abstracts all openstack apis, nova, neutron, etc.
           Any and all openstack libs calls must be added in this class.
           Provides create, read, update and delete methods for resources.
           Note: For resources defined in contrail-schema, the create & update
           methods expect resource desc (kwargs) to be in-sync with structure
           defined in contrail-schema (i.e, contrailv2 heat template).
       '''

       def __init__ (self, username, password, project_id, project_name,
                     auth_url, endpoint_type, region_name, logger):
           self.logger = logger
           prj = project_id.replace('-', '')
           insecure = bool(os.getenv('OS_INSECURE', True))
           self._qh = neuc.Client('2.0',
                                username=username,
                                password=password,
                                project_id=prj,
                                auth_url=auth_url,
                                region_name=region_name,
                                insecure=insecure)
           self._nh = novac.Client('2',
                                username=username,
                                api_key=password,
                                project_id=project_name,
                                auth_url=auth_url,
                                endpoint_type=endpoint_type,
                                region_name=region_name,
                                insecure=insecure)

       @property
       def quantum_handle (self):
           return self._qh

       @property
       def nova_handle (self):
           return self._nh

       def is_supported_type (self, arg):
           return arg in ['ContrailV2', 'Openstack']

       def get_zones (self):
           try:
               zones = self._nh.availability_zones.list()
               return filter(lambda x: x.zoneName != 'internal', zones)
           except novaException.Forbidden:
               return None

       def get_hosts (self, zone=None):
           computes = self._get_nova_services(binary='nova-compute')
           if zone:
               computes = filter(lambda x: x.zone == zone.zoneName, computes)
           return computes

       def _get_nova_services (self, **kwargs):
           try:
               svcs = self._nh.services.list(**kwargs)
               svcs = filter(lambda x: x.state != 'down' and \
                                       x.status != 'disabled', svcs)
               return svcs
           except novaException.Forbidden:
               return None

       def get_hypervisor (self, **kwargs):
           if kwargs:
               try:
                   return self._nh.hypervisors.find(**kwargs)
               except novaException.NotFound:
                   return None
           else:
               return self._nh.hypervisor.list()

       def get_flavor (self, name):
           try:
               return self._nh.flavors.find(name=name)
           except novaException.NotFound:
               return None

       def create_flavor (self, name, vcpus, ram, disk):
           self._nh.flavors.create(name=name, vcpus=vcpus, ram=ram, disk=disk)
           flavor = self.get_flavor(name)
           return flavor

       def get_image (self, name_or_id):
           try:
               return self._nh.images.get(name_or_id)
           except novaException.NotFound:
               try:
                   return self._nh.images.find(name=name_or_id)
               except novaException.NotFound:
                   return None

       def create_virtual_machine (self, **kwargs):
           lst = []
           for nic in kwargs['networks']:
               if nic.keys()[0] == 'port':
                   lst.append({'port-id': nic.values()[0]})
               else:
                   lst.append({'net-id': nic.values()[0]})
           kwargs['nics'] = lst
           del kwargs['networks']
           obj = self._nh.servers.create(**kwargs)
           return obj.id

       def get_virtual_machine (self, uuid):
           ret = self._nh.servers.list(search_opts={'uuid':uuid})
           if ret:
               return ret[0]
           return None

       def delete_virtual_machine (self, obj=None, uuid=None):
           uuid = uuid or obj.id
           return self._nh.servers.delete(uuid)

       #TODO get/create/delete/update virtual_machine
       #TODO get/create/delete/update virtual_machine_interface
       #TODO get/create/delete/update virtual_network
       #TODO get/create/delete/update subnet
       #TODO get/create/delete/update security_group
       #TODO get/create/delete/update security_group_rule
       #TODO get/create/delete/update floating_ip
       #TODO get/create/delete/update network_policy
       #TODO get/create/delete/update quota
       #TODO get/create/delete/update router
       #TODO get/create/delete/update loadbalancer
       #TODO get/create/delete/update loadbalancer_listener
       #TODO get/create/delete/update loadbalancer_pool
       #TODO get/create/delete/update loadbalancer_member
       #TODO get/create/delete/update health_monitor
       #TODO get/create/delete/update virtual_ip
       #TODO get/create/delete/update lbaas_pool
       #TODO get/create/delete/update lbaas_member
       #TODO get/create/delete/update lbaas_healthmonitor

except ImportError:
   pass
