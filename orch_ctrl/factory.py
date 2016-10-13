def _setup_1 (conn):
   from os_ctrl import OpenstackControl
   cfgm_ip = conn.inputs.api_server_ip or \
             conn.inputs.contrail_external_vip or conn.inputs.cfgm_ip
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
           'logger': conn.logger,
           'inputs': conn.inputs}
   return OpenstackControl(**args)

_DEPLOYMENTS = {
   'openstack' : _setup_1, # single openstack & contrail cluster
}

def create_orchestration_control (deployment, connections):
    assert deployment in _DEPLOYMENTS, 'Unsupported deployment %s' % deployment
    return _DEPLOYMENTS[deployment](connections)
