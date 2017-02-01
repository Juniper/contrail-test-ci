import re
from tcutils.util import Lock
from vnc_api.vnc_api import *

from common.neutron.base import BaseNeutronTest
from compute_node_test import ComputeNodeFixture
from common.base import GenericTestBase
from common.vrouter.base import BaseVrouterTest

from tcutils.traffic_utils.traffic_analyzer import TrafficAnalyzer
from tcutils.traffic_utils.scapy_traffic_gen import ScapyTraffic
from tcutils.traffic_utils.hping_traffic import Hping3

from time import sleep
import random
from netaddr import *

class PbbEvpnTestBase(BaseVrouterTest):

    @classmethod
    def setUpClass(cls):
        super(PbbEvpnTestBase, cls).setUpClass()
        cls.setupClass_is_run = False
        cls.setupClass_is_run = True
        cls.vnc_api_h = cls.vnc_lib
        cls.inputs.address_family = "dual"
        cls.vnc_lib_fixture = cls.connections.vnc_lib_fixture
        cls.vnc_h = cls.vnc_lib_fixture.vnc_h

    def setup_pbb_evpn(self,pbb_evpn_config=None, bd=None, vn=None, vmi=None,
                       vm=None, bd_vn_mapping=None, bd_vmi_mapping=None):

        # Base PBB EVPN config
        pbb_evpn_enable = pbb_evpn_config.get('pbb_evpn_enable', True)
        mac_learning_enabled = pbb_evpn_config.get('mac_learning_enabled', True)
        mac_limit = pbb_evpn_config.get('mac_limit').get('limit',1024)
        mac_limit_action = pbb_evpn_config.get('mac_limit').get('action','log')

        # MAC Move Limit parameters
        mac_move_limit = pbb_evpn_config.get('mac_move_limit').get('limit',1024)
        mac_move_limit_action = pbb_evpn_config.get('mac_move_limit').get('action','log')
        mac_move_time_window = pbb_evpn_config.get('mac_move_limit').get('window',60)

        # MAC Aging parameters
        mac_aging_time = pbb_evpn_config.get('mac_aging',300)

        # PBB E-Tree parameters
        pbb_etree_enable =  pbb_evpn_config.get('pbb_etree',False)

        # MAC Limit and MAC Move limit objects
        mac_limit_obj = MACLimitControlType(mac_limit=mac_limit,
                                            mac_limit_action=mac_limit_action)
        mac_move_limit_obj = MACMoveLimitControlType(mac_move_limit=mac_move_limit,
                                                     mac_move_limit_action=mac_move_limit_action,
                                                     mac_move_time_window=mac_move_time_window)

        # Global system configuration
        vnc_lib_fixture = self.connections.vnc_lib_fixture
        vnc_lib_fixture.set_global_mac_limit_control(mac_limit_control=mac_limit_obj)
        vnc_lib_fixture.set_global_mac_move_control(mac_move_control=mac_move_limit_obj)
        vnc_lib_fixture.set_global_mac_aging_time(mac_aging_time=mac_aging_time)

        # Bridge domains creation
        bd_count = bd['count']
        bd_fixtures = {} # Hash to store BD fixtures
        for i in range(0,bd_count):
            bd_id = 'bd'+str(i+1)
            if bd_id in bd:
                bd_isid = bd[bd_id].get('isid',0)
            else:
                bd_isid=randint(1,2**24-1)
            bd_fixture = self.create_bd(mac_learning_enabled=mac_learning_enabled,
                                        mac_limit_control=mac_limit_obj,
                                        mac_move_control=mac_move_limit_obj,
                                        mac_aging_time=mac_aging_time,
                                        isid=bd_isid)
            bd_fixtures[bd_id] = bd_fixture


        # VNs creation
        vn_count = vn['count']
        vn_fixtures = {} # Hash to store VN fixtures
        for i in range(0,vn_count):
            vn_id = 'vn'+str(i+1)
            if vn_id in vn:
                vn_subnet = vn[vn_id].get('subnet',None)
                asn = vn[vn_id].get('asn',None)
                target= vn[vn_id].get('target',None)
                vn_fixture = self.create_only_vn(vn_name=vn_id, vn_subnets=[vn_subnet],
                                                 router_asn=asn, rt_number=target)
            else:
                vn_fixture = self.create_only_vn()
            vn_fixtures[vn_id] = vn_fixture

        # VMIs creation
        vmi_count = vmi['count']
        vmi_fixtures = {} # Hash to store VMI fixtures
        for i in range(0,vmi_count):
            vmi_id = 'vmi'+str(i+1)
            if vmi_id in vmi:
                vmi_vn = vmi[vmi_id]['vn']
                vn_fixture = vn_fixtures[vmi_vn]
                parent_vmi = vmi[vmi_id].get('parent',None)
                # VMI is Sub-interface
                if parent_vmi:
                    parent_vmi_fixture = vmi_fixtures[parent_vmi]
                    vlan = vmi[vmi_id].get('vlan',0)
                    vmi_fixture = self.setup_only_vmi(vn_fixture.uuid,
                                                      parent_vmi=parent_vmi_fixture.vmi_obj,
                                                      vlan_id=vlan,
                                                      api_type='contrail',
                                                      mac_address=parent_vmi_fixture.mac_address)
                else:
                    vmi_fixture = self.setup_only_vmi(vn_fixture.uuid)
            vmi_fixtures[vmi_id] = vmi_fixture

        # VMs creation
        vm_count = vm['count']
        launch_mode = vm.get('launch_mode','default')
        vm_fixtures = {} # Hash to store VM fixtures

        compute_nodes = self.orch.get_hosts()
        compute_nodes_len = len(compute_nodes)
        index = random.randint(0,compute_nodes_len-1)
        for i in range(0,vm_count):
            vm_id = 'vm'+str(i+1)
            vn_list = vm[vm_id]['vn']
            vmi_list = vm[vm_id]['vmi']
            # Get the userdata related to sub interfaces
            userdata = vm[vm_id].get('userdata',None)
            if userdata:
                userdata = './scripts/pbb_evpn/'+userdata

            vn_fix_obj_list =[]
            vmi_fix_uuid_list =[]

            # Build the VN fixtures objects
            for vn in vn_list:
                vn_fix_obj_list.append(vn_fixtures[vn].obj)

           # Build the VMI UUIDs
            for vmi in vmi_list:
                vmi_fix_uuid_list.append(vmi_fixtures[vmi].uuid)

            # VM launch mode handling
            # Distribute mode, generate the new random index
            # Non Distribute mode, use previously generated index
            # Default mode, Nova takes care of launching
            if launch_mode == 'distribute':
                node_name = self.inputs.compute_names[index]
                index = random.randint(0,compute_nodes_len-1)
            elif launch_mode == 'non-Distribute':
                node_name = self.inputs.compute_names[index]
            elif launch_mode == 'default':
                node_name=None

            vm_fixture = self.create_vm(vn_objs=vn_fix_obj_list,
                                        port_ids=vmi_fix_uuid_list,
                                        userdata=userdata,
                                        node_name=node_name)
            vm_fixtures[vm_id] = vm_fixture

        # PBB EVPN VN configuration
        for vn_fixture in vn_fixtures.values():
            vn_fixture.set_pbb_evpn_enable(pbb_evpn_enable=pbb_evpn_enable)
            vn_fixture.set_pbb_etree_enable(pbb_etree_enable=pbb_etree_enable)
            vn_fixture.set_unknown_unicast_forwarding(True)

        # BD to VN mapping
        for bd, vn in bd_vn_mapping.iteritems():
            bd_fixture = bd_fixtures[bd]
            vn_fixture = vn_fixtures[vn]
            vn_fixture.add_bridge_domain(bd_obj=bd_fixture)

        for vm_fixture in vm_fixtures.values():
            vm_fixture.wait_till_vm_is_up()

        # BD to VMI mapping
        vlan_tag = 0
        for bd, vmi_list in bd_vmi_mapping.iteritems():
            bd_fixture = bd_fixtures[bd]
            for vmi in vmi_list:
                vmi_fixture = vmi_fixtures[vmi]
                self.add_bd_to_vmi(bd_fixture.uuid, vmi_fixture.uuid, vlan_tag)

        # Disable Policy on all VMIs
        for vmi_fixture in vmi_fixtures.values():
            self.vnc_h.disable_policy_on_vmi(vmi_fixture.uuid, True)


        self.ret_dict = {
            'bd_fixtures':bd_fixtures,
            'vmi_fixtures':vmi_fixtures,
            'vn_fixtures':vn_fixtures,
            'vm_fixtures':vm_fixtures,
        }
        return self.ret_dict

    def delete_pbb_evpn(self, bd_fixtures=None, vn_fixtures=None,
                         vm_fixtures=None, vmi_fixtures=None, ):

        # Clean up BD
        for bd_fixture in bd_fixtures.values():
            self.delete_bd(uuid=bd_fixture.uuid)

        # Clean up VMI
        for vmi_fixture in vmi_fixtures.values():
            self.addCleanup(vmi_fixture.cleanUp)

        # Clean up VM
        for vm_fixture in vm_fixtures.values():
            self.addCleanup(vm_fixture.cleanUp)

        # Clean up VN
        for vn_fixture in vn_fixtures.values():
            self.addCleanup(vn_fixture.cleanUp)



    def validate_l2_traffic (self, traffic=None, vm_fixtures=None):
        '''
            dest_compute_fixture should be supplied if underlay traffic is
            being checked
            dest_vm_fixture should be supplied if traffic is being checked for a
            specific destination VM

            Few things to note:
            1. traffic_generator can be "scapy" or "hping"
            2. "scapy" is specifically used here to test l2 and IPv6 traffic only.
               For all other traffic, hping is being used.
        '''
        stream_count = traffic.get('count', 1)
        traffic_generator = traffic.get('traffic_generator', 'scapy')
        for i in range(0,stream_count):
            stream_id = 'stream'+str(i+1)
            if stream_id in traffic:
                src = traffic[stream_id]['src']
                dst = traffic[stream_id]['dst']
                src_vm_fixture = vm_fixtures[src]
                dest_vm_fixture = vm_fixtures[dst]
                protocol = traffic[stream_id].get('protocol', 'udp')
                dest_ip = traffic[stream_id].get('dest_ip', None)
                src_port = traffic[stream_id].get('src_port', None)
                dst_port = traffic[stream_id].get('dst_port', None)
                interval = traffic[stream_id].get('interval', 1)
                count = traffic[stream_id].get('count', 1)
                src_mac = traffic[stream_id].get('src_mac', "00:00:00:00:00:11")
                dst_mac = traffic[stream_id].get('dst_mac', "ff:ff:ff:ff:ff:ff")
                ipv6_src = traffic[stream_id].get('ipv6_src', None)
                ipv6_dst = traffic[stream_id].get('ipv6_dst', None)

                # Default parameters
                src_compute_fixture = None
                dscp = None
                dot1p = None
                exp = None
                expected_dscp = None
                expected_dot1p = None
                expected_exp = None
                encap = 'MPLSoUDP'
                vrf_id = None
                af = 'ipv4'

                expected_src_mac = "00:00:00:00:00:11"

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
                    dot1q = {'prio':dot1p, 'vlan':212}
                    ipv6 = {}
                    udp_header = {}
                    if af == "ipv6":
                        tos = int(tos,16) if dscp else 0
                        ipv6 = {'tc':tos, 'src':ipv6_src, 'dst':ipv6_dst}
                        ## WA for Bug 1614472. Internal protocol inside IPv6 is must
                        udp_header = {'sport' : 1234}
                    offset =156 if ipv6 else 100
                    traffic_obj, scapy_obj = self._generate_scapy_traffic(
                                                                src_vm_fixture,
                                                                src_compute_fixture,
                                                                interface,
                                                                encap = encap,
                                                                interval=interval,
                                                                count=count,
                                                                ether = ether,
                                                                dot1q = dot1q,
                                                                ipv6 = ipv6,
                                                                udp = udp_header)
                    session,pcap = traffic_obj.packet_capture_start(
                                            capture_on_payload = True,
                                            signature_string ='5a5a5a5a5a5a5a5a',
                                            offset = offset,
                                            bytes_to_match = 8,
                                            min_length = 100,
                                            max_length = 250)
                elif traffic_generator == "hping":
                    traffic_obj, hping_obj = self._generate_hping_traffic(
                                                                src_vm_fixture,
                                                                src_compute_fixture,
                                                                interface,
                                                                dest_ip =dest_ip,
                                                                src_port = src_port,
                                                                dest_port = dest_port,
                                                                encap = encap,
                                                                interval = interval,
                                                                count = count,
                                                                proto = protocol,
                                                                vrf_id = vrf_id,
                                                                udp = udp,
                                                                tos = tos)
                    session,pcap = traffic_obj.packet_capture_start(
                                            traffic_between_diff_networks =
                                            traffic_between_diff_networks)
                sleep(5)
                traffic_obj.packet_capture_stop()
                if traffic_generator == "scapy":
                    scapy_obj.stop()
                elif traffic_generator == "hping":
                    (stats, hping_log) = hping_obj.stop()
                if isinstance(expected_src_mac,str):
                    result = traffic_obj.verify_packets('src_mac',
                                                        pcap_path_with_file_name = pcap,
                                                        expected_count=10,
                                                        src_mac=expected_src_mac)
                    #assert result, 'SRC MAC checks failed. Please check logs'
                self.inputs.run_cmd_on_server(src_compute_fixture.ip, "rm %s" % pcap,)
                return True
    # end validate_packet_qos_marking

    def _generate_scapy_traffic(self, src_vm_fixture, src_compute_fixture,
                                interface, encap = None, username = None,
                                password = None, interval=1, count=1, **kwargs):
        params = {}
        params['ether'] = kwargs.get('ether',{})
        params['dot1q'] = kwargs.get('dot1q',{})
        params['ip'] = kwargs.get('ip',{})
        params['ipv6'] = kwargs.get('ipv6',{})
        params['tcp'] = kwargs.get('tcp',{})
        params['udp'] = kwargs.get('udp',{})
        username = username or self.inputs.host_data[
                                    src_compute_fixture.ip]['username']
        password = password or self.inputs.host_data[
                                    src_compute_fixture.ip]['password']
        scapy_obj = ScapyTraffic(src_vm_fixture,
                                   interval= interval,
                                   count = count,
                                   **params)
        scapy_obj.start()
        traffic_obj = TrafficAnalyzer(interface,
                                    src_compute_fixture,
                                    username,
                                    password,
                                    logger=self.logger,
                                    encap_type = encap)
        return traffic_obj, scapy_obj

    def _generate_hping_traffic(self, src_vm_fixture, src_compute_fixture,
                                interface, dest_ip =None, src_port = None,
                                dest_port = None, encap = None, username = None,
                                password = None, interval=1, count=1,
                                vrf_id = None, proto = None, **kwargs):
        udp = kwargs.get('udp', False)
        tos = kwargs.get('tos', None)
        username = username or self.inputs.host_data[
                                    src_compute_fixture.ip]['username']
        password = password or self.inputs.host_data[
                                    src_compute_fixture.ip]['password']
        src_ip = src_vm_fixture.vm_ip
        hping_obj = Hping3(src_vm_fixture,
                             dest_ip,
                             destport=dest_port,
                             baseport=src_port,
                             count=count,
                             interval=interval,
                             udp=udp,
                             tos=tos,
                             keep=True,
                             numeric=True)
        hping_obj.start(wait=kwargs.get('wait', False))
        sleep(5)
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
            fwd_flow,rev_flow = src_compute_fixture.get_flow_entry(
                                    source_ip=src_ip,
                                    dest_ip=dest_ip,
                                    proto=proto,
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
            traffic_obj = TrafficAnalyzer(interface,
                                          src_compute_fixture,
                                          username,
                                          password,
                                          src_port=src_port1,
                                          protocol='udp',
                                          logger=self.logger,
                                          encap_type = encap)
        return traffic_obj, hping_obj



    @classmethod
    def tearDownClass(cls):
        super(PbbEvpnTestBase, cls).tearDownClass()
    # end tearDownClass


