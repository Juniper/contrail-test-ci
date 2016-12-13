from tcutils.util import *
import fixtures
import re

class DropStats(fixtures.TestWithFixtures) :

    def get_drop_stats_dict(self, compute, module='vrouter', intf_id=None):
        cmd = 'dropstats'
        if module == 'vif':
            cmd = 'vif --get ' + intf_id  + ' --get-drop-stats'
        drop_stats = self.inputs.run_cmd_on_server(compute, cmd)
        drop_stats = drop_stats.split('\r\n')
        while '' in drop_stats:
            drop_stats.remove('')
        drop_stats_dict = {}
        self.logger.info("Executing %s on %s" %(cmd, module))
        for field in drop_stats:
            stats_value = ''
            stats_list = re.split('\s\s\s+', field)
            stats_field_name = stats_list[0]
            print field
            if len(stats_list) > 1:
                stats_value = stats_list[1]
            drop_stats_dict[stats_field_name] = stats_value
        return drop_stats_dict
    # end get_drop_stats_dict


    def verify_flow_action_drop_stats(self, drop_type='Flow Action Drop'):
        result = True
        ping_count = 5
        image_name = 'cirros-0.3.0-x86_64-uec'

        compute_ips = self.inputs.compute_ips
        compute0 = compute_ips[0]
        compute1 = compute0
        compute0_name =  hostname = self.inputs.host_data[compute0]['name']
        compute1 = compute_ips[1]
        compute1_name =  hostname = self.inputs.host_data[compute1]['name']

        self.create_verify_vn_vm(compute0_name, compute1_name, image_name)

        tap = self.vm1_fixture.get_tap_intf_of_vm()[0]['name']
        intf_details = self.agent_inspect[compute0].get_vna_intf_details(tap)
        vif_index = intf_details[0]['index']

        vif_dict_before = self.get_drop_stats_dict(compute0, module='vif', intf_id=vif_index)
        vrouter_dict_before = self.get_drop_stats_dict(compute0)

        assert not self.vm1_fixture.ping_to_ip(self.vm2_ip, count=ping_count)

        vif_dict_after = self.get_drop_stats_dict(compute0, module='vif', intf_id=vif_index)
        vrouter_dict_after = self.get_drop_stats_dict(compute0)
        
        if not self.verify_dropstats_of_type(drop_type, vif_dict_before, 
            vrouter_dict_before, vif_dict_after, vrouter_dict_after, ping_count):
                result = result and False
        
        return result
    # end verify_flow_action_drop_stats
    
    def create_verify_vn_vm(self, compute0_name, compute1_name, image_name):
        self.vn1_subnets = [get_random_cidr(af=self.inputs.get_af())]
        self.vn2_subnets = [get_random_cidr(af=self.inputs.get_af())]

        self.vn1_fq_name = "default-domain:" + self.inputs.project_name + \
            ":" + get_random_name("vn1")
        self.vn2_fq_name = "default-domain:" + self.inputs.project_name + \
            ":" + get_random_name("vn2")

        self.vn1_name = self.vn1_fq_name.split(':')[2]
        self.vn2_name = self.vn2_fq_name.split(':')[2]

        self.vn1_fixture = self.create_vn(self.vn1_name, self.vn1_subnets)
        self.vn2_fixture = self.create_vn(self.vn2_name, self.vn2_subnets)

        self.policy_name_vn1_vn2 = get_random_name("vn1_vn2_deny")

        self.rules_vn1_vn2 = [{'direction': '<>',
                       'protocol': 'icmp',
                       'source_network': self.vn1_name,
                       'src_ports': [0, -1],
                       'dest_network': self.vn2_name,
                       'dst_ports': [0, -1],
                       'simple_action': 'deny',
                       'action_list': {'simple_action': 'deny'}
                       },
                       {'direction': '<>',
                       'protocol': 'icmp6',
                       'source_network': self.vn1_name,
                       'src_ports': [0, -1],
                       'dest_network': self.vn2_name,
                       'dst_ports': [0, -1],
                       'simple_action': 'deny',
                       'action_list': {'simple_action': 'deny'}
                       }]

        self.vm1_name = get_random_name("vm1")
        self.vm2_name = get_random_name("vm2")

        self.vm1_fixture = self.create_vm(
            vn_fixture=self.vn1_fixture, vm_name=self.vm1_name, node_name=compute0_name, image_name=image_name)
        self.vm2_fixture = self.create_vm(
            vn_fixture=self.vn2_fixture, vm_name=self.vm2_name, node_name=compute1_name, image_name=image_name)

        assert self.vm1_fixture.verify_on_setup()
        assert self.vm2_fixture.verify_on_setup()
        self.nova_h.wait_till_vm_is_up(self.vm1_fixture.vm_obj)
        self.nova_h.wait_till_vm_is_up(self.vm2_fixture.vm_obj)

        self.vm1_ip = self.vm1_fixture.get_vm_ips(self.vn1_fq_name)[0]
        self.vm2_ip = self.vm2_fixture.get_vm_ips(self.vn2_fq_name)[0]
   # end create_verify_vn_vm
    
    def verify_dropstats_of_type(self, drop_type, vif_dict_before, 
            vrouter_dict_before, vif_dict_after, vrouter_dict_after, ping_count):
        result = True

        vif_drop_before = int(vif_dict_before[drop_type])
        vif_drop_after = int(vif_dict_after[drop_type])
       
        vif_diff = vif_drop_after - vif_drop_before

        if vif_diff == ping_count:
            self.logger.info("Vif dropstats of type %s verifed" % drop_type)
        else:
            result = result and False
            self.logger.info("Vif dropstats of type %s failed" % drop_type)

        vrouter_drop_before = int(vrouter_dict_before[drop_type])
        vrouter_drop_after = int(vrouter_dict_after[drop_type])

        vrouter_diff = vrouter_drop_after - vrouter_drop_before

        if vrouter_diff == ping_count:
            self.logger.info("Vrouter dropstats of type %s verifed" % drop_type)
        else:
            self.logger.info("Vrouter dropstats of type %s failed" % drop_type)
            result = result and False
        return result
    # end verify_dropstats_of_type
