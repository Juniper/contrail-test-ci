import re
from vnc_api.vnc_api import *

from common.vrouter.base import BaseVrouterTest
#from common.neutron.base import BaseNeutronTest
#from compute_node_test import ComputeNodeFixture
#from common.base import GenericTestBase

from tcutils.traffic_utils.scapy_traffic_gen import ScapyTraffic

import random
#from netaddr import *
from tcutils.tcpdump_utils import *
from tcutils.util import *


MVPN_CONFIG = {
    'mvpn_enable': True,
}

class MVPNTestBase(BaseVrouterTest):

    @classmethod
    def setUpClass(cls):
        super(MVPNTestBase, cls).setUpClass()
        cls.vnc_lib_fixture = cls.connections.vnc_lib_fixture
        cls.vnc_h = cls.vnc_lib_fixture.vnc_h


    def setup_vns(self, vn=None):
        '''
        Input vn format:
            vn = {'count':1,
                  'vn1':{'subnet':get_random_cidr(), 'asn':64510, 'target':1},
                 }
        '''
        vn_count = vn['count'] if vn else 1
        vn_fixtures = {} # Hash to store VN fixtures
        for i in range(0,vn_count):
            vn_id = 'vn'+str(i+1)
            if vn_id in vn:
                vn_subnet = vn[vn_id].get('subnet',None)
                asn = vn[vn_id].get('asn',None)
                target= vn[vn_id].get('target',None)

                vn_fixture = self.create_vn(vn_name=vn_id, vn_subnets=[vn_subnet],
                                                 router_asn=asn, rt_number=target)
            else:
                vn_fixture = self.create_vn(vn_name=vn_id)
            vn_fixtures[vn_id] = vn_fixture

        return vn_fixtures

    def setup_vmis(self, vn_fixtures, vmi=None):
        '''
        Input vmi format:
            vmi = {'count':2,
                   'vmi1':{'vn': 'vn1'},
                   'vmi2':{'vn': 'vn1'},
                  }
        '''
        vmi_count = vmi['count'] if vmi else 1
        vmi_fixtures = {} # Hash to store VMI fixtures
        for i in range(0,vmi_count):
            vmi_id = 'vmi'+str(i+1)
            if vmi_id in vmi:
                vmi_vn = vmi[vmi_id]['vn']
                vn_fixture = vn_fixtures[vmi_vn]
                vmi_fixture = self.setup_vmi(vn_fixture.uuid)
            else:
                vmi_vn = 'vn'+str(i+1)
                vn_fixture = vn_fixtures[vmi_vn]
                vmi_fixture = self.setup_vmi(vn_fixture.uuid)
            vmi_fixtures[vmi_id] = vmi_fixture

        return vmi_fixtures

    def setup_vms(self, vn_fixtures, vmi_fixtures, vm=None):
        '''
        Input vm format:
            vm = {'count':2, 'launch_mode':'distribute',
                  'vm1':{'vn':['vn1'], 'vmi':['vmi1'], 'userdata':{
                    'vlan': str(vmi['vmi3']['vlan'])} },
                  'vm2':{'vn':['vn1'], 'vmi':['vmi2'], 'userdata':{
                    'vlan': str(vmi['vmi4']['vlan'])} }
                }
            launch_mode can be distribute or non-distribute
        '''
        vm_count = vm['count'] if vm else 1
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
            userdata_file = None
            if userdata:
                file_obj = self.create_user_data(userdata['vlan'])
                userdata_file = file_obj.name

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
                index = i%compute_nodes_len
                node_name = self.inputs.compute_names[index]
            elif launch_mode == 'non-distribute':
                node_name = self.inputs.compute_names[index]
            elif launch_mode == 'default':
                node_name=None

            vm_fixture = self.create_vm(vn_objs=vn_fix_obj_list,
                                        port_ids=vmi_fix_uuid_list,
                                        userdata=userdata_file,
                                        node_name=node_name)
            vm_fixtures[vm_id] = vm_fixture
            if userdata:
                file_obj.close()

        for vm_fixture in vm_fixtures.values():
            assert vm_fixture.wait_till_vm_is_up()

        return vm_fixtures

    def setup_mvpn(self, mvpn_config=None, vn=None, vmi=None,
                       vm=None, verify=True):
        '''
            Setup MVPN Configuration.

            Sets up MVPN configuration on global level

            Input parameters looks like:
                #MVPN parameters:
                mvpn_config = {
                    'mvpn_enable': True,
                }

                #VN parameters:
                vn = {'count':1,            # VN count
                     # VN Details
                    'vn1':{'subnet':'10.10.10.0/24', 'asn':64510, 'target':1},
                    }

                #VMI parameters:
                vmi = {'count':2, # VMI Count
                    'vmi1':{'vn': 'vn1'}, # VMI details
                    'vmi2':{'vn': 'vn1'}, # VMI details
                    }

                #VM parameters:
                vm = {'count':2, # VM Count
                    # VM Launch mode i.e distribute non-distribute, default
                    'launch_mode':'distribute',
                    'vm1':{'vn':['vn1'], 'vmi':['vmi1']}, # VM Details
                    'vm2':{'vn':['vn1'], 'vmi':['vmi2']}, # VM Details
                    }

        '''

        # Base MVPN config
        mvpn_enable = mvpn_config.get('mvpn_enable', True)

        # Configuring mvpn at global level
        name = self.inputs.ext_routers[0][0]
        ip = self.inputs.ext_routers[0][1]
        asn = self.inputs.router_asn
        self.vnc_h.provision_mvpn(name, ip, asn)

        # VNs creation
        vn_fixtures = self.setup_vns(vn)

        # VMIs creation
        vmi_fixtures = self.setup_vmis(vn_fixtures, vmi)

        # VMs creation
        vm_fixtures = self.setup_vms(vn_fixtures, vmi_fixtures, vm)

        ret_dict = {
            'vmi_fixtures':vmi_fixtures,
            'vn_fixtures':vn_fixtures,
            'vm_fixtures':vm_fixtures,
        }
        return ret_dict

    @classmethod
    def tearDownClass(cls):
        super(MVPNTestBase, cls).tearDownClass()
    # end tearDownClass


