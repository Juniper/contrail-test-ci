import test_v1
from common.connections import ContrailConnections
from tcutils.ssl_certs_utils import SslCert
from common.base import GenericTestBase
from tcutils.util import get_random_name
import os
import ConfigParser
from fabric.operations import put, get
from fabric.context_managers import settings, hide
from tcutils.collector.opserver_introspect_utils import VerificationOpsSrvIntrospect
from tcutils.agent.vna_introspect_utils import AgentInspect
from tcutils.config.svc_mon_introspect_utils import SvcMonInspect
from tcutils.control.cn_introspect_utils import ControlNodeInspect
from tcutils.vdns.dns_introspect_utils import DnsAgentInspect
from tcutils.verification_util import VerificationUtilBase, XmlDrv

CERT_LOCATION = '/tmp/'
DEFAULT_CERT = '/etc/contrail/ssl/certs/server.pem'
DEFAULT_PRIV_KEY = '/etc/contrail/ssl/private/server-privkey.pem'
DEFAULT_CA = '/etc/contrail/ssl/certs/ca-cert.pem'

CONTRAIL_CONF_FILES = {
    'contrail-vrouter-agent': '/etc/contrail/contrail-vrouter-agent.conf',
    'contrail-analytics-api': '/etc/contrail/contrail-analytics-api.conf',
    'contrail-collector': '/etc/contrail/contrail-collector.conf',
    'contrail-query-engine': '/etc/contrail/contrail-query-engine.conf',
    'contrail-snmp-collector': '/etc/contrail/contrail-snmp-collector.conf',
    'contrail-alarm-gen': '/etc/contrail/contrail-alarm-gen',
    'contrail-control': '/etc/contrail/contrail-control.conf',
    'contrail-dns': '/etc/contrail/contrail-dns.conf',
    'contrail-api': '/etc/contrail/contrail-api.conf',
    'contrail-schema': '/etc/contrail/contrail-schema.conf',
    'contrail-svc-monitor': '/etc/contrail/contrail-svc-monitor.conf'}

CONTRAIL_INTROSPECT_PORTS = {
    'contrail-vrouter-agent': 8085,
    'contrail-analytics-api': 8090,
    'contrail-collector': 8089,
    'contrail-query-engine': 8091,
    'contrail-control': 8083,
    'contrail-dns': 8092,
    'contrail-schema': 8087,
    'contrail-api': 8084,
    'contrail-svc-monitor': 8088}

CONTRAIL_SERVICE_CONTAINER = {
    'contrail-vrouter-agent': None,
    'contrail-analytics-api': 'analytics',
    'contrail-collector': 'analytics',
    'contrail-query-engine': 'analytics',
    'contrail-control': 'controller',
    'contrail-dns': 'controller',
    'contrail-schema': 'controller',
    'contrail-api': 'controller',
    'contrail-svc-monitor': 'controller'}

