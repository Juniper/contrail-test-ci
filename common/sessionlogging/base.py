from common.flow_tests.base import FlowTestBase
from common.introspect.base import BaseIntrospectSsl
from policy_test import PolicyFixture
from vn_policy_test import VN_Policy_Fixture
from tcutils.util import retry, get_random_name
from security_group import list_sg_rules
import random, re

AGENT_LOG = 'agent'
SYS_LOG = 'syslog'
UNDERLAY_PROTO = {
                'MPLSoGRE': 1,
                'MPLSoUDP': 2,
                'VXLAN': 3
                }
PROTO_STR = {
    1: 'icmp',
    6: 'tcp',
    17: 'udp',
    58: 'icmpv6'
}
FIREWALL_RULE_ID_DEFAULT = '00000000-0000-0000-0000-000000000001'
IP_RE = '[[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}]'
INT_RE = '\d+'
PORT_RE = '\d+'
UUID_RE = '[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}'

SESSION_LOG = "\[  vmi = %s vn = %s security_policy_rule = %s remote_vn = %s is_client_session = %s is_si = %s vrouter_ip = %s sess_agg_info= \[  \[ \[  local_ip = %s service_port = %s protocol = %s ] \[  sampled_forward_bytes = %s sampled_forward_pkts = %s sampled_reverse_bytes = %s sampled_reverse_pkts = %s sessionMap= \[  \[ \[  ip = %s port = %s ] \[  forward_flow_info= \[ sampled_bytes = %s sampled_pkts = %s flow_uuid = %s tcp_flags = %s setup_time = %s action = %s sg_rule_uuid = %s nw_ace_uuid = %s underlay_source_port = %s ] reverse_flow_info= \[  sampled_bytes = %s sampled_pkts = %s flow_uuid = %s tcp_flags = %s setup_time = %s action = %s sg_rule_uuid = %s nw_ace_uuid = %s underlay_source_port = %s ] vm = %s other_vrouter_ip = %s underlay_proto = %s ],  ] ] ],  ] ] ]"

SESSION_LOG_FWD = "\[  vmi = %s vn = %s security_policy_rule = %s remote_vn = %s is_client_session = %s is_si = %s vrouter_ip = %s sess_agg_info= \[  \[ \[  local_ip = %s service_port = %s protocol = %s ] \[  sampled_forward_bytes = %s sampled_forward_pkts = %s sampled_reverse_bytes = %s sampled_reverse_pkts = %s sessionMap= \[  \[ \[  ip = %s port = %s ] \[  forward_flow_info= \[ sampled_bytes = %s sampled_pkts = %s flow_uuid = %s tcp_flags = %s setup_time = %s action = %s sg_rule_uuid = %s nw_ace_uuid = %s underlay_source_port = %s ] reverse_flow_info= \[   flow_uuid = %s setup_time = %s action = %s sg_rule_uuid = %s nw_ace_uuid = %s ] vm = %s other_vrouter_ip = %s underlay_proto = %s ],  ] ] ],  ] ] ]"

SESSION_SYSLOG = "\[ vmi = %s vn = %s ] security_policy_rule = %s remote_vn = %s is_client_session = %s is_si = %s vrouter_ip = %s local_ip = %s service_port = %s protocol = %s sampled_forward_bytes = %s sampled_forward_pkts = %s sampled_reverse_bytes = %s sampled_reverse_pkts = %s ip = %s port = %s forward_flow_info= \[ sampled_bytes = %s sampled_pkts = %s flow_uuid = %s tcp_flags = %s setup_time = %s action = %s sg_rule_uuid = %s nw_ace_uuid = %s underlay_source_port = %s ] reverse_flow_info= \[  sampled_bytes = %s sampled_pkts = %s flow_uuid = %s tcp_flags = %s setup_time = %s action = %s sg_rule_uuid = %s nw_ace_uuid = %s underlay_source_port = %s ] vm = %s other_vrouter_ip = %s underlay_proto = %s"

SESSION_TEARDOWN = "\[  vmi = %s vn = %s security_policy_rule = %s remote_vn = %s is_client_session = %s is_si = %s vrouter_ip = %s sess_agg_info= \[  \[ \[  local_ip = %s service_port = %s protocol = %s ] \[  sampled_forward_bytes = %s sampled_forward_pkts = %s sampled_reverse_bytes = %s sampled_reverse_pkts = %s sessionMap= \[  \[ \[  ip = %s port = %s ] \[  forward_flow_info= \[  flow_uuid = %s setup_time = %s teardown_time = %s teardown_bytes = %s teardown_pkts = %s action = %s sg_rule_uuid = %s nw_ace_uuid = %s ] reverse_flow_info= \[   flow_uuid = %s setup_time = %s teardown_time = %s teardown_bytes = %s teardown_pkts = %s action = %s sg_rule_uuid = %s nw_ace_uuid = %s ] vm = %s other_vrouter_ip = %s underlay_proto = %s ],  ] ] ],  ] ] ]"

SESSION_TEARDOWN_TCP = "\[  vmi = %s vn = %s security_policy_rule = %s remote_vn = %s is_client_session = %s is_si = %s vrouter_ip = %s sess_agg_info= \[  \[ \[  local_ip = %s service_port = %s protocol = %s ] \[  sampled_forward_bytes = %s sampled_forward_pkts = %s sampled_reverse_bytes = %s sampled_reverse_pkts = %s sessionMap= \[  \[ \[  ip = %s port = %s ] \[  forward_flow_info= \[ sampled_bytes = %s sampled_pkts = %s flow_uuid = %s tcp_flags = %s setup_time = %s teardown_time = %s teardown_bytes = %s teardown_pkts = %s action = %s sg_rule_uuid = %s nw_ace_uuid = %s underlay_source_port = %s ] reverse_flow_info= \[  sampled_bytes = %s sampled_pkts = %s flow_uuid = %s tcp_flags = %s setup_time = %s teardown_time = %s teardown_bytes = %s teardown_pkts = %s action = %s sg_rule_uuid = %s nw_ace_uuid = %s underlay_source_port = %s ] vm = %s other_vrouter_ip = %s underlay_proto = %s ],  ] ] ],  ] ] ]"

SESSION_SYSLOG_TEARDOWN = "\[ vmi = %s vn = %s ] security_policy_rule = %s remote_vn = %s is_client_session = %s is_si = %s vrouter_ip = %s local_ip = %s service_port = %s protocol = %s sampled_forward_bytes = %s sampled_forward_pkts = %s sampled_reverse_bytes = %s sampled_reverse_pkts = %s ip = %s port = %s forward_flow_info= \[  flow_uuid = %s setup_time = %s teardown_time = %s teardown_bytes = %s teardown_pkts = %s action = %s sg_rule_uuid = %s nw_ace_uuid = %s ] reverse_flow_info= \[   flow_uuid = %s setup_time = %s teardown_time = %s teardown_bytes = %s teardown_pkts = %s action = %s sg_rule_uuid = %s nw_ace_uuid = %s ] vm = %s other_vrouter_ip = %s underlay_proto = %s"

SESSION_SYSLOG_TEARDOWN_TCP = "\[ vmi = %s vn = %s ] security_policy_rule = %s remote_vn = %s is_client_session = %s is_si = %s vrouter_ip = %s local_ip = %s service_port = %s protocol = %s sampled_forward_bytes = %s sampled_forward_pkts = %s sampled_reverse_bytes = %s sampled_reverse_pkts = %s ip = %s port = %s forward_flow_info= \[ sampled_bytes = %s sampled_pkts = %s flow_uuid = %s tcp_flags = %s setup_time = %s teardown_time = %s teardown_bytes = %s teardown_pkts = %s action = %s sg_rule_uuid = %s nw_ace_uuid = %s underlay_source_port = %s ] reverse_flow_info= \[  sampled_bytes = %s sampled_pkts = %s flow_uuid = %s tcp_flags = %s setup_time = %s teardown_time = %s teardown_bytes = %s teardown_pkts = %s action = %s sg_rule_uuid = %s nw_ace_uuid = %s underlay_source_port = %s ] vm = %s other_vrouter_ip = %s underlay_proto = %s"