class IGMPTestBase(BaseVrouterTest):

    @classmethod
    def setUpClass(cls):
        super(IGMPTestBase, cls).setUpClass()
        cls.vnc_lib_fixture = cls.connections.vnc_lib_fixture
        cls.vnc_h = cls.vnc_lib_fixture.vnc_h

    def send_igmp_reports(self, vm_fixtures, traffic, igmp, **kwargs):
        '''
            Sends IGMP Reports from multiple receivers :
                mandatory args:
                    traffic: Multicast receivers details
                    igmp : IGMP Report details
                optional args:
                     1. count: No. of reports
        '''

        # Send IGMPv3 membership report
        for stream in traffic.values():
            for rcvr in stream['rcvrs']:
                result = self.send_igmp_report(vm_fixtures[rcvr], igmp, vm_fixtures)

    def verify_mvpn_routes(self, route_type, vm_fixtures=None, traffic=None, igmp=None,  **kwargs):
        '''
            Verify MVPN routes at control node:
        '''

        # Verify MVPN Type-1 Route by default
        if route_type == 1:
            ip = self.inputs.ext_routers[0][1]
            mvpn_route = "1-"+ip
            result = self.verify_mvpn_route(mvpn_route, expectation=True)

        # Type-7 MVPN route
        elif route_type == 7:
            for stream in traffic.values():
                for rcvr in stream['rcvrs']:
                    compute_ip = vm_fixtures[rcvr].get_compute_host()
                    if igmp['type'] == 0x22:
                        numgrp = igmp.get('numgrp', 1)
                        for record in range(numgrp):
                            record_name = "record"+str(record+1)
                            rtype = igmp[record_name]['rtype']
                            maddr = igmp[record_name]['maddr']
                            srcaddrs = igmp[record_name]['srcaddrs']
                            asn = self.inputs.router_asn

                            for srcaddr in srcaddrs:
                                srcip = str(vm_fixtures[srcaddr].vm_ip)
                                mvpn_route = "7-"+compute_ip+".+"+asn+","+srcip+","+maddr

                                # Verify MVPN routes in bgp master mvpn table
                                if rtype == 1:
                                    expectation = True
                                elif rtype == 2:
                                    expectation = False
                                result = self.verify_mvpn_route(mvpn_route, expectation=expectation)

                                # Verify MVPN routes in RI mvpn table
                                vn_fq_name = vm_fixtures[rcvr].vn_fq_name
                                vn_name = vn_fq_name.split(':')[-1]
                                ri_name = vn_fq_name + ':' + vn_name

                                if rtype == 1:
                                    expectation = True
                                elif rtype == 2:
                                    expectation = False
                                result = self.verify_mvpn_route(mvpn_route, ri_name=ri_name, expectation=expectation)

        # Type-5 MVPN route
        elif route_type == 5:
            for stream in traffic.values():
                src_vm_fixture = vm_fixtures[stream['src']]
                compute_ip = src_vm_fixture.get_compute_host()
                src = src_vm_fixture.vm_ip
                maddr = stream['maddr']
                mvpn_route = "5-"+compute_ip+".+"+","+src+","+maddr

                # Verify MVPN routes in bgp master mvpn table
                result = self.verify_mvpn_route(mvpn_route, expectation=True)

                # Verify MVPN routes in RI mvpn table
                vn_fq_name = src_vm_fixture.vn_fq_name
                vn_name = vn_fq_name.split(':')[-1]
                ri_name = vn_fq_name + ':' + vn_name
                result = self.verify_mvpn_route(mvpn_route, ri_name=ri_name, expectation=True)
        return result


    def verify_mvpn_route(self, mvpn_route, ri_name=None, **kwargs):
        '''
            Verify MVPN routes at control node:
        '''

        expectation = kwargs.get('expectation',True)
        # Verify MVPN routes at control node
        for cn in self.inputs.bgp_ips:
            mvpn_table_entry = self.cn_inspect[cn].get_cn_mvpn_table(ri_name)
            if not ri_name:
                ri_name = 'mvpn.0'

            if expectation:
                result = False
                for mvpn_entry in mvpn_table_entry:
                    if re.match(mvpn_route, mvpn_entry['prefix']):
                        result = True
                        self.logger.info(
                            'MVPN route %s seen in the %s table of the control node-%s' % (mvpn_route, ri_name, cn))
                        origin = self.get_origin_mvpn_route(mvpn_entry)
                        protocol = self.get_protocol_mvpn_route(mvpn_entry)
                        source = self.get_source_mvpn_route(mvpn_entry)
                        pmsi_tunnel_label = self.get_pmsi_tunnel_label_mvpn_route(mvpn_entry)
                        pmsi_tunnel_type = self.get_pmsi_tunnel_type_mvpn_route(mvpn_entry)
                        pmsi_tunnel_id = self.get_pmsi_tunnel_id_mvpn_route(mvpn_entry)
                        self.logger.info(
                            'Origin:%s, Protocol:%s, Source:%s, Pmsi Tunnel Label:%s, \
                             Pmsi Tunnel Type:%s, Pmsi Tunnel Id:%s' %
                            (origin, source, protocol, pmsi_tunnel_label,
                             pmsi_tunnel_type, pmsi_tunnel_id))
                        break
                if result == False:
                    self.logger.warn(
                        'MVPN route %s not seen in the %s table of the control nodes' % (mvpn_route, ri_name))
            else:
                result = True
                for mvpn_entry in mvpn_table_entry:
                    if re.match(mvpn_route, mvpn_entry['prefix']):
                        result = False
                        self.logger.warn(
                            'MVPN route %s seen in the %s table of the control node-%s' % (mvpn_route, ri_name, cn))
                        break
                if result == True:
                    self.logger.info(
                        'MVPN route %s not seen in the %s table of the control nodes' % (mvpn_route, ri_name))

                return result

    def get_origin_mvpn_route(self, mvpn_entry, **kwargs):
        '''
            Get origin of MVPN route:
        '''
        return mvpn_entry['paths'][0]['origin']

    def get_protocol_mvpn_route(self, mvpn_entry, **kwargs):
        '''
            Get protocol of MVPN route:
        '''
        return mvpn_entry['paths'][0]['protocol']


    def get_source_mvpn_route(self, mvpn_entry, **kwargs):
        '''
            Get source of MVPN route:
        '''
        return mvpn_entry['paths'][0]['source']

    def get_pmsi_tunnel_label_mvpn_route(self, mvpn_entry, **kwargs):
        '''
            Get PMSI Tunnel label of MVPN route:
        '''
        return mvpn_entry['paths'][0]['pmsi_tunnel']['ShowPmsiTunnel']['label']

    def get_pmsi_tunnel_type_mvpn_route(self, mvpn_entry, **kwargs):
        '''
            Get PMSI Tunnel type of MVPN route:
        '''
        return mvpn_entry['paths'][0]['pmsi_tunnel']['ShowPmsiTunnel']['type']

    def get_pmsi_tunnel_id_mvpn_route(self, mvpn_entry, **kwargs):
        '''
            Get PMSI Tunnel ID of MVPN route:
        '''
        return mvpn_entry['paths'][0]['pmsi_tunnel']['ShowPmsiTunnel']['identifier']



    def verify_igmp_reports(self, vm_fixtures, traffic, igmp, **kwargs):
        '''
            Verify IGMP Reports at agent:
                mandatory args:
                    traffic: Multicast receivers details
                    igmp : IGMP Report details
                optional args:
                     1. count: No. of reports
        '''


        # Verify IGMPv3 membership at agent
        # As IGMP report is sent from these receivers, entries should be present
        # in agent
        for stream in traffic.values():
            for rcvr in stream['rcvrs']:
                # Verifying IGMP report details in VRF 1 at agent
                vrf_id = 1
                self.verify_igmp_report(vm_fixtures[rcvr], vrf_id, igmp,
                                        vm_fixtures, expectation=True)

                compute_node_ip = vm_fixtures[rcvr].vm_node_ip
                # Verifying IGMP report details in VM's VRF at agent
                vrf_id = vm_fixtures[rcvr].get_vrf_ids()[compute_node_ip].values()[0]
                self.verify_igmp_report(vm_fixtures[rcvr], vrf_id, igmp,
                                        vm_fixtures, expectation=True)

        # Verify IGMPv3 membership at agent
        # As IGMP report is not sent from these receivers, entries should
        # not be present in agent
        for stream in traffic.values():
            for rcvr in stream['non_rcvrs']:
                # Verifying IGMP report details in VRF 1 at agent
                vrf_id = 1
                self.verify_igmp_report(vm_fixtures[rcvr], vrf_id, igmp,
                                        vm_fixtures, expectation=False)

                compute_node_ip = vm_fixtures[rcvr].vm_node_ip
                vrf_id = vm_fixtures[rcvr].get_vrf_ids()[compute_node_ip].values()[0]
                self.verify_igmp_report(vm_fixtures[rcvr], vrf_id, igmp,
                                        vm_fixtures, expectation=False)


    def send_igmp_report(self, rcv_vm_fixture, igmp, vm_fixtures, **kwargs):
        '''
            Sends IGMP Report from VM :
                mandatory args:
                    rcv_vm_fixture: send IGMP Report from this VM
                    igmp : IGMP Report details
                optional args:
                     1. count: No. of reports
        '''

        # Get IGMP parameters
        igmpv3 = {}
        igmpv3gr = {}
        igmpv3['type'] = igmp.get('type', 0x11)
        num_of_grp_records = igmp.get('numgrp', 1)
        for record in range(num_of_grp_records):
            record_name = "record"+str(record+1)
            if record_name in igmp:
                rtype = igmp[record_name]['rtype']
                maddr = igmp[record_name]['maddr']
                srcaddrs = igmp[record_name]['srcaddrs']
                srcips = []
                for srcaddr in srcaddrs:
                    srcips.append(str(vm_fixtures[srcaddr].vm_ip))
                record = {'rtype':rtype,'maddr':maddr,'srcaddrs':srcips}
                igmpv3gr[record_name] = record

        if igmpv3['type'] == 0x22:
            igmpv3mr = {'numgrp':num_of_grp_records}

            scapy_obj = self._generate_igmp_traffic(rcv_vm_fixture,
                                                        igmpv3=igmpv3,
                                                        igmpv3mr=igmpv3mr,
                                                        igmpv3gr=igmpv3gr)

    def _generate_igmp_traffic(self, rcv_vm_fixture, **kwargs):
        params = {}
        ether = {'type': 0x0800}
        ip = {'src': str(rcv_vm_fixture.vm_ip)}
        params['ether'] = ether
        params['ip'] = ip
        params['igmp'] = kwargs.get('igmpv3',{})
        params['igmpv3mr'] = kwargs.get('igmpv3mr',{})
        params['igmpv3gr'] = kwargs.get('igmpv3gr',{})
        params['payload'] = "''"

        scapy_obj = ScapyTraffic(rcv_vm_fixture, **params)
        scapy_obj.start()
        return scapy_obj

    def verify_igmp_report(self, vm_fixture, vrf_id, igmp, vm_fixtures, expectation=True):
        '''
            Verify IGMP Report:
                mandatory args:
                    vm_fixture: IGMP Report from this VM
                optional args:
        '''

        tap_intf = vm_fixture.tap_intf.values()[0]['name']
        compute_node_ip = vm_fixture.vm_node_ip
        num_of_grp_records = igmp.get('numgrp', 1)
        for record in range(num_of_grp_records):
            record_name = "record"+str(record+1)
            if record_name in igmp:
                rtype = igmp[record_name]['rtype']
                maddr = igmp[record_name]['maddr']
                srcaddrs = igmp[record_name]['srcaddrs']
                for srcaddr in srcaddrs:
                    srcip = str(vm_fixtures[srcaddr].vm_ip)
                    if rtype == 1:
                        expectation = True
                    elif rtype == 2:
                        expectation =False

                    # Verifying IGMP report details in VM's VRF at agent
                    mc_route_in_agent = self.verify_igmp_at_agent(compute_node_ip,
                        vrf_id, tap_intf, maddr, srcip, expectation=expectation)


    def start_tcpdump_mcast_rcvrs(self, vm_fixtures, traffic, expectation=True):
        '''
            Verify IGMP Report:
                mandatory args:
                    vm_fixture: IGMP Report from this VM
                optional args:
        '''
        session = {}
        pcap = {}

        # Start tcpdump on receivers and non receivers
        for stream in traffic.values():
            src_ip = vm_fixtures[stream['src']].vm_ip
            dst_ip = stream['maddr']

            # Start the tcpdump on receivers
            for rcvr in stream['rcvrs']:
                filters = '\'(src host %s and dst host %s)\'' % (src_ip, dst_ip)
                session[rcvr], pcap[rcvr] = start_tcpdump_for_vm_intf(
                    self, vm_fixtures[rcvr], vm_fixtures[rcvr].vn_fq_name, filters=filters)

            # Start the tcpdump on non receivers
            for rcvr in stream['non_rcvrs']:
                filters = '\'(src host %s and dst host %s)\'' % (src_ip, dst_ip)
                session[rcvr], pcap[rcvr] = start_tcpdump_for_vm_intf(
                    self, vm_fixtures[rcvr], vm_fixtures[rcvr].vn_fq_name, filters=filters)


        return session, pcap
    def send_mcast_streams(self, vm_fixtures, traffic, **kwargs):
        '''
            Sends Multicast traffic from multiple senders:
                mandatory args:
                    vm_fixtures: VM fixture details
                    traffic: Multicast traffic details
                optional args:
                     1. count: No. of reports
        '''

        # Send Multicast Traffic
        for stream in traffic.values():
            self.send_mcast_stream(vm_fixtures[stream['src']],
                maddr=stream['maddr'], count=stream['count'])

    def verify_mcast_streams(self, session, pcap, vm_fixtures, traffic, **kwargs):
        '''
            Sends Multicast traffic from multiple senders:
                mandatory args:
                    vm_fixtures: VM fixture details
                    traffic: Multicast traffic details
                optional args:
                     1. count: No. of reports
        '''

        # Verify Multicast Traffic on receivers
        for stream in traffic.values():
            for rcvr in stream['rcvrs']:
                verify_tcpdump_count(self, session[rcvr], pcap[rcvr],
                                     exp_count=stream['count'],
                                     grep_string="ip-proto")

        # Verify Multicast Traffic on non receivers, traffic should not reach
        # these
        for stream in traffic.values():
            for rcvr in stream['non_rcvrs']:
                verify_tcpdump_count(self, session[rcvr], pcap[rcvr],
                                     exp_count=0,
                                     grep_string="ip-proto")



    @retry(delay=2, tries=2)
    def verify_igmp_at_agent(self, compute_ip, vrf_id, tap_intf, grp_ip=None, src_ip=None,
            expectation=True):
        '''
        Get IGMP Reports from the agent with retry
        '''
        mcast_route_in_agent = self.agent_inspect[compute_ip].get_vna_mcast_route(
            vrf_id=vrf_id, grp_ip=grp_ip, src_ip=src_ip)

        if expectation:
            if mcast_route_in_agent:
                src_present = mcast_route_in_agent['src']
                grp_present = mcast_route_in_agent['grp']
                tap_intf_present = mcast_route_in_agent['nh']['mc_list'][0]['itf']

                if src_ip == src_present and grp_ip == grp_present and tap_intf == tap_intf_present:
                    self.logger.debug("Mcast routes found in agent is: %s" % (
                        mcast_route_in_agent))
                    return True

            self.logger.warn("Mcast routes in agent %s not found for vrf id %s" % (
                compute_ip, vrf_id))
            return False
        else:
            if mcast_route_in_agent:
                self.logger.warn("Mcast routes found in agent is: %s" % (
                    mcast_route_in_agent))
                return False
            else:
                self.logger.debug("Mcast routes in agent %s not found for vrf id %s" % (
                    compute_ip, vrf_id))
                return True



    def send_mcast_stream(self, src_vm_fixture, **kwargs):
        '''
            Sends Multicast traffic from VM src_vm_fixture:
                mandatory args:
                    src_vm_fixture: send multicast traffic from this VM
                optional args:
                     1. maddr: Multicast group to which traffic is sent
                     2. count: No. of packets
                     3. payload: upper layer packets
        '''

        maddr = kwargs.get('maddr', None)
        count = kwargs.get('count', 1)
        payload = kwargs.get('payload', "'*****This is default payload*****'")

        params = {}
        ether = {'type': 0x0800}
        ip = {'src': str(src_vm_fixture.vm_ip), 'dst':maddr}
        params['ether'] = ether
        params['ip'] = ip
        params['count'] = count
        params['payload'] = payload

        scapy_obj = ScapyTraffic(src_vm_fixture, **params)
        scapy_obj.start()
        return scapy_obj


    def send_verify_mcast(self, vm_fixtures, traffic, igmp, **kwargs):
        '''
            Send and verify IGMP report and multicast traffic
                mandatory args:
                    vm_fixtures: vm_fixture details
                    traffic : Multicast traffic details
                    igmp: IGMP Report details
                optional args:
        '''


        # Send IGMP membership report from multiple receivers
        result = self.send_igmp_reports(vm_fixtures, traffic, igmp)

        # Verify IGMP membership reports at agent
        result = self.verify_igmp_reports(vm_fixtures, traffic, igmp)

        # Verify MVPN routes (type-7) at control node
        route_type = 7
        result = self.verify_mvpn_routes(route_type, vm_fixtures, traffic, igmp)

        # Start tcpdump on receivers
        session, pcap = self.start_tcpdump_mcast_rcvrs(vm_fixtures, traffic)

        # Send multicast traffic
        result = self.send_mcast_streams(vm_fixtures, traffic)

        # Verify MVPN routes (type-5) at control node
        route_type = 5
        result = self.verify_mvpn_routes(route_type, vm_fixtures, traffic, igmp)

        # Verify multicast traffic
        result = self.verify_mcast_streams(session, pcap, vm_fixtures, traffic)

    @classmethod
    def tearDownClass(cls):
        super(IGMPTestBase, cls).tearDownClass()
    # end tearDownClass



