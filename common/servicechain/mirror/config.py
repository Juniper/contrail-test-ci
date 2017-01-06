import os
from tcutils.util import get_random_cidr
from tcutils.util import get_random_name
from common.servicechain.verify import VerifySvcChain


class ConfigSvcMirror(VerifySvcChain):
    ''' Class for mirroring specific config routines
    '''

    def config_svc_mirroring(self, service_mode='transparent', *args, **kwargs):
        """Validate the service chaining datapath
           Test steps:
           1. Create the SI/ST in svc_mode specified.
           2. Create vn11/vm1, vn21/vm2
           3. Create the policy rule for ICMP/UDP and attach to vn's
           4. Send the traffic from vm1 to vm2 and verify if the packets gets mirrored to the analyzer
           5. If its a single analyzer only ICMP(5 pkts) will be sent else ICMP and UDP traffic will be sent.
           Pass criteria :
           count = sent
           single node : Pkts mirrored to the analyzer should be equal to 'count'
           multinode :Pkts mirrored to the analyzer should be equal to '2xcount'
        """
        ci = False
        if os.environ.get('ci_image'):
            ci = True
        create_svms = kwargs.get('create_svms', True)
        vn1_subnets = [get_random_cidr(af=self.inputs.get_af())]
        vn2_subnets = [get_random_cidr(af=self.inputs.get_af())]
        vn1_name = get_random_name('left')
        vn2_name = get_random_name('right')
        st_name = get_random_name("st1")
#        self.vn1_fq_name = "default-domain:" + self.inputs.project_name + \
#            ":" + get_random_name("in_network_vn1")
#        self.vn1_name = self.vn1_fq_name.split(':')[2]
#        self.vn1_subnets = vn1_subnets
#        self.vm1_name = get_random_name("in_network_vm1")
#        self.vn2_fq_name = "default-domain:" + self.inputs.project_name + \
#            ":" + get_random_name("in_network_vn2")
#        self.vn2_name = self.vn2_fq_name.split(':')[2]
#        self.vn2_subnets = vn2_subnets
#        self.vm2_name = get_random_name("in_network_vm2")
#
#        si_count = si_count
        action_list = []
        service_type = 'analyzer'
#        self.if_list = []
        si_prefix = get_random_name("mirror_si")
        policy_name = get_random_name("mirror_policy")
        vn1_fixture = self.config_vn(vn1_name, vn1_subnets)
        vn2_fixture = self.config_vn(vn2_name, vn2_subnets)
#        if ci:
#            svc_img_name = 'cirros-0.3.0-x86_64-uec'
#            image_name = 'cirros-0.3.0-x86_64-uec'
#        else:
#            svc_img_name = "vsrx"
#            image_name = 'ubuntu-traffic'
#        if svc_mode == 'in-network':
#           svc_img_name = 'ubuntu-in-net'
#        self.st_fixture, self.si_fixtures = self.config_st_si(self.st_name,
#                                                              self.si_prefix, si_count, left_vn_fixture=None, svc_type='analyzer', svc_mode=svc_mode, project=self.inputs.project_name, svc_img_name=svc_img_name, st_version=st_version)
#        self.action_list = self.chain_si(
#            si_count, self.si_prefix, self.inputs.project_name)

        ret_dict = self.verify_svc_chain(service_mode=service_mode,
                                         service_type=service_type,
                                         left_vn_fixture=vn1_fixture,
                                         right_vn_fixture=vn2_fixture,
                                         create_svms=create_svms)
        si_fixture = ret_dict['si_fixture']
        policy_fixture = ret_dict['policy_fixture']
        si_fq_name = si_fixture.fq_name_str
        rules = [{'direction': '<>',
                       'protocol': 'icmp',
                       'source_network': vn1_fixture.vn_fq_name,
                       'src_ports': [0, 65535],
                       'dest_network': vn2_fixture.vn_fq_name,
                       'dst_ports': [0, 65535],
                       'action_list': {'simple_action': 'pass',
                                       'mirror_to': {'analyzer_name': si_fq_name}}
                       },
                       {'direction': '<>',
                       'protocol': 'icmp6',
                       'source_network': vn1_fixture.vn_fq_name,
                       'src_ports': [0, 65535],
                       'dest_network': vn2_fixture.vn_fq_name,
                       'dst_ports': [0, 65535],
                       'action_list': {'simple_action': 'pass',
                                       'mirror_to': {'analyzer_name': si_fq_name}}
                       }]
        policy_fixture.update_policy_api(rules)
