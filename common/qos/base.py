import re

from common.neutron.base import BaseNeutronTest
from compute_node_test import ComputeNodeFixture
from qos_fixture import QosForwardingClassFixture, QosConfigFixture

from tcutils.traffic_utils.traffic_analyzer import TrafficAnalyzer
from tcutils.traffic_utils.scapy_traffic_gen import ScapyTraffic
from tcutils.traffic_utils.hping_traffic import Hping3

from time import sleep
from netaddr import *

class QosTestBase(BaseNeutronTest):

    @classmethod
    def setUpClass(cls):
        super(QosTestBase, cls).setUpClass()

    @classmethod
    def tearDownClass(cls):
        super(QosTestBase, cls).tearDownClass()
    # end tearDownClass

    def setup_fcs(self, fcs_list):
        fc_fixtures = []
        for fc_dict in fcs_list:
            fc_dict['connections'] = self.connections
            fc_fixture = self.useFixture(
                            QosForwardingClassFixture(**fc_dict))
            fc_fixtures.append(fc_fixture)
        return fc_fixtures
    # end 

    def setup_qos_config(self, name=None, dscp_map={}, dot1p_map={}, exp_map={},
                          **kwargs):
        ''' Helper to add and delete qos-config and forwarding-class objects
        '''
        qos_config_fixture = self.useFixture(QosConfigFixture(name=name,
                                             dscp_mapping=dscp_map,
                                             dot1p_mapping=dot1p_map,
                                             exp_mapping=exp_map,
                                             connections=self.connections,
                                             **kwargs))
        return qos_config_fixture
    # end setup_qos_config 

    def setup_qos_config_on_vmi(self, qos_fixture, vmi_uuid):
        ret_val = qos_fixture.apply_to_vmi(vmi_uuid)
        self.addCleanup(qos_fixture.remove_from_vmi, vmi_uuid)
        return ret_val
    # end setup_qos_config_on_vmi

    def remove_qos_config_on_vmi(self, qos_fixture, vmi_uuid):
        self._remove_from_cleanup(qos_fixture.remove_from_vmi, vmi_uuid)
        return qos_fixture.remove_from_vmi(vmi_uuid)

    def setup_qos_config_on_vn(self, qos_fixture, vn_uuid):
        ret_val = qos_fixture.apply_to_vn(vn_uuid)
        self.addCleanup(qos_fixture.remove_from_vn, vn_uuid)
        return ret_val
    # end setup_qos_config_on_vn

    def remove_qos_config_on_vn(self, qos_fixture, vn_uuid):
        self._remove_from_cleanup(qos_fixture.remove_from_vn, vn_uuid)
        return qos_fixture.remove_from_vn(vn_uuid)

    def delete_qos_config(self, qos_fixture):
        qos_fixture.cleanUp()
        self._remove_from_cleanup(qos_fixture.cleanUp)
    # end delete_qos_config
    
    def validate_packet_qos_marking(self,
                                    src_vm_fixture,
                                    dest_vm_fixture,
                                    traffic_generator = "hping",
                                    dest_ip=None,
                                    count=30000,
                                    dscp=None,
                                    dot1p=None,
                                    exp=None,
                                    protocol='udp',
                                    src_port=None,
                                    dest_port=None,
                                    src_compute_fixture=None,
                                    expected_dscp=None,
                                    expected_dot1p=None,
                                    expected_exp=None,
                                    encap = None,
                                    vrf_id = None,
                                    af = "ipv4",
                                    **kwargs):
        '''
            dest_compute_fixture should be supplied if underlay traffic is 
            being checked
            dest_vm_fixture should be supplied if traffic is being checked for a
            specific estination VM
            
            Few things to note:
            1. traffic_generator can be "scapy" or "hping"
            2. "scapy" is specifically used here to test l2 and IPv6 traffic only.
               For all other traffic, hping is being used.
        '''
        interval = kwargs.get('interval', 1)
        src_mac = kwargs.get('src_mac', "11:22:33:44:55:66")
        dst_mac = kwargs.get('dst_mac', "ff:ff:ff:ff:ff:ff")
        ipv6_src = kwargs.get('ipv6_src', None)
        ipv6_dst = kwargs.get('ipv6_dst', None)
        src_vm_cidr = src_vm_fixture.vn_objs[0]['network']\
                        ['contrail:subnet_ipam'][0]['subnet_cidr']
        dest_vm_cidr = dest_vm_fixture.vn_objs[0]['network']\
                        ['contrail:subnet_ipam'][0]['subnet_cidr']
        if IPNetwork(src_vm_cidr) == IPNetwork(dest_vm_cidr):
            traffic_between_diff_networks = False
        else:
            traffic_between_diff_networks = True
        #src_vm_interface = kwargs.get('src_vm_interface', "eth0")
        # TCP is anyway the default for hping3
        icmp = False; tcp = False; udp = False
        if protocol == 'icmp': icmp = True
        if protocol == 'udp': udp = True
        if isinstance(dscp,int):
            tos = format(dscp << 2, 'x')
        else:
            tos = None
        if not src_compute_fixture and src_vm_fixture:
            src_compute_fixture = self.useFixture(ComputeNodeFixture(
                                        self.connections,
                                        src_vm_fixture.vm_node_ip))
        username = self.inputs.host_data[src_compute_fixture.ip]['username']
        password = self.inputs.host_data[src_compute_fixture.ip]['password']
        interface = src_compute_fixture.agent_physical_interface
        src_ip = src_vm_fixture.vm_ip
        dest_ip = dest_ip or dest_vm_fixture.vm_ip
        if traffic_generator == "scapy":
            self.logger.debug("Generating L2 only stream and ignoring all"
                              " other parameters of layers above L2")
            dot1p = dot1p or 0
            ether = {'src':src_mac, 'dst':dst_mac}
            dot1q = {'prio':dot1p, 'vlan':100}
            ipv6 = {}
            udp_header = {}
            if af == "ipv6":
                tos = int(tos,16) if dscp else 0
                ipv6 = {'tc':tos, 'src':ipv6_src, 'dst':ipv6_dst}
                ## WA for Bug 1614472. Internal protocol inside IPv6 is must
                udp_header = {'sport' : 1234}
            scapy_h = ScapyTraffic(src_vm_fixture,
                                   interval= interval,
                                   count = count,
                                   ether = ether,
                                   dot1q = dot1q,
                                   ipv6 = ipv6,
                                   udp = udp_header)
            scapy_h.scapy_start_traffic()
            traffic_obj = TrafficAnalyzer(interface,
                                          src_compute_fixture,
                                          username,
                                          password,
                                          logger=self.logger,
                                          encap_type = encap)
            offset =156 if ipv6 else 100  # 40 bytes of extra encapsulation in IPv6
            session,pcap = traffic_obj.packet_capture_start(
                                    capture_on_payload = True,
                                    signature_string ='5a5a5a5a5a5a5a5a',
                                    offset = offset,
                                    bytes_to_match = 8,
                                    min_length = 100,
                                    max_length = 250)
        elif traffic_generator == "hping":
            hping_h = Hping3(src_vm_fixture,
                             dest_ip,
                             destport=dest_port,
                             baseport=src_port,
                             count=count,
                             interval=interval,
#                            icmp=icmp,
#                            tcp=tcp,
                             udp=udp,
                             tos=tos,
                             keep=True,
                             numeric=True)
            hping_h.start(wait=kwargs.get('wait', False))
            sleep(5)
            fwd_flow,rev_flow = src_compute_fixture.get_flow_entry(
                                    source_ip=src_ip,
                                    dest_ip=dest_ip,
                                    proto=protocol,
                                    source_port=src_port,
                                    dest_port=dest_port,
                                    vrf_id=vrf_id)
            if not fwd_flow or not rev_flow:
                self.logger.error('Flow not created. Cannot proceed with analysis')
                return False
            src_port1 = fwd_flow.dump()['underlay_udp_sport']
            if src_port1 == '0':
                self.logger.error('Flow does not seem active..something is '
                                'wrong. Cannot proceed')
                self.logger.debug('Fwd flow :%s, Rev flow: %s' % (
                                fwd_flow.dump(), rev_flow.dump()))
                return False
            if encap == "MPLSoGRE":
                
                traffic_obj = TrafficAnalyzer(interface,
                                          src_compute_fixture,
                                          username,
                                          password,
                                          src_ip=src_ip,
                                          dest_ip=dest_ip,
                                          logger=self.logger,
                                          encap_type = encap)
            else:
                traffic_obj = TrafficAnalyzer(interface,
                                          src_compute_fixture,
                                          username,
                                          password,
                                          src_port=src_port1,
                                          protocol='udp',
                                          logger=self.logger,
                                          encap_type = encap)    
            session,pcap = traffic_obj.packet_capture_start(
                                    traffic_between_diff_networks =
                                     traffic_between_diff_networks)
        sleep(5)
        traffic_obj.packet_capture_stop()
        if traffic_generator == "scapy":
            scapy_h.scapy_stop_traffic()
        elif traffic_generator == "hping":
            (stats, hping_log) = hping_h.stop()
        if isinstance(expected_dscp,int):
            result = traffic_obj.verify_packets('dscp',
                                                expected_count=1,
                                                dscp=expected_dscp)
            assert result, 'DSCP remarking checks failed. Please check logs'
        if isinstance(expected_dot1p,int):
            result = traffic_obj.verify_packets('dot1p',
                                                expected_count=1,
                                                dot1p=expected_dot1p)
            assert result, '802.1p remarking checks failed. Please check logs'
        if isinstance(expected_exp,int):
            result = traffic_obj.verify_packets('exp',
                                                expected_count=1,
                                                mpls_exp=expected_exp)
            assert result, 'MPLS exp remarking checks failed. Please check logs'
        self.inputs.run_cmd_on_server(src_compute_fixture.ip, "rm %s" % pcap)
        return True
    # end validate_packet_qos_marking
    
    def update_policy_qos_config(self, policy_fixture, qos_config_fixture, 
                                 operation = "add", entry_index =0):
        policy_entry = policy_fixture.policy_obj['policy']['entries']
        new_policy_entry = policy_entry
        if operation == "add":
            qos_obj_fq_name_str = self.vnc_lib.qos_config_read(
                                    id = qos_config_fixture.uuid).\
                                    get_fq_name_str()
            new_policy_entry['policy_rule'][entry_index]['action_list']\
                            ['qos_action'] = qos_obj_fq_name_str
        elif operation == "remove":
            new_policy_entry['policy_rule'][entry_index]['action_list']\
                            ['qos_action'] = ''
        policy_id = policy_fixture.policy_obj['policy']['id']
        policy_data = {'policy': {'entries': new_policy_entry}}
        policy_fixture.update_policy(policy_id, policy_data)
    
    def update_sg_qos_config(self, sg_fixture, qos_config_fixture, 
                             operation = "add"):
        sg_object = self.vnc_lib.security_group_read(id = sg_fixture.get_uuid())
        sg_rules = sg_object.get_security_group_entries().policy_rule
        if operation == "add":
            qos_obj_fq_name_str = self.vnc_lib.qos_config_read(
                                    id = qos_config_fixture.uuid).\
                                    get_fq_name_str()
            for elem in sg_rules:
                elem.action_list=ActionListType(qos_action=qos_obj_fq_name_str)
        elif operation == "remove":
            for elem in sg_rules:
                elem.action_list.qos_action = None
        sg_entries = sg_object.get_security_group_entries()
        sg_entries.set_policy_rule(sg_rules)
        sg_object.set_security_group_entries(sg_entries)
        self.vnc_lib.security_group_update(sg_object)