class MVPNTestSingleVNSingleComputeBase(MVPNTestBase, IGMPTestBase):

    @classmethod
    def setUpClass(cls):
        super(MVPNTestSingleVNSingleComputeBase, cls).setUpClass()
        cls.inputs.set_af(cls.get_af())

    def bringup_mvpn_setup(self, vn=None, vmi=None, vm=None):
        # MVPN parameters
        mvpn_config = MVPN_CONFIG

        # VN parameters
        vn = {'count':1,
            'vn1':{'subnet':'10.10.10.0/24', 'asn':64510, 'target':1},
            #'vn1':{'subnet':get_random_cidr(), 'asn':64510, 'target':1},
            }

        # VMI parameters
        vmi = {'count':3,
            'vmi1':{'vn': 'vn1'},
            'vmi2':{'vn': 'vn1'},
            'vmi3':{'vn': 'vn1'},
            }

        # VM parameters
        vm = {'count':3, 'launch_mode':'non-distribute',
            'vm1':{'vn':['vn1'], 'vmi':['vmi1']}, # Mcast source
            'vm2':{'vn':['vn1'], 'vmi':['vmi2']}, # Mcast receiver
            'vm3':{'vn':['vn1'], 'vmi':['vmi3']}, # Mcast receiver
            }

        ret_dict = self.setup_mvpn(mvpn_config=mvpn_config, vn=vn, vmi=vmi,
                                vm=vm)
        vmi_fixtures = ret_dict['vmi_fixtures']
        vn_fixtures = ret_dict['vn_fixtures']
        vm_fixtures = ret_dict['vm_fixtures']
        return ret_dict

    @classmethod
    def tearDownClass(cls):
        super(MVPNTestSingleVNSingleComputeBase, cls).tearDownClass()
    # end tearDownClass