#        if len(self.action_list) == 2:
#            self.rules.append({'direction': '<>',
#                               'protocol': 'udp',
#                               'source_network': self.vn1_name,
#                               'src_ports': [0, 65535],
#                               'dest_network': self.vn2_name,
#                               'dst_ports': [0, 65535],
#                               'simple_action': 'pass',
#                               'action_list': {'simple_action': 'pass',
#                                               'mirror_to': {'analyzer_name': self.action_list[1]}}
#                               }
#                              )
#        self.policy_fixture = self.config_policy(self.policy_name, self.rules)
#
#        self.vn1_policy_fix = self.attach_policy_to_vn(
#            self.policy_fixture, self.vn1_fixture)
#        self.vn2_policy_fix = self.attach_policy_to_vn(
#            self.policy_fixture, self.vn2_fixture)
#
#        # Making sure VM falls on diffrent compute host
#        host_list = []
#        for host in self.inputs.compute_ips:
#            host_list.append(self.inputs.host_data[host]['name'])
#        compute_1 = host_list[0]
#        compute_2 = host_list[0]
#        if len(host_list) > 1:
#            compute_1 = host_list[0]
#            compute_2 = host_list[1]
#        self.vm1_fixture = self.config_vm(
#            vn_fix=self.vn1_fixture, vm_name=self.vm1_name, node_name=compute_1, image_name=image_name)
#        self.vm2_fixture = self.config_vm(
#            vn_fix=self.vn2_fixture, vm_name=self.vm2_name, node_name=compute_2, image_name=image_name)
#        assert self.vm1_fixture.verify_on_setup()
#        assert self.vm2_fixture.verify_on_setup()
#        self.nova_h.wait_till_vm_is_up(self.vm1_fixture.vm_obj)
#        self.nova_h.wait_till_vm_is_up(self.vm2_fixture.vm_obj)
#        result, msg = self.validate_vn(
#            self.vn1_name, project_name=self.inputs.project_name)
#        assert result, msg
#        result, msg = self.validate_vn(
#            self.vn2_name, project_name=self.inputs.project_name)
#        assert result, msg

#        self.verify_si(self.si_fixtures)
        # Verify ICMP traffic mirror
#        left_vm_fixture = ret_dict['left_vm_fixture']
#        right_vm_fixture = ret_dict['right_vm_fixture']
#        si_fixture = ret_dict['si_fixture']
#        if ci:
#            return self.verify_mirroring(si_fixture, vm1_fixture, vm2_fixture)
#        self.verify_proto_based_mirror(si_fixture, left_vm_fixture,
#                                       right_vm_fixture, 'icmp')
        # One mirror instance
#        if len(self.action_list) != 2:
#            return True
#
#        # Verify UDP traffic mirror
#        sessions = self.tcpdump_on_all_analyzer(self.si_fixtures, self.si_prefix)
#        # Install traffic package in VM
#        self.vm1_fixture.install_pkg("Traffic")
#        self.vm2_fixture.install_pkg("Traffic")
#
#        sport = 8001
#        dport = 9001
#        sent, recv = self.verify_traffic(self.vm1_fixture, self.vm2_fixture,
#                                         'udp', sport=sport, dport=dport)
#        errmsg = "UDP traffic with src port %s and dst port %s failed" % (
#            sport, dport)
#        assert sent and recv == sent, errmsg
#        for svm_name, (session, pcap) in sessions.items():
#            count = sent
#            svm = {}
#            svm = self.get_svms_in_si(self.si_fixtures[1])
#            if svm_name == svm[0].name:
#                count = sent
#                if svc_mode == 'transparent' and self.vm1_fixture.vm_node_ip != self.vm2_fixture.vm_node_ip:
#                    count = count * 2
#                self.verify_l4_mirror(svm_name, session, pcap, count, 'udp')

        return ret_dict
    # end config_svc_mirroring