SESSION_CLIENT_AGGR = "\[  vmi = %s vn = %s security_policy_rule = %s remote_vn = %s is_client_session = %s is_si = %s vrouter_ip = %s sess_agg_info= \[  \[ \[  local_ip = %s service_port = %s protocol = %s ] \[  sampled_forward_bytes = %s sampled_forward_pkts = %s sampled_reverse_bytes = %s sampled_reverse_pkts = %s sessionMap= \[  \[ \[  ip = %s port = %s ] \[  forward_flow_info= \[ sampled_bytes = %s sampled_pkts = %s flow_uuid = %s tcp_flags = %s setup_time = %s action = %s sg_rule_uuid = %s nw_ace_uuid = %s underlay_source_port = %s ] reverse_flow_info= \[  sampled_bytes = %s sampled_pkts = %s flow_uuid = %s tcp_flags = %s setup_time = %s action = %s sg_rule_uuid = %s nw_ace_uuid = %s underlay_source_port = %s ] vm = %s other_vrouter_ip = %s underlay_proto = %s ],  \[  ip = %s port = %s ] \[  forward_flow_info= \[ sampled_bytes = %s sampled_pkts = %s flow_uuid = %s tcp_flags = %s setup_time = %s action = %s sg_rule_uuid = %s nw_ace_uuid = %s underlay_source_port = %s ] reverse_flow_info= \[  sampled_bytes = %s sampled_pkts = %s flow_uuid = %s tcp_flags = %s setup_time = %s action = %s sg_rule_uuid = %s nw_ace_uuid = %s underlay_source_port = %s ] vm = %s other_vrouter_ip = %s underlay_proto = %s ],  \[  ip = %s port = %s ] \[  forward_flow_info= \[ sampled_bytes = %s sampled_pkts = %s flow_uuid = %s tcp_flags = %s setup_time = %s action = %s sg_rule_uuid = %s nw_ace_uuid = %s underlay_source_port = %s ] reverse_flow_info= \[  sampled_bytes = %s sampled_pkts = %s flow_uuid = %s tcp_flags = %s setup_time = %s action = %s sg_rule_uuid = %s nw_ace_uuid = %s underlay_source_port = %s ] vm = %s other_vrouter_ip = %s underlay_proto = %s ],  ] ] ],  ] ] ]"

SESSION_CLIENT_AGGR_TEARDOWN = "\[  vmi = %s vn = %s security_policy_rule = %s remote_vn = %s is_client_session = %s is_si = %s vrouter_ip = %s sess_agg_info= \[  \[ \[  local_ip = %s service_port = %s protocol = %s ] \[  sampled_forward_bytes = %s sampled_forward_pkts = %s sampled_reverse_bytes = %s sampled_reverse_pkts = %s sessionMap= \[  \[ \[  ip = %s port = %s ] \[  forward_flow_info= \[  flow_uuid = %s setup_time = %s teardown_time = %s teardown_bytes = %s teardown_pkts = %s action = %s sg_rule_uuid = %s nw_ace_uuid = %s ] reverse_flow_info= \[   flow_uuid = %s setup_time = %s teardown_time = %s teardown_bytes = %s teardown_pkts = %s action = %s sg_rule_uuid = %s nw_ace_uuid = %s ] vm = %s other_vrouter_ip = %s underlay_proto = %s ],  \[  ip = %s port = %s ] \[  forward_flow_info= \[  flow_uuid = %s setup_time = %s teardown_time = %s teardown_bytes = %s teardown_pkts = %s action = %s sg_rule_uuid = %s nw_ace_uuid = %s ] reverse_flow_info= \[   flow_uuid = %s setup_time = %s teardown_time = %s teardown_bytes = %s teardown_pkts = %s action = %s sg_rule_uuid = %s nw_ace_uuid = %s ] vm = %s other_vrouter_ip = %s underlay_proto = %s ],  \[  ip = %s port = %s ] \[  forward_flow_info= \[  flow_uuid = %s setup_time = %s teardown_time = %s teardown_bytes = %s teardown_pkts = %s action = %s sg_rule_uuid = %s nw_ace_uuid = %s ] reverse_flow_info= \[   flow_uuid = %s setup_time = %s teardown_time = %s teardown_bytes = %s teardown_pkts = %s action = %s sg_rule_uuid = %s nw_ace_uuid = %s ] vm = %s other_vrouter_ip = %s underlay_proto = %s ],  ] ] ],  ] ] ]"

SESSION_CLIENT_AGGR_TEARDOWN_TCP = "\[  vmi = %s vn = %s security_policy_rule = %s remote_vn = %s is_client_session = %s is_si = %s vrouter_ip = %s sess_agg_info= \[  \[ \[  local_ip = %s service_port = %s protocol = %s ] \[  sampled_forward_bytes = %s sampled_forward_pkts = %s sampled_reverse_bytes = %s sampled_reverse_pkts = %s sessionMap= \[  \[ \[  ip = %s port = %s ] \[  forward_flow_info= \[ sampled_bytes = %s sampled_pkts = %s flow_uuid = %s tcp_flags = %s setup_time = %s teardown_time = %s teardown_bytes = %s teardown_pkts = %s action = %s sg_rule_uuid = %s nw_ace_uuid = %s underlay_source_port = %s ] reverse_flow_info= \[  sampled_bytes = %s sampled_pkts = %s flow_uuid = %s tcp_flags = %s setup_time = %s teardown_time = %s teardown_bytes = %s teardown_pkts = %s action = %s sg_rule_uuid = %s nw_ace_uuid = %s underlay_source_port = %s ] vm = %s other_vrouter_ip = %s underlay_proto = %s ],  \[  ip = %s port = %s ] \[  forward_flow_info= \[ sampled_bytes = %s sampled_pkts = %s flow_uuid = %s tcp_flags = %s setup_time = %s teardown_time = %s teardown_bytes = %s teardown_pkts = %s action = %s sg_rule_uuid = %s nw_ace_uuid = %s underlay_source_port = %s ] reverse_flow_info= \[  sampled_bytes = %s sampled_pkts = %s flow_uuid = %s tcp_flags = %s setup_time = %s teardown_time = %s teardown_bytes = %s teardown_pkts = %s action = %s sg_rule_uuid = %s nw_ace_uuid = %s underlay_source_port = %s ] vm = %s other_vrouter_ip = %s underlay_proto = %s ],  \[  ip = %s port = %s ] \[  forward_flow_info= \[ sampled_bytes = %s sampled_pkts = %s flow_uuid = %s tcp_flags = %s setup_time = %s teardown_time = %s teardown_bytes = %s teardown_pkts = %s action = %s sg_rule_uuid = %s nw_ace_uuid = %s underlay_source_port = %s ] reverse_flow_info= \[  sampled_bytes = %s sampled_pkts = %s flow_uuid = %s tcp_flags = %s setup_time = %s teardown_time = %s teardown_bytes = %s teardown_pkts = %s action = %s sg_rule_uuid = %s nw_ace_uuid = %s underlay_source_port = %s ] vm = %s other_vrouter_ip = %s underlay_proto = %s ],  ] ] ],  ] ] ]"

SESSION_SERVER_AGGR = SESSION_CLIENT_AGGR

LOGGED_SESSION = "\[  vmi = %s vn = %s security_policy_rule = %s remote_vn = %s is_client_session = %s is_si = %s vrouter_ip = %s sess_agg_info= \[  \[ \[  local_ip = %s service_port = %s protocol = %s ] \[   logged_forward_bytes = %s logged_forward_pkts = %s logged_reverse_bytes = %s logged_reverse_pkts = %s sessionMap= \[  \[ \[  ip = %s port = %s ] \[  forward_flow_info= \[  logged_bytes = %s logged_pkts = %s flow_uuid = %s tcp_flags = %s setup_time = %s action = %s sg_rule_uuid = %s nw_ace_uuid = %s underlay_source_port = %s ] reverse_flow_info= \[   logged_bytes = %s logged_pkts = %s flow_uuid = %s tcp_flags = %s setup_time = %s action = %s sg_rule_uuid = %s nw_ace_uuid = %s underlay_source_port = %s ] vm = %s other_vrouter_ip = %s underlay_proto = %s ],  ] ] ],  ] ] ]"