class MVPNTestSingleVNMultiComputeBase(MVPNTestBase, IGMPTestBase):

    @classmethod
    def setUpClass(cls):
        super(MVPNTestSingleVNMultiComputeBase, cls).setUpClass()
        cls.inputs.set_af(cls.get_af())

    def bringup_mvpn_setup(self):
        # MVPN parameters
        mvpn_config = MVPN_CONFIG

        # VN parameters
        vn = {'count':1,
            'vn1':{'subnet':get_random_cidr(), 'asn':64510, 'target':1},
            }

        # VMI parameters
        vmi = {'count':4,
            'vmi1':{'vn': 'vn1'},
            'vmi2':{'vn': 'vn1'},
            'vmi3':{'vn': 'vn1'},
            'vmi4':{'vn': 'vn1'},
            }

        # VM parameters
        vm = {'count':4, 'launch_mode':'distribute',
            'vm1':{'vn':['vn1'], 'vmi':['vmi1']}, # Mcast source
            'vm2':{'vn':['vn1'], 'vmi':['vmi2']}, # Mcast receiver
            'vm3':{'vn':['vn1'], 'vmi':['vmi3']}, # Mcast receiver
            'vm4':{'vn':['vn1'], 'vmi':['vmi4']}, # Mcast receiver
            }

        ret_dict = self.setup_mvpn(mvpn_config=mvpn_config, vn=vn, vmi=vmi,
                                vm=vm)
        vmi_fixtures = ret_dict['vmi_fixtures']
        vn_fixtures = ret_dict['vn_fixtures']
        vm_fixtures = ret_dict['vm_fixtures']
        return ret_dict

    @classmethod
    def tearDownClass(cls):
        super(MVPNTestSingleVNMultiComputeBase, cls).tearDownClass()
    # end tearDownClass

