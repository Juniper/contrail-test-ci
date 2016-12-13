import os
from common import RoundRobin, RoundRobinZoneRestricted

def _setup_1 (conn):
   from os_setup import OpenstackControl
   cfgm_ip = conn.inputs.api_server_ip or \
             conn.inputs.contrail_external_vip or conn.inputs.cfgm_ip

   conn.logger.debug('Intializing OpenstackControl')
   hyper = os.getenv('HYPERVISOR_TYPE')
   if hyper:
       zone = 'nova'
       if hyper == 'docker':
           zone = 'nova/docker'
       conn.logger.debug('load-balance-algo: hypervisor:%s, zone:%s' % (hyper,
                         zone))
       lb_class = RoundRobinZoneRestricted(zone)
   else:
       conn.logger.debug('load-balance-algo: default')
       lb_class = RoundRobin()

   args = {'username':conn.username,
           'password':conn.password,
           'auth_ip':conn.inputs.auth_ip,
           'auth_url':conn.inputs.auth_url,
           'project_name': conn.project_name,
           'project_id': conn.get_project_id(),
           'openstack_ip': conn.inputs.openstack_ip,
           'endpoint': conn.inputs.endpoint_type,
           'region': conn.inputs.region_name,
           'api_server_ip': cfgm_ip,
           'api_server_port': conn.inputs.api_server_port,
           'lb_class': lb_class,
           'inputs': conn.inputs,
           'logger': conn.logger}
   return OpenstackControl(**args)

_DEPLOYMENTS = {
   'openstack' : _setup_1, # single openstack cluster
   #TODO 'vcenter' : _setup_2, # single vcenter cluster
   #TODO 'openstack+vcenter' : _setup_3, # openstack with vcenter as compute
   #TODO 'openstack+vcenter-gateway' : _setup_4, # openstack with vcenter gateway
}

def create_orchestration_control (deployment, connections):
    assert deployment in _DEPLOYMENTS, 'Unsupported deployment %s' % deployment
    return _DEPLOYMENTS[deployment](connections)
