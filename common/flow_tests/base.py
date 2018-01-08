import re

from common.vrouter.base import BaseVrouterTest
from tcutils.util import get_random_name, retry
import random

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

class FlowTestBase(BaseVrouterTest):

    @classmethod
    def setUpClass(cls):
        super(FlowTestBase, cls).setUpClass()

    @classmethod
    def tearDownClass(cls):
        super(FlowTestBase, cls).tearDownClass()
    # end tearDownClass


    def get_flows_exported(self, agent_name, last="1m"):
        ''' agent_name is of format nodek1:Compute:contrail-vrouter-agent:0
        '''
        # TODO
        # Use test-code's api to do query instead of running contrail-stats cmd
        cmd = '''contrail-stats --table SandeshMessageStat.msg_info --select \
"SUM(msg_info.messages)" --last %s --where \
'name=%s' 'msg_info.type=FlowLogDataObject' | tail -1'''  % (last, agent_name)
        output = self.inputs.run_cmd_on_server(self.inputs.collector_ips[0],
                                               cmd, container='analytics')
        digits = re.findall('\d+', output)
        if digits:
            return digits[0]
        else:
            self.logger.debug('No flows seen in collector for cmd %s' % (cmd))
            return None
    # end get_flows_exported

    def get_sessions_exported(self, node_ip, start_time, end_time):
        '''
            Gets the total sessions exported within mentioned time range
            by a particular vrouter node
        '''
        table_name = "SessionSeriesTable"
        select_fields = ["forward_action", "sample_count", "vrouter_ip"]

        sessions_exported = 0
        res_s = self.ops_inspect[self.inputs.collector_ips[0]].post_query(
            table_name, start_time=start_time, end_time=end_time,
            select_fields=select_fields, session_type='server')

        res_c = self.ops_inspect[self.inputs.collector_ips[0]].post_query(
            table_name, start_time=start_time, end_time=end_time,
            select_fields=select_fields, session_type='client')

        self.logger.debug("Server sessions: %s\n Client sessions: %s" % (
            res_s, res_c))
        for record in res_s:
            if node_ip == record['vrouter_ip']:
                sessions_exported += record['sample_count']
        for record in res_c:
            if node_ip == record['vrouter_ip']:
                sessions_exported += record['sample_count']
        if not sessions_exported:
            self.logger.debug("No sessions exported from the vrouter %s"\
                " in last %s seconds" % (node_ip, last))

        return sessions_exported

    def setup_flow_export_rate(self, value):
        ''' Set flow export rate and handle the cleanup
        '''
        vnc_lib_fixture = self.connections.vnc_lib_fixture
        current_rate = vnc_lib_fixture.get_flow_export_rate()
        vnc_lib_fixture.set_flow_export_rate(value)
        self.addCleanup(vnc_lib_fixture.set_flow_export_rate, current_rate)
    # end setup_flow_export_rate

    def enable_logging_on_compute(self, node_ip, log_type,
            restart_on_cleanup=True):

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

        cmd = "mv %s %s" % (conf_file_backup, conf_file)
        output = self.inputs.run_cmd_on_server(
            node_ip,
            cmd,
            container=container)

        if restart_on_cleanup:
            self.inputs.restart_service(service_name, [node_ip],
                container=container, verify_service=True)

    @retry(delay=1, tries=10)
    def search_session_in_agent_log(self, node_ip, session_log):

        log_file = '/var/log/contrail/contrail-vrouter-agent.log*'
        container_name = 'agent'

        username = self.inputs.host_data[node_ip]['username']
        password = self.inputs.host_data[node_ip]['password']
        cmd = 'grep -a SessionEndpointObject %s | grep -aP "%s"' % (log_file,
            session_log)
        output = self.inputs.run_cmd_on_server(
            node_ip, cmd, username, password, container=container_name)

        if not output:
            return False, None
        else:
            self.logger.debug("\nSession Expected: %s, \nSession found: %s",
                session_log, output)
            return True, output

    @retry(delay=1, tries=10)
    def search_session_in_syslog(self, node_ip, session_log):

        log_file = '/var/log/syslog*'
        container_name = 'agent'

        username = self.inputs.host_data[node_ip]['username']
        password = self.inputs.host_data[node_ip]['password']
        cmd = 'grep -a SessionData %s | grep -aP "%s"' % (log_file,
            session_log)
        output = self.inputs.run_cmd_on_server(
            node_ip, cmd, username, password, container=container_name)

        if not output:
            return False, None
        else:
            self.logger.debug("\nSession Expected: %s, \nSession found: %s",
                session_log, output)
            return True, output

    def start_traffic_validate_sessions(self, client_fixture,
            server_fixture, policy_fixture=None, proto=1, underlay_proto=0):
        '''
        Start the traffic for protocol proto and validates the client and server
        sessions in agent log.
        Supported proto are tcp, udp and icmp
        '''

        pkt_count = 10
        pkt_count2 = INT_RE

        if proto == 1:
            client_port = INT_RE
            service_port = 0 if (self.inputs.get_af() == 'v4') else 129
            srv_session_c_port = client_port
            srv_session_s_port = client_port
            proto = 1 if (self.inputs.get_af() == 'v4') else 58
            assert client_fixture.ping_with_certainty(ip=server_fixture.vm_ip,
                count=pkt_count)
        elif proto == 17 or proto == 6:
            client_port = random.randint(12000, 65000)
            service_port = client_port + 1
            srv_session_c_port = client_port
            srv_session_s_port = service_port
            pkt_count = pkt_count2
            receiver = False if proto == 17 else True
            assert self.send_nc_traffic(client_fixture, server_fixture,
                client_port, service_port, proto, receiver=receiver)
        else:
            return False

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

        pkt_count = 10
        pkt_count2 = INT_RE

        if proto == 1:
            client_port = INT_RE
            service_port = 0 if (self.inputs.get_af() == 'v4') else 129
            srv_session_c_port = client_port
            srv_session_s_port = client_port
            proto = 1 if (self.inputs.get_af() == 'v4') else 58
            assert client_fixture.ping_with_certainty(ip=server_fixture.vm_ip,
                count=pkt_count)
        elif proto == 17 or proto == 6:
            client_port = random.randint(12000, 65000)
            service_port = client_port + 1
            srv_session_c_port = client_port
            srv_session_s_port = service_port
            pkt_count = pkt_count2
            receiver = False if proto == 17 else True
            assert self.send_nc_traffic(client_fixture, server_fixture,
                client_port, service_port, proto, receiver=receiver)
        else:
            return False

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