class MVPNTestMultiVNSingleComputeBase(MVPNTestBase, IGMPTestBase):

    @classmethod
    def setUpClass(cls):
        super(MVPNTestMultiVNSingleComputeBase, cls).setUpClass()
        cls.inputs.set_af(cls.get_af())

    def bringup_mvpn_setup(self):
        # MVPN parameters
        mvpn_config = MVPN_CONFIG

        # VN parameters
        vn = {'count':2,
            'vn1':{'subnet':get_random_cidr(), 'asn':64510, 'target':1},
            'vn2':{'subnet':get_random_cidr(), 'asn':64520, 'target':1},
            }

        # VMI parameters
        vmi = {'count':4,
            'vmi1':{'vn': 'vn1'},
            'vmi2':{'vn': 'vn1'},
            'vmi3':{'vn': 'vn2'},
            'vmi4':{'vn': 'vn2'},
            }

        # VM parameters
        vm = {'count':4, 'launch_mode':'non-distribute',
            'vm1':{'vn':['vn1'], 'vmi':['vmi1']}, # Mcast source
            'vm2':{'vn':['vn1'], 'vmi':['vmi2']}, # Mcast receiver
            'vm3':{'vn':['vn2'], 'vmi':['vmi3']}, # Mcast receiver
            'vm4':{'vn':['vn2'], 'vmi':['vmi4']}, # Mcast receiver
            }

        ret_dict = self.setup_mvpn(mvpn_config=mvpn_config, vn=vn, vmi=vmi,
                                vm=vm)
        vmi_fixtures = ret_dict['vmi_fixtures']
        vn_fixtures = ret_dict['vn_fixtures']
        vm_fixtures = ret_dict['vm_fixtures']
        return ret_dict

    @classmethod
    def tearDownClass(cls):
        super(MVPNTestMultiVNSingleComputeBase, cls).tearDownClass()
    # end tearDownClass

