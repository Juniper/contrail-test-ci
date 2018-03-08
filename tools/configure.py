import argparse
import ConfigParser
import sys
import string
import json
import os
import platform
from fabric.api import env, run, local, lcd
from fabric.context_managers import settings, hide
sys.path.append(os.path.join(os.path.dirname(__file__), os.pardir))
from common import log_orig as contrail_logging
from fabric.contrib.files import exists
from cfgm_common import utils
from tcutils.util import istrue

def detect_ostype():
    return platform.dist()[0].lower()

def get_address_family():
    address_family = os.getenv('AF', 'dual')
    # ToDo: CI to execute 'v4' testcases alone for now
    if os.getenv('GUESTVM_IMAGE', None):
        address_family = 'v4'
    return address_family

def configure_test_env(contrail_fab_path='/opt/contrail/utils', test_dir='/contrail-test'):
    """
    Configure test environment by creating sanity_params.ini and sanity_testbed.json files
    """
    print "Configuring test environment"
    sys.path.insert(0, contrail_fab_path)
    from fabfile.testbeds import testbed
    from fabfile.utils.host import get_openstack_internal_vip, \
        get_control_host_string, get_authserver_ip, get_admin_tenant_name, \
        get_authserver_port, get_env_passwords, get_authserver_credentials, \
        get_vcenter_ip, get_vcenter_port, get_vcenter_username, \
        get_vcenter_password, get_vcenter_datacenter, get_vcenter_compute, \
        get_authserver_protocol, get_region_name, get_contrail_internal_vip, \
        get_openstack_external_vip, get_contrail_external_vip, \
        get_apiserver_protocol, get_apiserver_certfile, get_apiserver_keyfile, \
        get_apiserver_cafile, get_keystone_insecure_flag, \
        get_apiserver_insecure_flag, get_keystone_certfile, get_keystone_keyfile, \
        get_keystone_cafile, get_keystone_version, get_discovery_protocol
    from fabfile.utils.multitenancy import get_mt_enable
    from fabfile.utils.interface import get_data_ip
    from fabfile.tasks.install import update_config_option, update_js_config
    from fabfile.utils.fabos import get_as_sudo
    logger = contrail_logging.getLogger(__name__)

    def validate_and_copy_file(filename, source_host):
        with settings(host_string='%s' %(source_host),
                      warn_only=True, abort_on_prompts=False):
            if exists(filename):
                filedir = os.path.dirname(filename)
                if not os.path.exists(filedir):
                    os.makedirs(filedir)
                get_as_sudo(filename, filename)
                return filename
            return ""

    cfgm_host = env.roledefs['cfgm'][0]

    auth_protocol = get_authserver_protocol()
    auth_server_ip = get_authserver_ip()
    auth_server_port = get_authserver_port()
    api_auth_protocol = get_apiserver_protocol()
    discovery_auth_protocol = get_discovery_protocol()

    if api_auth_protocol == 'https':
        api_certfile = validate_and_copy_file(get_apiserver_certfile(), cfgm_host)
        api_keyfile = validate_and_copy_file(get_apiserver_keyfile(), cfgm_host)
        api_cafile = validate_and_copy_file(get_apiserver_cafile(), cfgm_host)
        api_insecure_flag = get_apiserver_insecure_flag()
    else:
       api_certfile = ""
       api_keyfile = ""
       api_cafile = ""
       api_insecure_flag = True

    cert_dir = os.path.dirname(api_certfile)
    if auth_protocol == 'https':
        keystone_cafile = validate_and_copy_file(cert_dir + '/' +\
                          os.path.basename(get_keystone_cafile()), cfgm_host)
        keystone_certfile = validate_and_copy_file(cert_dir + '/' +\
                          os.path.basename(get_keystone_certfile()), cfgm_host)
        keystone_keyfile = keystone_certfile
        keystone_insecure_flag = istrue(os.getenv('OS_INSECURE', \
                                 get_keystone_insecure_flag()))
    else:
        keystone_certfile = ""
        keystone_keyfile = ""
        keystone_cafile = ""
        keystone_insecure_flag = True

    with settings(warn_only=True), hide('everything'):
        with lcd(contrail_fab_path):
            if local('git branch').succeeded:
                fab_revision = local('git log --format="%H" -n 1', capture=True)
            else:
                with settings(host_string=cfgm_host), hide('everything'):
                   fab_revision = run('cat /opt/contrail/contrail_packages/VERSION')
        with lcd(test_dir):
            if local('git branch').succeeded:
                revision = local('git log --format="%H" -n 1', capture=True)
            else:
                with settings(host_string=cfgm_host), hide('everything'):
                    revision = run('cat /opt/contrail/contrail_packages/VERSION')

    sanity_testbed_dict = {
        'hosts': [],
        'vgw': [],
        'esxi_vms':[],
        'vcenter_servers':[],
        'hosts_ipmi': [],
        'tor':[],
        'sriov':[],
        'dpdk':[],
        'ns_agilio_vrouter':[],
    }

    sample_ini_file = test_dir + '/' + 'sanity_params.ini.sample'
    with open(sample_ini_file, 'r') as fd_sample_ini:
       contents_sample_ini = fd_sample_ini.read()
    sanity_ini_templ = string.Template(contents_sample_ini)

    if env.get('orchestrator', 'openstack') != 'vcenter':
        with settings(host_string = env.roledefs['openstack'][0]), hide('everything'):
            openstack_host_name = run("hostname")

    with settings(host_string = env.roledefs['cfgm'][0]), hide('everything'):
        cfgm_host_name = run("hostname")

    control_host_names = []
    for control_host in env.roledefs['control']:
        with settings(host_string = control_host), hide('everything'):
            host_name = run("hostname")
            control_host_names.append(host_name)

    cassandra_host_names = []
    if 'database' in env.roledefs.keys():
        for cassandra_host in env.roledefs['database']:
            with settings(host_string = cassandra_host), hide('everything'):
                host_name = run("hostname")
                cassandra_host_names.append(host_name)
    keystone_version = get_keystone_version()
    internal_vip = get_openstack_internal_vip()
    external_vip = get_openstack_external_vip()
    contrail_internal_vip = get_contrail_internal_vip()
    contrail_external_vip = get_contrail_external_vip()
    multi_role_test = False
    for host_string in env.roledefs['all']:
        if host_string in env.roledefs.get('test',[]):
            for role in env.roledefs.iterkeys():
                if role in ['test','all']:
                    continue
                if host_string in env.roledefs.get(role,[]):
                    multi_role_test=True
                    break
            if not multi_role_test:
                continue
        host_ip = host_string.split('@')[1]
        with settings(host_string = host_string), hide('everything'):
            try:
                host_name = run("hostname")
            except:
                logger.warn('Unable to login to %s'%host_ip)
                continue
        host_dict = {}

        host_dict['ip'] = host_ip
        host_dict['data-ip']= get_data_ip(host_string)[0]
        if host_dict['data-ip'] == host_string.split('@')[1]:
            host_dict['data-ip'] = get_data_ip(host_string)[0]
        host_dict['control-ip']= get_control_host_string(host_string).split('@')[1]

        host_dict['name'] = host_name
        host_dict['username'] = host_string.split('@')[0]
        host_dict['password'] =get_env_passwords(host_string)
        host_dict['roles'] = []
       
        if env.get('qos', {}): 
            if host_string in env.qos.keys():
                role_dict = env.qos[host_string]
                host_dict['qos'] = role_dict
        if env.get('qos_niantic', {}):    
            if host_string in env.qos_niantic.keys():
                role_dict = env.qos_niantic[host_string]
                host_dict['qos_niantic'] = role_dict

        if host_string in env.roledefs['openstack']:
            role_dict = {'type': 'openstack', 'params': {'cfgm': cfgm_host_name}}
            host_dict['roles'].append(role_dict)

        if host_string in env.roledefs['cfgm']:
            role_dict = {'type': 'cfgm', 'params': {'collector': host_name, 'cassandra': ' '.join(cassandra_host_names)}}

            if env.get('orchestrator', 'openstack') != 'vcenter':
                role_dict['openstack'] = openstack_host_name
            host_dict['roles'].append(role_dict)

        if host_string in env.roledefs['control']:
            role_dict = {'type': 'bgp', 'params': {'collector': cfgm_host_name, 'cfgm': cfgm_host_name}}
            host_dict['roles'].append(role_dict)

        if 'database' in env.roledefs.keys() and host_string in env.roledefs['database']:
            role_dict = { 'type': 'database', 'params': {'cassandra': ' '.join(cassandra_host_names)} }
            host_dict['roles'].append(role_dict)

        if host_string in env.roledefs['compute']:
            role_dict = {'type': 'compute', 'params': {'collector': cfgm_host_name, 'cfgm': cfgm_host_name}}
            role_dict['params']['bgp'] = []
            if len(env.roledefs['control']) == 1:
                role_dict['params']['bgp'] = control_host_names
            else:
                for control_node in control_host_names:
                    role_dict['params']['bgp'].append(control_node)
               # role_dict['params']['bgp'].extend(control_host_names[randrange(len(env.roledefs['control']))])
            host_dict['roles'].append(role_dict)

        if 'collector' in env.roledefs.keys() and host_string in env.roledefs['collector']:
            role_dict = { 'type': 'collector', 'params': {'cassandra': ' '.join(cassandra_host_names)} }
            host_dict['roles'].append(role_dict)

        if 'webui' in env.roledefs.keys() and host_string in env.roledefs['webui']:
            role_dict = { 'type': 'webui', 'params': {'cfgm': cfgm_host_name} }
            host_dict['roles'].append(role_dict)

        sanity_testbed_dict['hosts'].append(host_dict)
    if env.has_key('vgw'): sanity_testbed_dict['vgw'].append(env.vgw)

    #get sriov info
    if env.has_key('sriov'):
        sanity_testbed_dict['sriov'].append(env.sriov)

    #get dpdk info
    if env.has_key('dpdk'):
        sanity_testbed_dict['dpdk'].append(env.dpdk)

   #get ns_agilio_vrouter info
    if env.has_key('ns_agilio_vrouter'):
        sanity_testbed_dict['ns_agilio_vrouter'].append(env.ns_agilio_vrouter)

    # Read ToR config
    sanity_tor_dict = {}
    if env.has_key('tor_agent'):
        sanity_testbed_dict['tor_agent'] = env.tor_agent

    # Read any tor-host config
    if env.has_key('tor_hosts'):
        sanity_testbed_dict['tor_hosts'] = env.tor_hosts

    if env.has_key('xmpp_auth_enable'):
        sanity_testbed_dict['xmpp_auth_enable'] = env.xmpp_auth_enable
    if env.has_key('xmpp_dns_auth_enable'):
        sanity_testbed_dict['xmpp_dns_auth_enable'] = env.xmpp_dns_auth_enable

    # Read any MX config (as physical_router )
    if env.has_key('physical_routers'):
        sanity_testbed_dict['physical_routers'] = env.physical_routers

    esxi_hosts = getattr(testbed, 'esxi_hosts', None)
    if esxi_hosts:
        for esxi in esxi_hosts:
            host_dict = {}
            host_dict['ip'] = esxi_hosts[esxi]['ip']
            host_dict['data-ip'] = host_dict['ip']
            host_dict['control-ip'] = host_dict['ip']
            host_dict['name'] = esxi
            host_dict['username'] = esxi_hosts[esxi]['username']
            host_dict['password'] = esxi_hosts[esxi]['password']
            #Its used for vcenter only mode provosioning for contrail-vm
            #Its not needed for vcenter_gateway mode, hence might not be there in testbed.py
            if 'contrail_vm' in esxi_hosts[esxi]:
                host_dict['contrail_vm'] = esxi_hosts[esxi]['contrail_vm']['host']
            host_dict['roles'] = []
            sanity_testbed_dict['hosts'].append(host_dict)
            sanity_testbed_dict['esxi_vms'].append(host_dict)

    vcenter_servers = env.get('vcenter_servers')
    if vcenter_servers:
        for vcenter in vcenter_servers:
            host_dict = {}
            host_dict['server'] = vcenter_servers[vcenter]['server']
            host_dict['port'] = vcenter_servers[vcenter]['port']
            host_dict['username'] = vcenter_servers[vcenter]['username']
            host_dict['password'] = vcenter_servers[vcenter]['password']
            host_dict['datacenter'] = vcenter_servers[vcenter]['datacenter']
            host_dict['auth'] = vcenter_servers[vcenter]['auth']
            host_dict['cluster'] = vcenter_servers[vcenter]['cluster']
            host_dict['dv_switch'] = vcenter_servers[vcenter]['dv_switch']['dv_switch_name']
            #Mostly we do not use the below info for vcenter sanity tests.
            #Its used for vcenter only mode provosioning for contrail-vm
            #Its not needed for vcenter_gateway mode, hence might not be there in testbed.py
            if 'dv_port_group' in vcenter_servers[vcenter]:
                host_dict['dv_port_group'] = vcenter_servers[vcenter]['dv_port_group']['dv_portgroup_name']
            sanity_testbed_dict['vcenter_servers'].append(host_dict)

    #get other orchestrators (vcenter etc) info if any 
    slave_orch = None  
    if env.has_key('other_orchestrators'):
        sanity_testbed_dict['other_orchestrators'] = env.other_orchestrators
        for k,v in env.other_orchestrators.items():
            if v['type'] == 'vcenter':
                slave_orch = 'vcenter'

    # get host ipmi list
    if env.has_key('hosts_ipmi'):
        sanity_testbed_dict['hosts_ipmi'].append(env.hosts_ipmi)


    if not getattr(env, 'test', None):
        env.test={}

    # generate json file and copy to cfgm
    sanity_testbed_json = json.dumps(sanity_testbed_dict)
    stack_user = os.getenv('stack_user', env.get('STACK_USER', env.test.get('stack_user', '')))
    stack_password = os.getenv('stack_password',
            env.test.get('STACK_PASSWORD',env.get('stack_password', '')))
    stack_tenant = os.getenv('STACK_TENANT', env.get('stack_tenant',
            env.test.get('stack_tenant', '')))
    stack_domain = os.getenv('STACK_DOMAIN',
            env.get('stack_domain', env.test.get('stack_domain', '')))
    if not env.has_key('domain_isolation'):
        env.domain_isolation = False
    if not env.has_key('cloud_admin_domain'):
        env.cloud_admin_domain = 'Default'
    if not env.has_key('cloud_admin_user'):
        env.cloud_admin_user = 'admin'
    if not env.has_key('cloud_admin_password'):
        env.cloud_admin_password = env.get('openstack_admin_password','contrail123')
    domain_isolation = os.getenv('DOMAIN_ISOLATION',
            env.test.get('domain_isolation', env.domain_isolation))
    cloud_admin_domain = os.getenv('CLOUD_ADMIN_DOMAIN',
            env.test.get('cloud_admin_domain', env.cloud_admin_domain))
    cloud_admin_user = os.getenv('CLOUD_ADMIN_USER',
            env.test.get('cloud_admin_user', env.cloud_admin_user))
    cloud_admin_password = os.getenv('CLOUD_ADMIN_PASSWORD',
            env.test.get('cloud_admin_password', env.cloud_admin_password))
    tenant_isolation = os.getenv('TENANT_ISOLATION',
            env.test.get('tenant_isolation', ''))

    stop_on_fail = env.get('stop_on_fail', False)
    mail_to = os.getenv('MAIL_TO', env.test.get('mail_to', ''))
    log_scenario = env.get('log_scenario', 'Sanity')
    stack_region_name = get_region_name()
    admin_user, admin_password = get_authserver_credentials()
    admin_tenant = get_admin_tenant_name()
    # Few hardcoded variables for sanity environment
    # can be removed once we move to python3 and configparser

    webserver_host = os.getenv('WEBSERVER_HOST',
            env.test.get('webserver_host',''))
    webserver_user = os.getenv('WEBSERVER_USER',
            env.test.get('webserver_user', ''))
    webserver_password = os.getenv('WEBSERVER_PASSWORD',
            env.test.get('webserver_password', ''))
    webserver_log_path = os.getenv('WEBSERVER_LOG_PATH',
            env.test.get('webserver_log_path', '/var/www/contrail-test-ci/logs/'))
    webserver_report_path = os.getenv('WEBSERVER_REPORT_PATH',
            env.test.get('webserver_report_path', '/var/www/contrail-test-ci/reports/'))
    webroot = os.getenv('WEBROOT', env.test.get('webroot', 'contrail-test-ci'))
    mail_server = os.getenv('MAIL_SERVER', env.test.get('mail_server', ''))
    mail_port = os.getenv('MAIL_PORT', env.test.get('mail_port', '25'))
    fip_pool_name = os.getenv('FIP_POOL_NAME',
            env.test.get('fip_pool_name', 'floating-ip-pool'))
    public_virtual_network = os.getenv('PUBLIC_VIRTUAL_NETWORK',
            env.test.get('public_virtual_network', 'public'))
    public_tenant_name = os.getenv('PUBLIC_TENANT_NAME',
            env.test.get('public_tenant_name', 'admin'))
    fixture_cleanup = os.getenv('FIXTURE_CLEANUP',
            env.test.get('fixture_cleanup', 'yes'))
    generate_html_report = os.getenv('GENERATE_HTML_REPORT',
            env.test.get('generate_html_report', 'True'))
    keypair_name = os.getenv('KEYPAIR_NAME',
            env.test.get('keypair_name', 'contrail_key'))
    mail_sender = os.getenv('MAIL_SENDER', env.test.get('mail_sender', 'contrailbuild@juniper.net'))
    discovery_ip = os.getenv('DISCOVERY_IP', env.test.get('discovery_ip', ''))
    config_api_ip = os.getenv('CONFIG_API_IP', env.test.get('config_api_ip', ''))
    analytics_api_ip = os.getenv('ANALYTICS_API_IP',
            env.test.get('analytics_api_ip', ''))
    discovery_port = os.getenv('DISCOVERY_PORT',
            env.test.get('discovery_port', ''))
    config_api_port = os.getenv('CONFIG_API_PORT',
            env.test.get('config_api_port', ''))
    analytics_api_port = os.getenv('ANALYTICS_API_PORT',
            env.test.get('analytics_api_port', ''))
    control_port = os.getenv('CONTROL_PORT', env.test.get('control_port', ''))
    dns_port = os.getenv('DNS_PORT', env.test.get('dns_port', ''))
    agent_port = os.getenv('AGENT_PORT', env.test.get('agent_port', ''))
    user_isolation = os.getenv('USER_ISOLATION',
            env.test.get('user_isolation', True))
    neutron_username = os.getenv('NEUTRON_USERNAME',
            env.test.get('neutron_username', None))
    availability_zone = os.getenv('AVAILABILITY_ZONE',
            env.test.get('availability_zone', None))
    ci_flavor = os.getenv('CI_FLAVOR', env.test.get('ci_flavor', None))
    use_devicemanager_for_md5 = getattr(testbed, 'use_devicemanager_for_md5', False)

    orch = getattr(env, 'orchestrator', 'openstack')
    router_asn = getattr(testbed, 'router_asn', '')
    public_vn_rtgt = getattr(testbed, 'public_vn_rtgt', '')
    public_vn_subnet = getattr(testbed, 'public_vn_subnet', '')
    ext_routers = getattr(testbed, 'ext_routers', '')
    router_info = str(ext_routers)
    test_verify_on_setup = getattr(env, 'test_verify_on_setup', True)
    webui = getattr(testbed, 'webui', False)
    horizon = getattr(testbed, 'horizon', False)
    ui_config = getattr(testbed, 'ui_config', False)
    ui_browser = getattr(testbed, 'ui_browser', False)

    if not env.has_key('openstack'):
        env.openstack = {}
    if not env.has_key('cfgm'):
        env.cfgm = {}

    config_amqp_ip = env.openstack.get('amqp_host', '')
    if config_amqp_ip:
        config_amqp_ips = [config_amqp_ip]
    else:
        config_amqp_ips = []

    # If amqp details are in env.cfgm as well, use that 
    config_amqp_port = env.cfgm.get('amqp_port', '5672')
    config_amqp_ips = env.cfgm.get('amqp_hosts', config_amqp_ips)

    key_filename = env.get('key_filename', '')
    pubkey_filename = env.get('pubkey_filename', '')

    vcenter_dc = ''
    if orch == 'vcenter' or slave_orch== 'vcenter':
        public_tenant_name='vCenter'

    if env.has_key('vcenter_servers'):
            if env.vcenter_servers:
                for k in env.vcenter_servers:
                    vcenter_dc = env.vcenter_servers[k]['datacenter']

    sanity_params = sanity_ini_templ.safe_substitute(
        {'__testbed_json_file__'   : 'sanity_testbed.json',
         '__keystone_version__'    : keystone_version,
         '__nova_keypair_name__'   : keypair_name,
         '__orch__'                : orch,
         '__admin_user__'          : admin_user,
         '__admin_password__'      : admin_password,
         '__admin_tenant__'        : admin_tenant,
         '__domain_isolation__'    : domain_isolation,
         '__cloud_admin_domain__'  : cloud_admin_domain,
         '__cloud_admin_user__'    : cloud_admin_user,
         '__cloud_admin_password__': cloud_admin_password,
         '__tenant_isolation__'    : tenant_isolation,
         '__stack_user__'          : stack_user,
         '__stack_password__'      : stack_password,
         '__auth_ip__'             : auth_server_ip,
         '__auth_port__'           : auth_server_port,
         '__auth_protocol__'       : auth_protocol,
         '__stack_region_name__'   : stack_region_name,
         '__stack_tenant__'        : stack_tenant,
         '__stack_domain__'        : stack_domain,
         '__multi_tenancy__'       : get_mt_enable(),
         '__address_family__'      : get_address_family(),
         '__log_scenario__'        : log_scenario,
         '__generate_html_report__': generate_html_report,
         '__fixture_cleanup__'     : fixture_cleanup,
         '__key_filename__'        : key_filename,
         '__pubkey_filename__'     : pubkey_filename,
         '__webserver__'           : webserver_host,
         '__webserver_user__'      : webserver_user,
         '__webserver_password__'  : webserver_password,
         '__webserver_log_dir__'   : webserver_log_path,
         '__webserver_report_dir__': webserver_report_path,
         '__webroot__'             : webroot,
         '__mail_server__'         : mail_server,
         '__mail_port__'           : mail_port,
         '__sender_mail_id__'      : mail_sender,
         '__receiver_mail_id__'    : mail_to,
         '__http_proxy__'          : env.get('http_proxy', ''),
         '__ui_browser__'          : ui_browser,
         '__ui_config__'           : ui_config,
         '__horizon__'             : horizon,
         '__webui__'               : webui,
         '__devstack__'            : False,
         '__public_vn_rtgt__'      : public_vn_rtgt,
         '__router_asn__'          : router_asn,
         '__router_name_ip_tuples__': router_info,
         '__public_vn_name__'      : fip_pool_name,
         '__public_virtual_network__':public_virtual_network,
         '__public_tenant_name__'  :public_tenant_name,
         '__public_vn_subnet__'    : public_vn_subnet,
         '__test_revision__'       : revision,
         '__fab_revision__'        : fab_revision,
         '__test_verify_on_setup__': test_verify_on_setup,
         '__stop_on_fail__'        : stop_on_fail,
         '__ha_setup__'            : getattr(testbed, 'ha_setup', ''),
         '__ipmi_username__'       : getattr(testbed, 'ipmi_username', ''),
         '__ipmi_password__'       : getattr(testbed, 'ipmi_password', ''),
         '__contrail_internal_vip__' : contrail_internal_vip,
         '__contrail_external_vip__' : contrail_external_vip,
         '__internal_vip__'        : internal_vip,
         '__external_vip__'        : external_vip,
         '__vcenter_dc__'          : vcenter_dc,
         '__vcenter_server__'      : get_vcenter_ip(),
         '__vcenter_port__'        : get_vcenter_port(),
         '__vcenter_username__'    : get_vcenter_username(),
         '__vcenter_password__'    : get_vcenter_password(),
         '__vcenter_datacenter__'  : get_vcenter_datacenter(),
         '__vcenter_compute__'     : get_vcenter_compute(),
         '__use_devicemanager_for_md5__'       : use_devicemanager_for_md5,
         '__discovery_port__'      : discovery_port,
         '__config_api_port__'     : config_api_port,
         '__analytics_api_port__'  : analytics_api_port,
         '__control_port__'        : control_port,
         '__dns_port__'            : dns_port,
         '__vrouter_agent_port__'  : agent_port,
         '__discovery_ip__'        : discovery_ip,
         '__config_api_ip__'       : config_api_ip,
         '__analytics_api_ip__'    : analytics_api_ip,
         '__user_isolation__'      : user_isolation,
         '__neutron_username__'    : neutron_username,
         '__availability_zone__'   : availability_zone,
         '__ci_flavor__'           : ci_flavor,
         '__config_amqp_ips__'     : ','.join(config_amqp_ips),
         '__config_amqp_port__'    : config_amqp_port,
         '__api_auth_protocol__'   : api_auth_protocol,
         '__ds_auth_protocol__'    : discovery_auth_protocol,
         '__api_certfile__'        : api_certfile,
         '__api_keyfile__'         : api_keyfile,
         '__api_cafile__'          : api_cafile,
         '__api_insecure_flag__'   : api_insecure_flag,
         '__keystone_certfile__'   : keystone_certfile,
         '__keystone_keyfile__'    : keystone_keyfile,
         '__keystone_cafile__'     : keystone_cafile,
         '__keystone_insecure_flag__': keystone_insecure_flag,
        })

    ini_file = test_dir + '/' + 'sanity_params.ini'
    testbed_json_file = test_dir + '/' + 'sanity_testbed.json'
    with open(ini_file, 'w') as ini:
        ini.write(sanity_params)

    with open(testbed_json_file,'w') as tb:
        tb.write(sanity_testbed_json)

    # Create /etc/contrail/openstackrc
    if not os.path.exists('/etc/contrail'):
        os.makedirs('/etc/contrail')

    keycertbundle = None
    if keystone_cafile and keystone_keyfile and keystone_certfile:
        bundle = '/tmp/keystonecertbundle.pem'
        certs = [keystone_certfile, keystone_keyfile, keystone_cafile]
        keycertbundle = utils.getCertKeyCaBundle(bundle, certs)

    with open('/etc/contrail/openstackrc','w') as rc:
        rc.write("export OS_USERNAME=%s\n" % admin_user)
        rc.write("export OS_PASSWORD=%s\n" % admin_password)
        rc.write("export OS_TENANT_NAME=%s\n" % admin_tenant)
        rc.write("export OS_REGION_NAME=%s\n" % stack_region_name)
        rc.write("export OS_AUTH_URL=%s://%s:%s/v2.0\n" % (auth_protocol,
                                                           auth_server_ip,
                                                           auth_server_port))
        rc.write("export OS_CACERT=%s\n" % keycertbundle)
        rc.write("export OS_CERT=%s\n" % keystone_certfile)
        rc.write("export OS_KEY=%s\n" % keystone_keyfile)
        rc.write("export OS_INSECURE=%s\n" % keystone_insecure_flag)
        rc.write("export OS_NO_CACHE=1\n")

    # Write vnc_api_lib.ini - this is required for vnc_api to connect to keystone
    config = ConfigParser.ConfigParser()
    config.optionxform = str
    vnc_api_ini = '/etc/contrail/vnc_api_lib.ini'
    if os.path.exists(vnc_api_ini):
        config.read(vnc_api_ini)

    if 'auth' not in config.sections():
        config.add_section('auth')

    config.set('auth','AUTHN_TYPE', 'keystone')
    config.set('auth','AUTHN_PROTOCOL', auth_protocol)
    config.set('auth','AUTHN_SERVER', auth_server_ip)
    config.set('auth','AUTHN_PORT', auth_server_port)
    if keystone_version == 'v3':
        config.set('auth','AUTHN_URL', '/v3/auth/tokens')
    else:
        config.set('auth','AUTHN_URL', '/v2.0/tokens')

    if api_auth_protocol == 'https':
        if 'global' not in config.sections():
            config.add_section('global')
        config.set('global','certfile', api_certfile)
        config.set('global','cafile', api_cafile)
        config.set('global','keyfile', api_keyfile)
        config.set('global','insecure',api_insecure_flag)

    if auth_protocol == 'https':
        if 'auth' not in config.sections():
            config.add_section('auth')
        config.set('auth','certfile', keystone_certfile)
        config.set('auth','cafile', keystone_cafile)
        config.set('auth','keyfile', keystone_keyfile)
        config.set('auth','insecure', keystone_insecure_flag)

    with open(vnc_api_ini,'w') as f:
        config.write(f)

    # If webui = True, in testbed, setup webui for sanity
    if webui:
        update_config_option('openstack', '/etc/keystone/keystone.conf',
                             'token', 'expiration',
                             '86400','keystone')
        update_js_config('openstack', '/etc/contrail/config.global.js',
                         'contrail-webui')

def main(argv=sys.argv):
    ap = argparse.ArgumentParser(
        description='Configure test environment')
    ap.add_argument('contrail_test_directory', type=str,
                    help='contrail test directory')
    ap.add_argument('-p','--contrail-fab-path', type=str, default='/opt/contrail/utils',
                    help='Contrail fab path on local machine')
    args = ap.parse_args()

    configure_test_env(args.contrail_fab_path, args.contrail_test_directory)

if __name__ == "__main__":
    sys.exit(main(sys.argv))
