import test_v1
from common.connections import ContrailConnections
from vm_test import VMFixture
from vn_test import VNFixture
from tcutils.util import *
from tcutils.tcpdump_utils import *
from compute_node_test import ComputeNodeFixture
from vnc_api.vnc_api import *
from tcutils.traffic_utils.base_traffic import *
from tcutils.traffic_utils.hping_traffic import Hping3

class BaseVrouterTest(test_v1.BaseTestCase_v1):

    @classmethod
    def setUpClass(cls):
        super(BaseVrouterTest, cls).setUpClass()
        cls.quantum_h = cls.connections.quantum_h
        cls.nova_h = cls.connections.nova_h
        cls.vnc_lib_fixture = cls.connections.vnc_lib_fixture
        cls.vnc_lib = cls.connections.vnc_lib
        cls.agent_inspect = cls.connections.agent_inspect
        cls.cn_inspect = cls.connections.cn_inspect
        cls.analytics_obj = cls.connections.analytics_obj
        cls.api_s_inspect = cls.connections.api_server_inspect
        cls.orch = cls.connections.orch
        cls.compute_ips = cls.inputs.compute_ips 
        cls.compute_fixtures_dict = {}

        for ip in cls.compute_ips:
            cls.compute_fixtures_dict[ip] = ComputeNodeFixture(
                                        cls.connections,ip)
            cls.compute_fixtures_dict[ip].setUp()
    #end setUpClass

    @classmethod
    def tearDownClass(cls):
        for ip in cls.compute_ips:
            cls.compute_fixtures_dict[ip].cleanUp()
        super(BaseVrouterTest, cls).tearDownClass()
    # end tearDownClass

    def create_vn(self, count=1, *args, **kwargs):
        vn_fixtures = []
        for i in xrange(count): 
            vn_fixtures.append(self.useFixture(
                        VNFixture(project_name=self.inputs.project_name,
                                  connections=self.connections,
                                  inputs=self.inputs,
                                  *args, **kwargs
                                  )) )

        return vn_fixtures

    def verify_vn(self, vn_fixtures):
        for vn_fixture in vn_fixtures:
            assert vn_fixture.verify_on_setup()

    def create_vm(self, vn_fixture, count=1, image_name='ubuntu-traffic', *args, **kwargs):
        vm_fixtures = []
        for i in xrange(count):
            vm_fixtures.append(self.useFixture(
                        VMFixture(
                            project_name=self.inputs.project_name,
                            connections=self.connections,
                            vn_obj=vn_fixture.obj,
                            image_name=image_name,
                            *args, **kwargs
                            )) )

        return vm_fixtures

    def _remove_from_cleanup(self, fixture):
        for cleanup in self._cleanups:
            if hasattr(cleanup[0],'__self__') and fixture == cleanup[0].__self__:
                self._cleanups.remove(cleanup)
                return True
        return False

    def delete_vm(self, vm_fixtures):
        for vm_fixture in vm_fixtures:
            self._remove_from_cleanup(vm_fixture)
            vm_fixture.cleanUp()

    def verify_vm(self, vm_fixtures):
        for vm_fixture in vm_fixtures:
            assert vm_fixture.verify_on_setup()
        for vm_fixture in vm_fixtures:
            assert vm_fixture.wait_till_vm_is_up()

    def add_static_routes_on_vm(self,prefix, vm_fixtures, ip=None):
        if ip is None:
            #get a random IP from the prefix and configure it on the VMs
            ip = get_random_ip(prefix)
        for vm_fixture in vm_fixtures:
            vmi_ids = vm_fixture.get_vmi_ids().values()
            for vmi_id in vmi_ids:
                route_table_name = get_random_name('my_route_table')
                vm_fixture.provision_static_route(
                                prefix=prefix, 
                                tenant_name=self.inputs.project_name,
                                oper='add',
                                virtual_machine_interface_id=vmi_id,
                                route_table_name=route_table_name,
                                user=self.inputs.stack_user,
                                password=self.inputs.stack_password)
                assert vm_fixture.config_virtual_interface(ip)

        return ip

    def disable_policy_on_vmi(self, vmi_ids, disable=True):
        '''vmi_ids: list of VMIs'''

        log_str = 'DISABLED' if disable else 'ENABLED'

        for vmi_id in vmi_ids:
            vmi_obj = self.vnc_lib.virtual_machine_interface_read(id=vmi_id)
            vmi_obj.set_virtual_machine_interface_disable_policy(disable)
            self.vnc_lib.virtual_machine_interface_update(vmi_obj)
            self.logger.info("Policy %s on VMI %s" % (log_str, vmi_id))

    def disable_policy_for_vm(self, vm_fixtures, disable=True):
        for vm in vm_fixtures:
            vmi_ids = vm.get_vmi_ids().values()         
            self.disable_policy_on_vmi(vmi_ids, disable)

        return True

    def config_fat_flow_on_vmi(self,vmi_ids,fat_flow_config={'proto':'udp','port':53}):
        '''vmi_ids: list of vmi ids
           fat_flow_config: dictionary of format {'proto':<string>,'port':<int>}
        '''
        proto_type = ProtocolType(protocol=fat_flow_config['proto'],
                        port=fat_flow_config['port'])
        fat_config_obj = FatFlowProtocols(fat_flow_protocol=[proto_type])

        for vmi_id in vmi_ids:
            vmi_obj = self.vnc_lib.virtual_machine_interface_read(id=vmi_id)
            vmi_obj.set_virtual_machine_interface_fat_flow_protocols(
                                                    fat_config_obj)
            self.vnc_lib.virtual_machine_interface_update(vmi_obj)
            self.logger.info("Fat flow configured on VMI %s: %s" % (
                                vmi_id, fat_flow_config))

        return True

    def set_proto_based_flow_aging_time(self, proto, port, timeout=180):
        self.vnc_lib_fixture.set_proto_based_flow_aging_time(proto, port, timeout)
        self.addCleanup(self.vnc_lib_fixture.delete_proto_based_flow_aging_time,
                                proto, port, timeout)

        return True

    def verify_traffic_load_balance(self, sender_vm_fix,
                                dest_vm_fix_list, dest_ip):
        try_count = len(dest_vm_fix_list) + 1 
        packet_count = 1 
        session = {}
        pcap = {}
        compute_node_ips = []
        compute_fixtures = []
        proto = 'icmp'
        destport = '11000'
        baseport = '10000'
        interval = 'u100'

        #Get all the VMs compute IPs 
        compute_node_ips.append(sender_vm_fix.vm_node_ip)
        for vm in dest_vm_fix_list:
            if vm.vm_node_ip not in compute_node_ips:
                compute_node_ips.append(vm.vm_node_ip)

        #Get the compute fixture for all the concerned computes
        for ip in compute_node_ips:
            compute_fixtures.append(self.compute_fixtures_dict[ip])

        #Send traffic multiple times to verify load distribution
        for i in xrange(try_count):
            result = True

            #Start the tcpdump on all the destination VMs
            for vm in dest_vm_fix_list:
                filters = '\'(tcp and src host %s and dst host %s and dst port %s)\'' % (
                                            sender_vm_fix.vm_ip, dest_ip, int(destport))
                session[vm], pcap[vm] = start_tcpdump_for_vm_intf(self, vm,
                                            vm.vn_fq_names[0], filters = filters)

            hping_h = Hping3(sender_vm_fix,
                             dest_ip,
                             syn=True,
                             destport=destport,
                             baseport=baseport,
                             count=try_count,
                             interval=interval)
            hping_h.start(wait=False)
            (stats, hping_log) = hping_h.stop()
            self.logger.debug('Hping3 log : %s' % (hping_log))
            assert stats['loss'] == '0', ('Some loss seen in hping3 session'
                                          'Stats : %s, Check logs..' % (stats))
            assert stats['sent'] == stats['received'], ('Sent count and '
                                        'received count are not same.Stats: %s'
                                        % (stats))

            #Verify tcpdump count, all destinations should receive some packets
            for vm in dest_vm_fix_list:
                ret = verify_tcpdump_count(self, session[vm], pcap[vm])
                if not ret:
                    self.logger.debug("Tcpdump verification on VM %s failed" %
                                        vm.vm_ip)
                    stop_tcpdump_for_vm_intf(self, session[vm], pcap[vm])
                delete_pcap(session[vm], pcap[vm]) 
                result = result and ret 

            #Verify flow count 0, on all the computes 
            for fixture in compute_fixtures:
                (ff_count, rf_count) = fixture.get_flow_count(
                    source_ip=sender_vm_fix.vm_ip,
                    dest_ip=dest_ip,
                    proto=proto,
                    vrf_id=fixture.get_vrf_id(
                              sender_vm_fix.vn_fq_names[0])
                    )
                assert ff_count == 0, 'Flows created when policy is disabled'
                assert rf_count == 0, 'Flows created when policy is disabled' 
            
            if result:
                self.logger.info("Traffic is distributed to all the ECMP routes"
                        " as expected")
                return result 

        return result

    def verify_fat_flow_with_traffic(self, sender_vm_fix_list, dst_vm_fix,
                                        proto, dest_port, traffic=True,
                                        expectation=True):

        if expectation:
            expected_count = 1
        else:
            expected_count = 0
        #Use 2 different source ports for each sender VM
        sport_list = [10000, 10001]
        dst_compute_fix = self.compute_fixtures_dict[dst_vm_fix.vm_node_ip]

        #Start the traffic from each of the VM in sender_vm_fix_list to dst_vm_fix 
        if traffic:
            for fix in sender_vm_fix_list:
                for port in sport_list:
                    traffic_obj = BaseTraffic.factory(proto=proto)
                    assert traffic_obj
                    assert traffic_obj.start(fix, dst_vm_fix,
                                          proto, port, dest_port)
                    sent, recv = traffic_obj.stop()

        #Verify the flows on sender computes for each sender/receiver VMs and port tuples
        for fix in sender_vm_fix_list:
            for port in sport_list:
                compute_fix = self.compute_fixtures_dict[fix.vm_node_ip]
                (ff_count, rf_count) = compute_fix.get_flow_count(
                                            source_ip=fix.vm_ip,
                                            dest_ip=dst_vm_fix.vm_ip,
                                            source_port=port,
                                            dest_port=dest_port,
                                            proto=proto,
                                            vrf_id=compute_fix.get_vrf_id(
                                                      fix.vn_fq_names[0])
                                            )
                assert ff_count == expected_count, ('Flows count mismatch on '
                                'sender compute, got:%s, expected:%s' % (
                                ff_count, expected_count))
                assert rf_count == expected_count, ('Flows count mismatch on '
                                'sender compute, got:%s, expected:%s' % (
                                rf_count, expected_count)) 

                #For the case when sender and receiver are on different nodes
                #Flow with source and dest port should not be created on dest node
                if dst_vm_fix.vm_node_ip != fix.vm_node_ip:
                    (ff_count, rf_count) = dst_compute_fix.get_flow_count(
                                                source_ip=fix.vm_ip,
                                                dest_ip=dst_vm_fix.vm_ip,
                                                source_port=port,
                                                dest_port=dest_port,
                                                proto=proto,
                                                vrf_id=dst_compute_fix.get_vrf_id(
                                                          dst_vm_fix.vn_fq_names[0])
                                                )
                    assert ff_count == 0, ('Flows created with source port on '
                                'dest compute for Fat flow')
                    assert rf_count == 0, ('Flows created with source port on '
                                'dest compute for Fat flow')

        #FAT flow verification on destination compute
        for fix in sender_vm_fix_list:
            if dst_vm_fix.vm_node_ip == fix.vm_node_ip:
                #When sender and receiver VM are on same node, no FAT flow will be created
                fat_flow_count = 0
            else:
                #When sender and receiver VMs are on different node,
                #FAT flow will be created with source port ZERO
                fat_flow_count = expected_count 
            #Get Fat flow, with source port as ZERO
            (ff_count, rf_count) = dst_compute_fix.get_flow_count(
                                        source_ip=fix.vm_ip,
                                        dest_ip=dst_vm_fix.vm_ip,
                                        source_port=0,
                                        dest_port=dest_port,
                                        proto=proto,
                                        vrf_id=dst_compute_fix.get_vrf_id(
                                                  dst_vm_fix.vn_fq_names[0])
                                        )
            assert ff_count == fat_flow_count, ('Fat flow count mismatch on '
                'dest compute, got:%s, exp:%s' % (ff_count, fat_flow_count))
            assert rf_count == fat_flow_count, ('Fat flow count mismatch on '
                'dest compute, got:%s, exp:%s' % (rf_count, fat_flow_count))

        self.logger.info("Fat flow verification passed") 
        return True