class MVPNTestMultiVNMultiComputeBase(MVPNTestBase, IGMPTestBase):

    @classmethod
    def setUpClass(cls):
        super(MVPNTestMultiVNMultiComputeBase, cls).setUpClass()
        cls.inputs.set_af(cls.get_af())

    def bringup_mvpn_setup(self):
        # MVPN parameters
        mvpn_config = MVPN_CONFIG

        # VN parameters
        vn = {'count':2,
            'vn1':{'subnet':get_random_cidr(), 'asn':64510, 'target':1},
            'vn2':{'subnet':get_random_cidr(), 'asn':64520, 'target':1},
            }

        # VMI parameters
        vmi = {'count':4,
            'vmi1':{'vn': 'vn1'},
            'vmi2':{'vn': 'vn1'},
            'vmi3':{'vn': 'vn2'},
            'vmi4':{'vn': 'vn2'},
            }

        # VM parameters
        vm = {'count':4, 'launch_mode':'distribute',
            'vm1':{'vn':['vn1'], 'vmi':['vmi1']}, # Mcast source
            'vm2':{'vn':['vn1'], 'vmi':['vmi2']}, # Mcast receiver
            'vm3':{'vn':['vn2'], 'vmi':['vmi3']}, # Mcast receiver
            'vm4':{'vn':['vn2'], 'vmi':['vmi4']}, # Mcast receiver
            }

        ret_dict = self.setup_mvpn(mvpn_config=mvpn_config, vn=vn, vmi=vmi,
                                vm=vm)
        vmi_fixtures = ret_dict['vmi_fixtures']
        vn_fixtures = ret_dict['vn_fixtures']
        vm_fixtures = ret_dict['vm_fixtures']
        return ret_dict

    @classmethod
    def tearDownClass(cls):
        super(MVPNTestMultiVNMultiComputeBase, cls).tearDownClass()
    # end tearDownClass