LOGGED_TEARDOWN = "\[  vmi = %s vn = %s security_policy_rule = %s remote_vn = %s is_client_session = %s is_si = %s vrouter_ip = %s sess_agg_info= \[  \[ \[  local_ip = %s service_port = %s protocol = %s ] \[   logged_forward_bytes = %s logged_forward_pkts = %s logged_reverse_bytes = %s logged_reverse_pkts = %s sessionMap= \[  \[ \[  ip = %s port = %s ] \[  forward_flow_info= \[  flow_uuid = %s setup_time = %s teardown_time = %s teardown_bytes = %s teardown_pkts = %s action = %s sg_rule_uuid = %s nw_ace_uuid = %s ] reverse_flow_info= \[   flow_uuid = %s setup_time = %s teardown_time = %s teardown_bytes = %s teardown_pkts = %s action = %s sg_rule_uuid = %s nw_ace_uuid = %s ] vm = %s other_vrouter_ip = %s underlay_proto = %s ],  ] ] ],  ] ] ]"

LOGGED_TEARDOWN_TCP = "\[  vmi = %s vn = %s security_policy_rule = %s remote_vn = %s is_client_session = %s is_si = %s vrouter_ip = %s sess_agg_info= \[  \[ \[  local_ip = %s service_port = %s protocol = %s ] \[   logged_forward_bytes = %s logged_forward_pkts = %s logged_reverse_bytes = %s logged_reverse_pkts = %s sessionMap= \[  \[ \[  ip = %s port = %s ] \[  forward_flow_info= \[  logged_bytes = %s logged_pkts = %s flow_uuid = %s tcp_flags = %s setup_time = %s teardown_time = %s teardown_bytes = %s teardown_pkts = %s action = %s sg_rule_uuid = %s nw_ace_uuid = %s underlay_source_port = %s ] reverse_flow_info= \[   logged_bytes = %s logged_pkts = %s flow_uuid = %s tcp_flags = %s setup_time = %s teardown_time = %s teardown_bytes = %s teardown_pkts = %s action = %s sg_rule_uuid = %s nw_ace_uuid = %s underlay_source_port = %s ] vm = %s other_vrouter_ip = %s underlay_proto = %s ],  ] ] ],  ] ] ]"

LOGGED_SYSLOG = "\[ vmi = %s vn = %s ] security_policy_rule = %s remote_vn = %s is_client_session = %s is_si = %s vrouter_ip = %s local_ip = %s service_port = %s protocol = %s  logged_forward_bytes = %s logged_forward_pkts = %s logged_reverse_bytes = %s ip = %s port = %s forward_flow_info= \[  logged_bytes = %s logged_pkts = %s flow_uuid = %s tcp_flags = %s setup_time = %s action = %s sg_rule_uuid = %s nw_ace_uuid = %s underlay_source_port = %s ] reverse_flow_info= \[   logged_bytes = %s logged_pkts = %s flow_uuid = %s tcp_flags = 0 setup_time = %s action = %s sg_rule_uuid = %s nw_ace_uuid = %s underlay_source_port = %s ] vm = %s other_vrouter_ip = %s underlay_proto = %s  ]"