class BaseIntrospectSsl(GenericTestBase):

    @classmethod
    def setUpClass(cls):
        super(BaseIntrospectSsl, cls).setUpClass()
        cls.quantum_h = cls.connections.quantum_h
        cls.nova_h = cls.connections.nova_h
        cls.vnc_lib_fixture = cls.connections.vnc_lib_fixture
        cls.vnc_lib = cls.connections.vnc_lib
        cls.agent_inspect = cls.connections.agent_inspect
        cls.cn_inspect = cls.connections.cn_inspect
        cls.analytics_obj = cls.connections.analytics_obj
        cls.api_s_inspect = cls.connections.api_server_inspect
        cls.orch = cls.connections.orch
        cls.logger = cls.connections.logger
        cls.cert_location = CERT_LOCATION
        cls.ca_cert = None
        cls.ca_private_key = None
    #end setUpClass

    @classmethod
    def tearDownClass(cls):
        super(BaseIntrospectSsl, cls).tearDownClass()
    # end tearDownClass

    def set_ssl_config_in_inputs(self, inputs=None, key=None, cert=None, ca_cert=None):
        inputs = inputs or self.inputs

        self.introspect_insecure_old = inputs.introspect_insecure

        inputs.introspect_certfile = cert or DEFAULT_CERT
        inputs.introspect_keyfile = key or DEFAULT_PRIV_KEY
        inputs.introspect_cafile = ca_cert or DEFAULT_CA
        inputs.introspect_insecure = False
        inputs.introspect_protocol = 'https'
        inputs.certbundle = inputs.introspect_cafile

        return inputs

    def check_file_dir_exists(self, file_dir, tries=5):
        while tries > 0:
            if os.path.isfile(file_dir) or os.path.isdir(file_dir):
                return 1
            else:
                time.sleep(0.5)
                tries -= 1
        assert False, 'file is not present'

    def create_ca_cert(self):
        ca_private_key = self.cert_location + get_random_name(self.connections.project_name) + '-ca-cert-privkey.pem'
        ca_cert = self.cert_location + get_random_name(self.connections.project_name) + '-ca-cert.pem'

        SslCert.generate_private_key(ca_private_key)
        self.check_file_dir_exists(ca_private_key)
        self.ca_private_key = ca_private_key
        result, fqdn, stderr  = SslCert.local_exec('hostname -f')
        subject = '/CN=contrail-test-ca-' + fqdn
        SslCert.generate_cert(ca_cert, ca_private_key, self_signed=True, subj=subject)
        self.check_file_dir_exists(ca_cert)
        self.ca_cert = ca_cert
        return ca_private_key, ca_cert

    def create_cert(self, subject='/', subjectAltName=None, ca_cert=None):
        ca_cert = ca_cert or self.ca_cert
        private_key = self.cert_location + get_random_name(self.connections.project_name) + '-privkey.pem'
        csr = self.cert_location + get_random_name(self.connections.project_name) + '-req.csr'
        cert = self.cert_location + get_random_name(self.connections.project_name) + '-cert.pem'
        SslCert.generate_private_key(private_key)
        self.check_file_dir_exists(private_key)
        SslCert.generate_csr(csr, private_key, subj=subject, subjectAltName=subjectAltName)
        self.check_file_dir_exists(csr)
        SslCert.generate_cert(cert, self.ca_private_key, ca_pem=ca_cert,
                           csr=csr, subjectAltName=subjectAltName)
        self.check_file_dir_exists(cert)
        return private_key, csr, cert

    def copy_certs_on_node(self, node_ip, cert_list, dstdir=CERT_LOCATION, container=None):
        '''copy certificates on node or container'''

        for cert in cert_list:
            self.inputs.copy_file_to_server(node_ip, cert, self.cert_location,
                cert.split('/')[-1], container=container)

    def create_agent_certs_and_update_on_compute(self, compute_fixture, subject,
            ssl_enable='false', subjectAltName=None):
        agent_key, agent_csr, agent_cert = self.create_cert(subject=subject,
            subjectAltName=subjectAltName)

        self.copy_certs_on_node(compute_fixture.ip, [agent_key, agent_cert, self.ca_cert])

        return self.update_agent_ssl_config(compute_fixture, ssl_enable, agent_key,
            agent_cert, self.ca_cert)

    def update_agent_ssl_config(self, compute_fixture, ssl_enable=False,
            key=None, cert=None, ca_cert=None):

        #Copy original config file to restore it in cleanup
        agent_config_file = get_random_name('contrail-vroute-agent')
        cmd = "cp " + compute_fixture.agent_conf_file + " /tmp/" +\
            agent_config_file
        output = self.inputs.run_cmd_on_server(
            compute_fixture.ip,
            cmd,
            self.inputs.host_data[compute_fixture.ip]['username'],
            self.inputs.host_data[compute_fixture.ip]['password'])

        compute_fixture.get_introspect_ssl_and_certs()
        ssl_enable_old = compute_fixture.introspect_ssl_enable
        self.addCleanup(
            self.restore_default_agent_config,
            compute_fixture, agent_config_file, ssl_enable_old)

        return compute_fixture.set_introspect_ssl_and_certs(ssl_enable, key,
            cert, ca_cert)

    def restore_default_config_file(self, conf_file_backup, service_name, node_ip,
                              container=None):

        cmd = "mv %s %s" % (conf_file_backup, CONTRAIL_CONF_FILES[service_name])
        output = self.inputs.run_cmd_on_server(
            node_ip,
            cmd,
            self.inputs.host_data[node_ip]['username'],
            self.inputs.host_data[node_ip]['password'],
            container=container)

        self.inputs.introspect_insecure = self.introspect_insecure_old
        self.inputs.restart_service(service_name, [node_ip], container=container)
        self.inputs.confirm_service_active(service_name, node_ip, container)

    def restore_default_agent_config(self, compute_fixture, agent_config_file, ssl_enable):
        cmd = "cp /tmp/%s %s" % (agent_config_file ,compute_fixture.agent_conf_file)
        output = self.inputs.run_cmd_on_server(
            compute_fixture.ip,
            cmd,
            self.inputs.host_data[compute_fixture.ip]['username'],
            self.inputs.host_data[compute_fixture.ip]['password'])

        compute_fixture.introspect_ssl_enable = ssl_enable
        compute_fixture.restart_agent()
        compute_fixture.wait_for_vrouter_agent_state(state='active')

    def get_url_and_verify(self, url, inspect, exp_out=None):
        output = inspect.dict_get(url=url, raw_data=True)
        assert (output != None)
        self.logger.debug("output: %s" % (output))
        if exp_out:
            assert (output == exp_out)
        self.logger.info("Request %s, Result: Success" % (url))
        return output

    def update_contrail_conf(self, service, operation, section, option, value,
                              node_ip, container=None, verify_service=True):
        conf_file = CONTRAIL_CONF_FILES[service]
        if operation == 'del':
            cmd = 'openstack-config --del %s %s %s' % (conf_file, section, option)
        if operation == 'set':
            cmd = 'openstack-config --set %s %s %s %s' % (conf_file, section, option, value)
        status = self.inputs.run_cmd_on_server(node_ip, cmd, container=container)

        if verify_service:
            self.inputs.restart_service(service, [node_ip], container=container)
            self.inputs.confirm_service_active(service, node_ip, container)

        return status

    def udpate_config_file_and_restart_service(self, node_ip, conf_file, ssl_enable, keyfile,
            certfile, ca_certfile, service_name, container_name=None):
        '''
        set the introspect ssl configurations and restart the service
        '''

        self.logger.info('Set introspect ssl configs in node %s' % (node_ip))

        #Take backup of original conf file to revert back later
        conf_file_backup = CERT_LOCATION + get_random_name(conf_file.split('/')[-1])
        cmd = 'cp %s %s' % (conf_file, conf_file_backup)
        status = self.inputs.run_cmd_on_server(node_ip, cmd, container=container_name)

        oper = 'set'
        section = 'SANDESH'
        self.update_contrail_conf(service_name, oper, section,
            'introspect_ssl_enable', ssl_enable, node_ip, container_name, verify_service=False)
        self.update_contrail_conf(service_name, oper, section,
            'sandesh_keyfile', keyfile, node_ip, container_name, verify_service=False)
        self.update_contrail_conf(service_name, oper, section,
            'sandesh_certfile', certfile, node_ip, container_name, verify_service=False)
        self.update_contrail_conf(service_name, oper, section,
            'sandesh_ca_cert', ca_certfile, node_ip, container_name, verify_service=True)

        self.addCleanup(
            self.restore_default_config_file,
            conf_file_backup, service_name, node_ip, container_name)

    def get_introspect_for_service(self, service, host_ip):
        if service == 'contrail-svc-monitor':
            inspect = SvcMonInspect(host_ip,
                port=CONTRAIL_INTROSPECT_PORTS[service], logger=self.logger,
                args=self.inputs)
        elif service == 'contrail-vrouter-agent':
            agent_inspect = AgentInspect(host_ip,
                CONTRAIL_INTROSPECT_PORTS[service], self.logger,
                inputs=self.inputs)
        elif service in ['contrail-query-engine', 'contrail-analytics-api', 'contrail-collector']:
            inspect = VerificationOpsSrvIntrospect(host_ip,
                CONTRAIL_INTROSPECT_PORTS[service], self.logger,
                inputs=self.inputs)
        elif service == 'contrail-dns':
            inspect = DnsAgentInspect(host_ip,
                CONTRAIL_INTROSPECT_PORTS[service], self.logger,
                args=self.inputs)
        elif service == 'contrail-control':
            inspect = ControlNodeInspect(host_ip,
                CONTRAIL_INTROSPECT_PORTS[service], self.logger,
                args=self.inputs)
        elif service in ['contrail-api', 'contrail-schema']:
            inspect = VerificationUtilBase(host_ip,
                CONTRAIL_INTROSPECT_PORTS[service], drv=XmlDrv, logger=self.logger,
                args=self.inputs)
        else:
            inspect = None

        return inspect