class SessionLoggingBase(FlowTestBase, BaseIntrospectSsl):

    @classmethod
    def setUpClass(cls):
        super(SessionLoggingBase, cls).setUpClass()

    @classmethod
    def tearDownClass(cls):
        super(SessionLoggingBase, cls).tearDownClass()

    def _create_resources(self, test_type='intra-node', no_of_client=1,
            no_of_server=1, session_export_rate=-1):
        '''
            test_type: can be intra-node or inter-node
        '''
        compute_hosts = self.orch.get_hosts()
        if (len(compute_hosts) < 2) and (test_type == 'inter-node'):
            raise self.skipTest("Skipping test case,\
                                    this test needs atleast 2 compute nodes")

        self.setup_flow_export_rate(session_export_rate)

        node_name1 = compute_hosts[0]
        node_ip1 = self.inputs.compute_info[node_name1]
        node_name2 = compute_hosts[0]
        node_ip2 = self.inputs.compute_info[node_name2]

        if test_type == 'inter-node':
            node_name2 = compute_hosts[1]
            node_ip2 = self.inputs.compute_info[node_name2]

        self.vn_fixtures = self.create_vns(count=2)
        self.verify_vns(self.vn_fixtures)
        self.vn1_fixture = self.vn_fixtures[0]
        self.vn2_fixture = self.vn_fixtures[1]
        self.client_fixtures = self.create_vms(vn_fixture=self.vn1_fixture,
            count=no_of_client, node_name=node_name1, image_name='ubuntu-traffic')
        self.server_fixtures = self.create_vms(vn_fixture=self.vn2_fixture,
            count=no_of_server, node_name=node_name2, image_name='ubuntu-traffic')
        self.client_fixture = self.client_fixtures[0]
        self.server_fixture = self.server_fixtures[0]

        policy_name = 'policy1'
        policy_rules = [
            {
                'direction': '<>', 'simple_action': 'pass',
                'protocol': 'any',
                'source_network': self.vn1_fixture.vn_name,
                'dest_network': self.vn2_fixture.vn_name,
            }
        ]
        self.policy_fixture = self.useFixture(
            PolicyFixture(
                policy_name=policy_name,
                rules_list=policy_rules,
                inputs=self.inputs,
                connections=self.connections,
                api=True))

        vn1_policy_fixture = self.useFixture(
            VN_Policy_Fixture(
                connections=self.connections,
                vn_name=self.vn1_fixture.vn_name,
                policy_obj={self.vn1_fixture.vn_name : \
                           [self.policy_fixture.policy_obj]},
                vn_obj={self.vn1_fixture.vn_name : self.vn1_fixture},
                vn_policys=[policy_name],
                project_name=self.project.project_name))

        vn2_policy_fixture = self.useFixture(
            VN_Policy_Fixture(
                connections=self.connections,
                vn_name=self.vn2_fixture.vn_name,
                policy_obj={self.vn2_fixture.vn_name : \
                           [self.policy_fixture.policy_obj]},
                vn_obj={self.vn2_fixture.vn_name : self.vn2_fixture},
                vn_policys=[policy_name],
                project_name=self.project.project_name))

        self.verify_vms(self.client_fixtures + self.server_fixtures)

    def enable_logging_on_compute(self, node_ip, log_type,
            restart_on_cleanup=True):
        ''' Enable local logging on compute node
            log_type: can be agent/syslog
        '''
        container_name = 'agent'
        conf_file = '/etc/contrail/contrail-vrouter-agent.conf'
        service_name = 'contrail-vrouter-agent'
        #Take backup of original conf file to revert back later
        conf_file_backup = '/tmp/'+ get_random_name(conf_file.split('/')[-1])
        cmd = 'cp %s %s' % (conf_file, conf_file_backup)
        status = self.inputs.run_cmd_on_server(node_ip, cmd,
            container=container_name)

        self.addCleanup(
            self.restore_default_config_file, conf_file,
            conf_file_backup, service_name, node_ip, container_name,
            restart_on_cleanup)

        oper = 'set'
        section = 'DEFAULT'
        self.update_contrail_conf(service_name, oper, section,
            'log_flow', 1, node_ip, container_name)
        self.update_contrail_conf(service_name, oper, section,
            'log_local', 1, node_ip, container_name)
        self.update_contrail_conf(service_name, oper, section,
            'log_level', 'SYS_INFO', node_ip, container_name)

        if log_type == 'syslog':
            self.update_contrail_conf(service_name, oper, section,
                'use_syslog', 1, node_ip, container_name)

        self.inputs.restart_service(service_name, [node_ip],
            container=container_name, verify_service=True)
    #end enable_logging_on_compute

    def restore_default_config_file(self, conf_file, conf_file_backup,
            service_name, node_ip, container=None, restart_on_cleanup=True):
        '''Restore config file from conf_file_backup
            conf_file: full path of config file location
            conf_file_backup: full path of backup config file from where it will be restored
            service_name: service name
        '''
        cmd = "mv %s %s" % (conf_file_backup, conf_file)
        output = self.inputs.run_cmd_on_server(
            node_ip,
            cmd,
            container=container)

        if restart_on_cleanup:
            self.inputs.restart_service(service_name, [node_ip],
                container=container, verify_service=True)

    @retry(delay=1, tries=10)
    def search_session_in_log(self, log_file, node_ip, session_log,
            object_name='SessionEndpointObject'):
        '''Search session in log file on node node_ip'''

        container_name = 'agent'
        username = self.inputs.host_data[node_ip]['username']
        password = self.inputs.host_data[node_ip]['password']
        cmd = 'grep -a %s %s | grep -aP "%s"' % (object_name, log_file,
            session_log)
        output = self.inputs.run_cmd_on_server(
            node_ip, cmd, username, password, container=container_name)
        if not output:
            return False, None
        elif not re.search(session_log, output):
            return False, None
        else:
            self.logger.debug("\nSession Expected: %s, \nSession found: %s",
                session_log, output)
            return True, output

    def search_session_in_agent_log(self, node_ip, session_log):
        '''Search session in agent log file'''

        log_file = '/var/log/contrail/contrail-vrouter-agent.log*'
        object_name = 'SessionEndpointObject'
        return self.search_session_in_log(log_file, node_ip, session_log,
            object_name=object_name)

    def search_session_in_syslog(self, node_ip, session_log):
        '''Search session in syslog'''

        log_file = '/var/log/syslog*'
        object_name = 'SessionData'
        return self.search_session_in_log(log_file, node_ip, session_log,
            object_name=object_name)

    def start_traffic(self, client_fixture,
            server_fixture, proto=1):
        '''
        Starts the traffic for protocol proto, supported proto are tcp, udp and icmp
        '''

        self.pkt_count = 10
        self.pkt_count2 = INT_RE
        self.proto = proto

        if proto == 1:
            self.client_port = INT_RE
            self.service_port = 0 if (self.inputs.get_af() == 'v4') else 129
            self.srv_session_c_port = self.client_port
            self.srv_session_s_port = self.client_port
            self.proto = 1 if (self.inputs.get_af() == 'v4') else 58
            return client_fixture.ping_with_certainty(ip=server_fixture.vm_ip,
                count=self.pkt_count)
        elif proto == 17 or proto == 6:
            self.client_port = random.randint(12000, 65000)
            self.service_port = self.client_port + 1
            self.srv_session_c_port = self.client_port
            self.srv_session_s_port = self.service_port
            self.pkt_count = self.pkt_count2
            receiver = False if proto == 17 else True
            return self.send_nc_traffic(client_fixture, server_fixture,
                self.client_port, self.service_port, proto, receiver=receiver)
        else:
            return False

    def start_traffic_validate_sessions(self, client_fixture,
            server_fixture, policy_fixture=None, proto=1, underlay_proto=0):
        '''
        Start the traffic for protocol proto and validates the client and server
        sessions in agent log.
        Supported proto are tcp, udp and icmp
        '''
        assert self.start_traffic(client_fixture, server_fixture, proto)
        pkt_count = self.pkt_count
        pkt_count2 = self.pkt_count2
        client_port = self.client_port
        service_port = self.service_port
        srv_session_c_port = self.srv_session_c_port
        srv_session_s_port = self.srv_session_s_port
        proto = self.proto

        tcp_flags = 120 if proto == 6 else 0
        project_fqname = ':'.join(self.project.project_fq_name)
        client_vmi_fqname = project_fqname + ':' +\
            client_fixture.vmi_ids[client_fixture.vn_fq_name]
        is_client_session = 1
        if policy_fixture:
            policy_api_obj = self.vnc_lib.network_policy_read(
                id=policy_fixture.get_id())
            nw_ace_uuid = policy_api_obj.get_network_policy_entries(
                ).policy_rule[0].rule_uuid
        else:
            nw_ace_uuid = UUID_RE

        expected_client_session = SESSION_LOG % (
            client_vmi_fqname,
            client_fixture.vn_fq_name, FIREWALL_RULE_ID_DEFAULT,
            server_fixture.vn_fq_name, is_client_session, 0,
            client_fixture.vm_node_ip,
            client_fixture.vm_ip, service_port, proto,
            INT_RE, pkt_count2, INT_RE, pkt_count2,
            server_fixture.vm_ip, client_port,
            INT_RE, pkt_count2, UUID_RE, tcp_flags, INT_RE,#Fwd flow info
            'pass', UUID_RE, nw_ace_uuid, INT_RE,
            INT_RE, pkt_count2, UUID_RE, tcp_flags, INT_RE,#Reverse flow info
            'pass', UUID_RE, nw_ace_uuid, INT_RE,
            client_fixture.vm_id,
            server_fixture.vm_node_ip, underlay_proto)

        #Verify Client session
        result, output = self.search_session_in_agent_log(
            client_fixture.vm_node_ip,
            expected_client_session)
        assert result, ("Expected client session not found in agent log "
            "for protocol %s" % (proto))

        server_vmi_fqname = project_fqname + ':' +\
            server_fixture.vmi_ids[server_fixture.vn_fq_name]
        is_client_session = 0

        expected_server_session = SESSION_LOG % (
            server_vmi_fqname,
            server_fixture.vn_fq_name, FIREWALL_RULE_ID_DEFAULT,
            client_fixture.vn_fq_name, is_client_session, 0,
            server_fixture.vm_node_ip,
            server_fixture.vm_ip, srv_session_s_port, proto,
            INT_RE, pkt_count2, INT_RE, pkt_count2,
            client_fixture.vm_ip, srv_session_c_port,
            INT_RE, pkt_count2, UUID_RE, tcp_flags, INT_RE,
            'pass', UUID_RE, nw_ace_uuid, INT_RE,
            INT_RE, pkt_count2, UUID_RE, tcp_flags, INT_RE,
            'pass', UUID_RE, nw_ace_uuid, INT_RE,
            server_fixture.vm_id,
            client_fixture.vm_node_ip, underlay_proto)

        #Verify Server session
        result, output = self.search_session_in_agent_log(
            server_fixture.vm_node_ip,
            expected_server_session)
        assert result, ("Expected server session not found in agent log "
            "for protocol %s" % (proto))
        self.sleep(1)
        self.delete_all_flows_on_vms_compute([client_fixture, server_fixture])

        #Verify teardown sessions
        tcp_flags = 0
        expected_client_session = SESSION_TEARDOWN % (
            client_vmi_fqname,
            client_fixture.vn_fq_name, FIREWALL_RULE_ID_DEFAULT,
            server_fixture.vn_fq_name, 1, 0,
            client_fixture.vm_node_ip,
            client_fixture.vm_ip, service_port, proto,
            INT_RE, INT_RE, INT_RE, INT_RE,
            server_fixture.vm_ip, client_port,
            UUID_RE, INT_RE, INT_RE, INT_RE, pkt_count,
            'pass', UUID_RE, nw_ace_uuid,
            UUID_RE, INT_RE, INT_RE, INT_RE, pkt_count,
            'pass', UUID_RE, nw_ace_uuid,
            client_fixture.vm_id,
            server_fixture.vm_node_ip, underlay_proto)

        result, output = self.search_session_in_agent_log(
            client_fixture.vm_node_ip,
            expected_client_session)

        if ((not result) and (proto == 6)):
            expected_client_session = SESSION_TEARDOWN_TCP % (
                client_vmi_fqname,
                client_fixture.vn_fq_name, FIREWALL_RULE_ID_DEFAULT,
                server_fixture.vn_fq_name, 1, 0,
                client_fixture.vm_node_ip,
                client_fixture.vm_ip, service_port, proto,
                INT_RE, INT_RE, INT_RE, INT_RE,
                server_fixture.vm_ip, client_port,
                INT_RE, pkt_count, UUID_RE, tcp_flags, INT_RE,
                INT_RE, INT_RE, pkt_count,
                'pass', UUID_RE, nw_ace_uuid, INT_RE,
                INT_RE, pkt_count, UUID_RE, tcp_flags, INT_RE,
                INT_RE, INT_RE, pkt_count,
                'pass', UUID_RE, nw_ace_uuid, INT_RE,
                client_fixture.vm_id,
                server_fixture.vm_node_ip, underlay_proto)

            result_tcp, output = self.search_session_in_agent_log(
                client_fixture.vm_node_ip,
                expected_client_session)
            result = result or result_tcp

        assert result, ("Expected client session not found in agent log "
            "for protocol %s" % (proto))

        server_vmi_fqname = project_fqname + ':' +\
            server_fixture.vmi_ids[server_fixture.vn_fq_name]

        expected_server_session = SESSION_TEARDOWN % (
            server_vmi_fqname,
            server_fixture.vn_fq_name, FIREWALL_RULE_ID_DEFAULT,
            client_fixture.vn_fq_name, 0, 0,
            server_fixture.vm_node_ip,
            server_fixture.vm_ip, srv_session_s_port, proto,
            INT_RE, INT_RE, INT_RE, INT_RE,
            client_fixture.vm_ip, srv_session_c_port,
            UUID_RE, INT_RE, INT_RE, INT_RE, pkt_count,
            'pass', UUID_RE, nw_ace_uuid,
            UUID_RE, INT_RE, INT_RE, INT_RE, pkt_count,
            'pass', UUID_RE, nw_ace_uuid,
            server_fixture.vm_id,
            client_fixture.vm_node_ip, underlay_proto)

        result, output = self.search_session_in_agent_log(
            server_fixture.vm_node_ip,
            expected_server_session)

        if ((not result) and (proto == 6)):
            expected_server_session = SESSION_TEARDOWN_TCP % (
                server_vmi_fqname,
                server_fixture.vn_fq_name, FIREWALL_RULE_ID_DEFAULT,
                client_fixture.vn_fq_name, 0, 0,
                server_fixture.vm_node_ip,
                server_fixture.vm_ip, srv_session_s_port, proto,
                INT_RE, INT_RE, INT_RE, INT_RE,
                client_fixture.vm_ip, srv_session_c_port,
                INT_RE, pkt_count, UUID_RE, tcp_flags, INT_RE,
                INT_RE, INT_RE, pkt_count,
                'pass', UUID_RE, nw_ace_uuid, INT_RE,
                INT_RE, pkt_count, UUID_RE, tcp_flags, INT_RE,
                INT_RE, INT_RE, pkt_count,
                'pass', UUID_RE, nw_ace_uuid, INT_RE,
                server_fixture.vm_id,
                client_fixture.vm_node_ip, underlay_proto)

            result_tcp, output = self.search_session_in_agent_log(
                server_fixture.vm_node_ip,
                expected_server_session)
            result = result or result_tcp

        assert result, ("Expected server session not found in agent log "
            "for protocol %s" % (proto))

    def start_traffic_validate_sessions_in_syslog(self, client_fixture,
            server_fixture, policy_fixture=None, proto=1, underlay_proto=0):
        '''
        Start the traffic for protocol proto and validates the client and server
        sessions in syslog
        '''

        assert self.start_traffic(client_fixture, server_fixture, proto)
        pkt_count = self.pkt_count
        pkt_count2 = self.pkt_count2
        client_port = self.client_port
        service_port = self.service_port
        srv_session_c_port = self.srv_session_c_port
        srv_session_s_port = self.srv_session_s_port
        proto = self.proto

        tcp_flags = 120 if proto == 6 else 0
        project_fqname = ':'.join(self.project.project_fq_name)
        client_vmi_fqname = project_fqname + ':' +\
            client_fixture.vmi_ids[client_fixture.vn_fq_name]
        is_client_session = 1
        if policy_fixture:
            policy_api_obj = self.vnc_lib.network_policy_read(
                id=policy_fixture.get_id())
            nw_ace_uuid = policy_api_obj.get_network_policy_entries(
                ).policy_rule[0].rule_uuid
        else:
            nw_ace_uuid = UUID_RE

        expected_client_session = SESSION_SYSLOG % (
            client_vmi_fqname,
            client_fixture.vn_fq_name, FIREWALL_RULE_ID_DEFAULT,
            server_fixture.vn_fq_name, is_client_session, 0,
            client_fixture.vm_node_ip,
            client_fixture.vm_ip, service_port, proto,
            INT_RE, pkt_count2, INT_RE, pkt_count2,
            server_fixture.vm_ip, client_port,
            INT_RE, pkt_count2, UUID_RE, tcp_flags, INT_RE,
            'pass', UUID_RE, nw_ace_uuid, INT_RE,
            INT_RE, pkt_count2, UUID_RE, tcp_flags, INT_RE,
            'pass', UUID_RE, nw_ace_uuid, INT_RE,
            client_fixture.vm_id,
            server_fixture.vm_node_ip, underlay_proto)

        #Verify client session
        result, output = self.search_session_in_syslog(
            client_fixture.vm_node_ip,
            expected_client_session)
        assert result, ("Expected client session not found in syslog for "
            "protocol %s" % (proto))

        server_vmi_fqname = project_fqname + ':' +\
            server_fixture.vmi_ids[server_fixture.vn_fq_name]
        is_client_session = 0

        expected_server_session = SESSION_SYSLOG % (
            server_vmi_fqname,
            server_fixture.vn_fq_name, FIREWALL_RULE_ID_DEFAULT,
            client_fixture.vn_fq_name, is_client_session, 0,
            server_fixture.vm_node_ip,
            server_fixture.vm_ip, srv_session_s_port, proto,
            INT_RE, pkt_count2, INT_RE, pkt_count2,
            client_fixture.vm_ip, srv_session_c_port,
            INT_RE, pkt_count2, UUID_RE, tcp_flags, INT_RE,
            'pass', UUID_RE, nw_ace_uuid, INT_RE,
            INT_RE, pkt_count2, UUID_RE, tcp_flags, INT_RE,
            'pass', UUID_RE, nw_ace_uuid, INT_RE,
            server_fixture.vm_id,
            client_fixture.vm_node_ip, underlay_proto)

        #Verify server session
        result, output = self.search_session_in_syslog(
            server_fixture.vm_node_ip,
            expected_server_session)
        assert result, ("Expected server session not found in syslog for "
            "protocol %s" % (proto))

        self.sleep(1)
        self.delete_all_flows_on_vms_compute([client_fixture, server_fixture])

        #Verify teardown sessions
        tcp_flags = 0
        expected_client_session = SESSION_SYSLOG_TEARDOWN % (
            client_vmi_fqname,
            client_fixture.vn_fq_name, FIREWALL_RULE_ID_DEFAULT,
            server_fixture.vn_fq_name, 1, 0,
            client_fixture.vm_node_ip,
            client_fixture.vm_ip, service_port, proto,
            INT_RE, INT_RE, INT_RE, INT_RE,
            server_fixture.vm_ip, client_port,
            UUID_RE, INT_RE, INT_RE, INT_RE, pkt_count,
            'pass', UUID_RE, nw_ace_uuid,
            UUID_RE, INT_RE, INT_RE, INT_RE, pkt_count,
            'pass', UUID_RE, nw_ace_uuid,
            client_fixture.vm_id,
            server_fixture.vm_node_ip, underlay_proto)

        result, output = self.search_session_in_syslog(
            client_fixture.vm_node_ip,
            expected_client_session)

        if ((not result) and (proto == 6)):
            expected_client_session = SESSION_SYSLOG_TEARDOWN_TCP % (
                client_vmi_fqname,
                client_fixture.vn_fq_name, FIREWALL_RULE_ID_DEFAULT,
                server_fixture.vn_fq_name, 1, 0,
                client_fixture.vm_node_ip,
                client_fixture.vm_ip, service_port, proto,
                INT_RE, INT_RE, INT_RE, INT_RE,
                server_fixture.vm_ip, client_port,
                INT_RE, pkt_count2, UUID_RE, tcp_flags, INT_RE,
                INT_RE, INT_RE, pkt_count,
                'pass', UUID_RE, nw_ace_uuid, INT_RE,
                INT_RE, pkt_count2, UUID_RE, tcp_flags, INT_RE,
                INT_RE, INT_RE, pkt_count,
                'pass', UUID_RE, nw_ace_uuid, INT_RE,
                client_fixture.vm_id,
                server_fixture.vm_node_ip, underlay_proto)

            result_tcp, output = self.search_session_in_syslog(
                client_fixture.vm_node_ip,
                expected_client_session)
            result = result or result_tcp

        assert result, ("Expected client session not found in syslog for "
            "protocol %s" % (proto))

        server_vmi_fqname = project_fqname + ':' +\
            server_fixture.vmi_ids[server_fixture.vn_fq_name]

        expected_server_session = SESSION_SYSLOG_TEARDOWN % (
            server_vmi_fqname,
            server_fixture.vn_fq_name, FIREWALL_RULE_ID_DEFAULT,
            client_fixture.vn_fq_name, 0, 0,
            server_fixture.vm_node_ip,
            server_fixture.vm_ip, srv_session_s_port, proto,
            INT_RE, INT_RE, INT_RE, INT_RE,
            client_fixture.vm_ip, srv_session_c_port,
            UUID_RE, INT_RE, INT_RE, INT_RE, pkt_count,
            'pass', UUID_RE, nw_ace_uuid,
            UUID_RE, INT_RE, INT_RE, INT_RE, pkt_count,
            'pass', UUID_RE, nw_ace_uuid,
            server_fixture.vm_id,
            client_fixture.vm_node_ip, underlay_proto)

        result, output = self.search_session_in_syslog(
            server_fixture.vm_node_ip,
            expected_server_session)

        if ((not result) and (proto == 6)):
            expected_server_session = SESSION_SYSLOG_TEARDOWN_TCP % (
                server_vmi_fqname,
                server_fixture.vn_fq_name, FIREWALL_RULE_ID_DEFAULT,
                client_fixture.vn_fq_name, 0, 0,
                server_fixture.vm_node_ip,
                server_fixture.vm_ip, srv_session_s_port, proto,
                INT_RE, INT_RE, INT_RE, INT_RE,
                client_fixture.vm_ip, srv_session_c_port,
                INT_RE, pkt_count2, UUID_RE, tcp_flags, INT_RE,
                INT_RE, INT_RE, pkt_count,
                'pass', UUID_RE, nw_ace_uuid, INT_RE,
                INT_RE, pkt_count2, UUID_RE, tcp_flags, INT_RE,
                INT_RE, INT_RE, pkt_count,
                'pass', UUID_RE, nw_ace_uuid, INT_RE,
                server_fixture.vm_id,
                client_fixture.vm_node_ip, underlay_proto)

            result_tcp, output = self.search_session_in_syslog(
                server_fixture.vm_node_ip,
                expected_server_session)
            result = result or result_tcp

        assert result, ("Expected server session not found in syslog for "
            "protocol %s" % (proto))

    def start_traffic_validate_slo_in_syslog(self, client_fixture,
            server_fixture, policy_fixture=None, proto=1, underlay_proto=0,
            slo_rate=1, sg_uuid=None, exp_session_count=None):
        '''
        Start the traffic for protocol proto and validates the client and server
        SLO sessions in syslog
        '''

        assert self.start_traffic(client_fixture, server_fixture, proto)
        pkt_count = self.pkt_count
        pkt_count2 = self.pkt_count2
        client_port = self.client_port
        service_port = self.service_port
        srv_session_c_port = self.srv_session_c_port
        srv_session_s_port = self.srv_session_s_port
        proto = self.proto
        if exp_session_count is None:
            exp_session_count = pkt_count/slo_rate if proto == 1 else 1

        eth_type = 'IPv4' if (self.inputs.get_af() == 'v4') else 'IPv6'
        proto_str = 'any'
        if sg_uuid is not None:
            sg_rule_id_ingress = list_sg_rules(self.connections, sg_uuid,
                eth_type=eth_type, proto=proto_str, direction='ingress')[0]['id']
            sg_rule_id_egress = list_sg_rules(self.connections, sg_uuid,
                eth_type=eth_type, proto=proto_str, direction='egress')[0]['id']
        else:
            sg_rule_id_ingress = sg_rule_id_egress = UUID_RE

        tcp_flags = 120 if proto == 6 else 0
        project_fqname = ':'.join(self.project.project_fq_name)
        client_vmi_fqname = project_fqname + ':' +\
            client_fixture.vmi_ids[client_fixture.vn_fq_name]
        is_client_session = 1
        if policy_fixture:
            policy_api_obj = self.vnc_lib.network_policy_read(
                id=policy_fixture.get_id())
            nw_ace_uuid = policy_api_obj.get_network_policy_entries(
                ).policy_rule[0].rule_uuid
        else:
            nw_ace_uuid = UUID_RE

        expected_client_session = LOGGED_SYSLOG % (
            client_vmi_fqname,
            client_fixture.vn_fq_name, FIREWALL_RULE_ID_DEFAULT,
            server_fixture.vn_fq_name, is_client_session, 0,
            client_fixture.vm_node_ip,
            client_fixture.vm_ip, service_port, proto,
            INT_RE, pkt_count2, INT_RE, pkt_count2,
            server_fixture.vm_ip, client_port,
            INT_RE, pkt_count2, UUID_RE, tcp_flags, INT_RE,
            'pass', sg_rule_id_egress, nw_ace_uuid, INT_RE,
            INT_RE, pkt_count2, UUID_RE, tcp_flags, INT_RE,
            'pass', sg_rule_id_egress, nw_ace_uuid, INT_RE,
            client_fixture.vm_id,
            server_fixture.vm_node_ip, underlay_proto)

        #Verify client session
        result, output = self.verify_no_of_sessions_in_syslog(
            client_fixture.vm_node_ip,
            expected_client_session, exp_session_count)
        assert result, ("Expected No. of client session not found in syslog for "
            "protocol %s" % (proto))

        server_vmi_fqname = project_fqname + ':' +\
            server_fixture.vmi_ids[server_fixture.vn_fq_name]
        is_client_session = 0

        expected_server_session = LOGGED_SYSLOG % (
            server_vmi_fqname,
            server_fixture.vn_fq_name, FIREWALL_RULE_ID_DEFAULT,
            client_fixture.vn_fq_name, is_client_session, 0,
            server_fixture.vm_node_ip,
            server_fixture.vm_ip, srv_session_s_port, proto,
            INT_RE, pkt_count2, INT_RE, pkt_count2,
            client_fixture.vm_ip, srv_session_c_port,
            INT_RE, pkt_count2, UUID_RE, tcp_flags, INT_RE,
            'pass', sg_rule_id_ingress, nw_ace_uuid, INT_RE,
            INT_RE, pkt_count2, UUID_RE, tcp_flags, INT_RE,
            'pass', sg_rule_id_ingress, nw_ace_uuid, INT_RE,
            server_fixture.vm_id,
            client_fixture.vm_node_ip, underlay_proto)

        #Verify server session
        result, output = self.verify_no_of_sessions_in_syslog(
            server_fixture.vm_node_ip,
            expected_server_session)
        assert result, ("Expected No. of server session not found in syslog for "
            "protocol %s" % (proto))

        self.sleep(1)
        self.delete_all_flows_on_vms_compute([client_fixture, server_fixture])

        #Verify teardown sessions
        #TBD
        tcp_flags = 0
        expected_client_session = SESSION_SYSLOG_TEARDOWN % (
            client_vmi_fqname,
            client_fixture.vn_fq_name, FIREWALL_RULE_ID_DEFAULT,
            server_fixture.vn_fq_name, 1, 0,
            client_fixture.vm_node_ip,
            client_fixture.vm_ip, service_port, proto,
            INT_RE, INT_RE, INT_RE, INT_RE,
            server_fixture.vm_ip, client_port,
            UUID_RE, INT_RE, INT_RE, INT_RE, pkt_count,
            'pass', UUID_RE, nw_ace_uuid,
            UUID_RE, INT_RE, INT_RE, INT_RE, pkt_count,
            'pass', UUID_RE, nw_ace_uuid,
            client_fixture.vm_id,
            server_fixture.vm_node_ip, underlay_proto)

        result, output = self.search_session_in_syslog(
            client_fixture.vm_node_ip,
            expected_client_session)

        if ((not result) and (proto == 6)):
            expected_client_session = SESSION_SYSLOG_TEARDOWN_TCP % (
                client_vmi_fqname,
                client_fixture.vn_fq_name, FIREWALL_RULE_ID_DEFAULT,
                server_fixture.vn_fq_name, 1, 0,
                client_fixture.vm_node_ip,
                client_fixture.vm_ip, service_port, proto,
                INT_RE, INT_RE, INT_RE, INT_RE,
                server_fixture.vm_ip, client_port,
                INT_RE, pkt_count2, UUID_RE, tcp_flags, INT_RE,
                INT_RE, INT_RE, pkt_count,
                'pass', UUID_RE, nw_ace_uuid, INT_RE,
                INT_RE, pkt_count2, UUID_RE, tcp_flags, INT_RE,
                INT_RE, INT_RE, pkt_count,
                'pass', UUID_RE, nw_ace_uuid, INT_RE,
                client_fixture.vm_id,
                server_fixture.vm_node_ip, underlay_proto)

            result_tcp, output = self.search_session_in_syslog(
                client_fixture.vm_node_ip,
                expected_client_session)
            result = result or result_tcp

        assert result, ("Expected client session not found in syslog for "
            "protocol %s" % (proto))

        server_vmi_fqname = project_fqname + ':' +\
            server_fixture.vmi_ids[server_fixture.vn_fq_name]

        expected_server_session = SESSION_SYSLOG_TEARDOWN % (
            server_vmi_fqname,
            server_fixture.vn_fq_name, FIREWALL_RULE_ID_DEFAULT,
            client_fixture.vn_fq_name, 0, 0,
            server_fixture.vm_node_ip,
            server_fixture.vm_ip, srv_session_s_port, proto,
            INT_RE, INT_RE, INT_RE, INT_RE,
            client_fixture.vm_ip, srv_session_c_port,
            UUID_RE, INT_RE, INT_RE, INT_RE, pkt_count,
            'pass', UUID_RE, nw_ace_uuid,
            UUID_RE, INT_RE, INT_RE, INT_RE, pkt_count,
            'pass', UUID_RE, nw_ace_uuid,
            server_fixture.vm_id,
            client_fixture.vm_node_ip, underlay_proto)

        result, output = self.search_session_in_syslog(
            server_fixture.vm_node_ip,
            expected_server_session)

        if ((not result) and (proto == 6)):
            expected_server_session = SESSION_SYSLOG_TEARDOWN_TCP % (
                server_vmi_fqname,
                server_fixture.vn_fq_name, FIREWALL_RULE_ID_DEFAULT,
                client_fixture.vn_fq_name, 0, 0,
                server_fixture.vm_node_ip,
                server_fixture.vm_ip, srv_session_s_port, proto,
                INT_RE, INT_RE, INT_RE, INT_RE,
                client_fixture.vm_ip, srv_session_c_port,
                INT_RE, pkt_count2, UUID_RE, tcp_flags, INT_RE,
                INT_RE, INT_RE, pkt_count,
                'pass', UUID_RE, nw_ace_uuid, INT_RE,
                INT_RE, pkt_count2, UUID_RE, tcp_flags, INT_RE,
                INT_RE, INT_RE, pkt_count,
                'pass', UUID_RE, nw_ace_uuid, INT_RE,
                server_fixture.vm_id,
                client_fixture.vm_node_ip, underlay_proto)

            result_tcp, output = self.search_session_in_syslog(
                server_fixture.vm_node_ip,
                expected_server_session)
            result = result or result_tcp

        assert result, ("Expected server session not found in syslog for "
            "protocol %s" % (proto))

    def start_traffic_validate_slo(self, client_fixture,
            server_fixture, policy_fixture=None, proto=1, underlay_proto=0,
            slo_rate=1, sg_uuid=None, exp_session_count=None):
        '''
        Start the traffic for protocol proto and validates the client and server
        sessions logged matching SLO in agent log.
        Supported protocols are 1, 58, 17 and 6
        '''

        assert self.start_traffic(client_fixture, server_fixture, proto)
        pkt_count = self.pkt_count
        pkt_count2 = self.pkt_count2
        client_port = self.client_port
        service_port = self.service_port
        srv_session_c_port = self.srv_session_c_port
        srv_session_s_port = self.srv_session_s_port
        proto = self.proto
        if exp_session_count is None:
            exp_session_count = pkt_count/slo_rate if proto == 1 else 1

        eth_type = 'IPv4' if (self.inputs.get_af() == 'v4') else 'IPv6'
        proto_str = 'any'
        if sg_uuid is not None:
            sg_rule_id_ingress = list_sg_rules(self.connections, sg_uuid,
                eth_type=eth_type, proto=proto_str, direction='ingress')[0]['id']
            sg_rule_id_egress = list_sg_rules(self.connections, sg_uuid,
                eth_type=eth_type, proto=proto_str, direction='egress')[0]['id']
        else:
            sg_rule_id_ingress = sg_rule_id_egress = UUID_RE

        tcp_flags = 120 if proto == 6 else 0
        project_fqname = ':'.join(self.project.project_fq_name)
        client_vmi_fqname = project_fqname + ':' +\
            client_fixture.vmi_ids[client_fixture.vn_fq_name]
        is_client_session = 1
        if policy_fixture:
            policy_api_obj = self.vnc_lib.network_policy_read(
                id=policy_fixture.get_id())
            nw_ace_uuid = policy_api_obj.get_network_policy_entries(
                ).policy_rule[0].rule_uuid
        else:
            nw_ace_uuid = UUID_RE

        expected_client_session = LOGGED_SESSION % (
            client_vmi_fqname,
            client_fixture.vn_fq_name, FIREWALL_RULE_ID_DEFAULT,
            server_fixture.vn_fq_name, is_client_session, 0,
            client_fixture.vm_node_ip,
            client_fixture.vm_ip, service_port, proto,
            INT_RE, pkt_count2, INT_RE, pkt_count2,
            server_fixture.vm_ip, client_port,
            INT_RE, pkt_count2, UUID_RE, tcp_flags, INT_RE,#Fwd flow info
            'pass', sg_rule_id_egress, nw_ace_uuid, INT_RE,
            INT_RE, pkt_count2, UUID_RE, tcp_flags, INT_RE,#Reverse flow info
            'pass', sg_rule_id_egress, nw_ace_uuid, INT_RE,
            client_fixture.vm_id,
            server_fixture.vm_node_ip, underlay_proto)

        self.sleep(1)
        #Verify No. of Client sessions
        result, output = self.verify_no_of_sessions_in_agent_log(
            client_fixture.vm_node_ip,
            expected_client_session, exp_session_count)
        assert result, ("Expected no. of client session not found in agent log "
            "for protocol %s, exp:%s, got:%s" % (proto, exp_session_count,
            output))

        server_vmi_fqname = project_fqname + ':' +\
            server_fixture.vmi_ids[server_fixture.vn_fq_name]
        is_client_session = 0

        expected_server_session = LOGGED_SESSION % (
            server_vmi_fqname,
            server_fixture.vn_fq_name, FIREWALL_RULE_ID_DEFAULT,
            client_fixture.vn_fq_name, is_client_session, 0,
            server_fixture.vm_node_ip,
            server_fixture.vm_ip, srv_session_s_port, proto,
            INT_RE, pkt_count2, INT_RE, pkt_count2,
            client_fixture.vm_ip, srv_session_c_port,
            INT_RE, pkt_count2, UUID_RE, tcp_flags, INT_RE,
            'pass', sg_rule_id_ingress, nw_ace_uuid, INT_RE,
            INT_RE, pkt_count2, UUID_RE, tcp_flags, INT_RE,
            'pass', sg_rule_id_ingress, nw_ace_uuid, INT_RE,
            server_fixture.vm_id,
            client_fixture.vm_node_ip, underlay_proto)

        #Verify No. of Server sessions
        result, output = self.verify_no_of_sessions_in_agent_log(
            server_fixture.vm_node_ip,
            expected_server_session, exp_session_count)
        assert result, ("Expected no. of server sessions not found in agent log"
            " for protocol %s, exp:%s, got:%s" % (proto, exp_session_count,
            output))

        self.sleep(1)
        self.delete_all_flows_on_vms_compute([client_fixture, server_fixture])

        #Verify teardown sessions
        tcp_flags = 0
        expected_client_session = LOGGED_TEARDOWN % (
            client_vmi_fqname,
            client_fixture.vn_fq_name, FIREWALL_RULE_ID_DEFAULT,
            server_fixture.vn_fq_name, 1, 0,
            client_fixture.vm_node_ip,
            client_fixture.vm_ip, service_port, proto,
            0, 0, 0, 0,
            server_fixture.vm_ip, client_port,
            UUID_RE, INT_RE, INT_RE, INT_RE, pkt_count,#Fwd flow
            'pass', sg_rule_id_egress, nw_ace_uuid,
            UUID_RE, INT_RE, INT_RE, INT_RE, pkt_count,#Reverse flow
            'pass', sg_rule_id_egress, nw_ace_uuid,
            client_fixture.vm_id,
            server_fixture.vm_node_ip, underlay_proto)

        result, output = self.search_session_in_agent_log(
            client_fixture.vm_node_ip,
            expected_client_session)

        if ((not result) and (proto == 6)):
            expected_client_session = LOGGED_TEARDOWN_TCP % (
                client_vmi_fqname,
                client_fixture.vn_fq_name, FIREWALL_RULE_ID_DEFAULT,
                server_fixture.vn_fq_name, 1, 0,
                client_fixture.vm_node_ip,
                client_fixture.vm_ip, service_port, proto,
                INT_RE, INT_RE, INT_RE, INT_RE,
                server_fixture.vm_ip, client_port,
                INT_RE, INT_RE,
                UUID_RE, tcp_flags, INT_RE, INT_RE, INT_RE, pkt_count,#Fwd flow
                'pass', sg_rule_id_egress, nw_ace_uuid, INT_RE,
                INT_RE, INT_RE,
                UUID_RE, tcp_flags, INT_RE, INT_RE, INT_RE, pkt_count,#Reverse flow
                'pass', sg_rule_id_egress, nw_ace_uuid, INT_RE,
                client_fixture.vm_id,
                server_fixture.vm_node_ip, underlay_proto)

            result_tcp, output = self.search_session_in_agent_log(
                client_fixture.vm_node_ip,
                expected_client_session)
            result = result or result_tcp

        assert result, ("Expected client session not found in agent log "
            "for protocol %s" % (proto))

        server_vmi_fqname = project_fqname + ':' +\
            server_fixture.vmi_ids[server_fixture.vn_fq_name]

        expected_server_session = LOGGED_TEARDOWN % (
            server_vmi_fqname,
            server_fixture.vn_fq_name, FIREWALL_RULE_ID_DEFAULT,
            client_fixture.vn_fq_name, 0, 0,
            server_fixture.vm_node_ip,
            server_fixture.vm_ip, srv_session_s_port, proto,
            0, 0, 0, 0,
            client_fixture.vm_ip, srv_session_c_port,
            UUID_RE, INT_RE, INT_RE, INT_RE, pkt_count,
            'pass', sg_rule_id_ingress, nw_ace_uuid,
            UUID_RE, INT_RE, INT_RE, INT_RE, pkt_count,
            'pass', sg_rule_id_ingress, nw_ace_uuid,
            server_fixture.vm_id,
            client_fixture.vm_node_ip, underlay_proto)

        result, output = self.search_session_in_agent_log(
            server_fixture.vm_node_ip,
            expected_server_session)

        if ((not result) and (proto == 6)):
            expected_server_session = LOGGED_TEARDOWN_TCP % (
                server_vmi_fqname,
                server_fixture.vn_fq_name, FIREWALL_RULE_ID_DEFAULT,
                client_fixture.vn_fq_name, 0, 0,
                server_fixture.vm_node_ip,
                server_fixture.vm_ip, srv_session_s_port, proto,
                INT_RE, INT_RE, INT_RE, INT_RE,
                client_fixture.vm_ip, srv_session_c_port,
                INT_RE, pkt_count2, UUID_RE, tcp_flags, INT_RE,
                INT_RE, INT_RE, pkt_count,
                'pass', sg_rule_id_ingress, nw_ace_uuid, INT_RE,
                INT_RE, pkt_count2, UUID_RE, tcp_flags, INT_RE,
                INT_RE, INT_RE, pkt_count,
                'pass', sg_rule_id_ingress, nw_ace_uuid, INT_RE,
                server_fixture.vm_id,
                client_fixture.vm_node_ip, underlay_proto)

            result_tcp, output = self.search_session_in_agent_log(
                server_fixture.vm_node_ip,
                expected_server_session)
            result = result or result_tcp

        assert result, ("Expected server session not found in agent log "
            "for protocol %s" % (proto))

    @retry(delay=1, tries=10)
    def verify_no_of_sessions_in_log(self, node_ip, log_type, session_log,
            exp_session_count=None):
        ''' Verify No. of sessions on compute node for given log type
            log_type: agent/syslog
        '''
        container_name = 'agent'
        if log_type == 'agent':
            log_file = '/var/log/contrail/contrail-vrouter-agent.log*'
            object_name = 'SessionEndpointObject'
        elif log_type == 'syslog':
            log_file = '/var/log/syslog*'
            object_name = 'SessionData'

        username = self.inputs.host_data[node_ip]['username']
        password = self.inputs.host_data[node_ip]['password']
        cmd = 'grep -a %s %s | grep -aP "%s" | wc -l' % (object_name,
            log_file, session_log)
        output = self.inputs.run_cmd_on_server(
            node_ip, cmd, username, password, container=container_name)

        if exp_session_count is not None:
            return (exp_session_count == int(output)), int(output)
        else:
            return True, int(output)

    def verify_no_of_sessions_in_agent_log(self, node_ip, session_log,
            exp_session_count=None):

        return self.verify_no_of_sessions_in_log(node_ip, 'agent', session_log,
            exp_session_count=exp_session_count)

    def verify_no_of_sessions_in_syslog(self, node_ip, session_log,
            exp_session_count=None):

        return self.verify_no_of_sessions_in_log(node_ip, 'syslog', session_log,
            exp_session_count=exp_session_count)

    def get_total_no_of_sessions_in_agent_log(self, node_ip):
        '''Returns total no. of sessions in agent log file'''
        log_file = '/var/log/contrail/contrail-vrouter-agent.log*'
        container_name = 'agent'

        username = self.inputs.host_data[node_ip]['username']
        password = self.inputs.host_data[node_ip]['password']
        cmd = "grep -a SessionEndpointObject %s" % (log_file) +\
            "| grep -ao \" ip = \"| wc -l"
        output = self.inputs.run_cmd_on_server(
            node_ip, cmd, username, password, container=container_name)

        return int(output)

    def clear_log_file(self, node_ip, log_file=None):
        '''Clears log file'''
        log_file = log_file or '/var/log/contrail/contrail-vrouter-agent.log'
        container_name = 'agent'

        username = self.inputs.host_data[node_ip]['username']
        password = self.inputs.host_data[node_ip]['password']
        cmd = 'rm %s.*;echo \'\' > %s' % (log_file, log_file)
        output = self.inputs.run_cmd_on_server(
            node_ip, cmd, username, password, container=container_name)
