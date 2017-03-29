import time
import paramiko
import fixtures
from fabric.api import run, hide, settings
from tcutils.commands import ssh, execute_cmd, execute_cmd_out
from tcutils.util import get_random_cidr
from tcutils.util import get_random_name
from tcutils.cfgparser import parse_cfg_file
from vn_test import VNFixture
from vm_test import VMFixture
from policy_test import PolicyFixture
from floating_ip import FloatingIPFixture
from svc_instance_fixture import SvcInstanceFixture
from svc_template_fixture import SvcTemplateFixture
from common.connections import ContrailConnections
from common.policy.config import AttachPolicyFixture
from tcutils.util import retry
import random
import re

class ConfigSvcChain(fixtures.Fixture):

    def __init__(self, use_vnc_api=False, connections=None):
        self.use_vnc_api = use_vnc_api
        if connections:
            self.connections = connections
            self.inputs = connections.inputs
            self.orch = connections.orch
            self.vnc_lib = connections.vnc_lib
            self.logger = connections.logger
        super(ConfigSvcChain, self).__init__()

    def delete_si_st(self, si_fixtures, st_fix):
        for si_fix in si_fixtures:
            self.logger.debug("Delete SI '%s'", si_fix.si_name)
            si_fix.cleanUp()
            self.remove_from_cleanups(si_fix.cleanUp)

        self.logger.debug("Delete ST '%s'", st_fix.st_name)
        st_fix.cleanUp()
        self.remove_from_cleanups(st_fix.cleanUp)

    def config_st_si(self, st_name, si_name_prefix, si_count,
                     svc_scaling=False, max_inst=1, domain= None,
                     project='admin', mgmt_vn_fixture=None, left_vn_fixture=None,
                     right_vn_fixture=None, svc_type='firewall',
                     svc_mode='transparent', flavor='contrail_flavor_2cpu',
                     static_route=[None, None, None], ordered_interfaces=True,
                     svc_img_name=None, st_version=1):
        domain = domain or self.connections.domain_name
        svc_type_props = {
            'firewall': {'in-network-nat': 'tiny_nat_fw',
                         'in-network': 'tiny_in_net',
                         'transparent': 'tiny_trans_fw',
                         },
            'analyzer': {'transparent': 'analyzer',
                         'in-network' : 'analyzer',
                         }
        }

        svc_mode_props = {
            'in-network-nat':   {'left': {'shared': True},
                                 'right': {'shared': False},
                                 },
            'in-network':       {'left': {'shared': True},
                                 'right': {'shared': True}
                                 },
            'transparent':      {'left': {'shared': True},
                                 'right': {'shared': True}
                                 }
        }

        mgmt_props = ['management', False, False]
        left_scaling = False
        right_scaling = False
        if svc_scaling:
            left_scaling = True
            right_scaling = svc_mode_props[svc_mode]['right']['shared']
        svc_img_name = svc_img_name or svc_type_props[svc_type][svc_mode]
        images_info = parse_cfg_file('configs/images.cfg')
        flavor = flavor or images_info[svc_img_name]['flavor']
        if_list = [mgmt_props,
                   ['left', left_scaling, bool(static_route[1])],
                   ['right', right_scaling, bool(static_route[2])],
                   ]
        if svc_type == 'analyzer':
            left_scaling = svc_mode_props[svc_mode]['left']['shared']
            if_list = [['left', left_scaling, bool(static_route[1])]]

        self.logger.debug('SI properties:'"\n"
                          'type: %s '"\n"
                          'mode: %s' "\n"
                          'image: %s' "\n"
                          'flavor: %s' "\n"
                          'intf_list: %s' % (svc_type, svc_mode, svc_img_name, flavor, if_list))
        # create service template
        st_fixture = self.useFixture(SvcTemplateFixture(
            connections=self.connections, inputs=self.inputs, domain_name=domain,
            st_name=st_name, svc_img_name=svc_img_name, svc_type=svc_type,
            if_list=if_list, svc_mode=svc_mode, svc_scaling=svc_scaling, flavor=flavor, ordered_interfaces=ordered_interfaces, version=st_version))
        assert st_fixture.verify_on_setup()

        mgmt_vn_name = mgmt_vn_fixture.vn_fq_name if mgmt_vn_fixture else None
        left_vn_name=left_vn_fixture.vn_fq_name if left_vn_fixture else None
        right_vn_name=right_vn_fixture.vn_fq_name if right_vn_fixture else None

        # create service instances
        si_fixtures = []
        for i in range(0, si_count):
            verify_vn_ri = True
            if i:
                verify_vn_ri = False
            si_name = si_name_prefix + str(i + 1)
            si_fixture = self.useFixture(SvcInstanceFixture(
                connections=self.connections, inputs=self.inputs,
                domain_name=domain, project_name=project, si_name=si_name,
                svc_template=st_fixture.st_obj, if_list=if_list,
                mgmt_vn_name=mgmt_vn_name,
                left_vn_name=left_vn_name,
                right_vn_name=right_vn_name,
                do_verify=verify_vn_ri, max_inst=max_inst,
                static_route=static_route))
            if st_version == 2:
                self.logger.debug('Launching SVM')
                if svc_mode == 'transparent':
                    self.trans_mgmt_vn_name = get_random_name('trans_mgmt_vn')
                    self.trans_mgmt_vn_subnets = [
                        get_random_cidr(af=self.inputs.get_af())]
                    self.trans_left_vn_name = get_random_name('trans_left_vn')
                    self.trans_left_vn_subnets = [
                        get_random_cidr(af=self.inputs.get_af())]
                    self.trans_right_vn_name = get_random_name(
                        'trans_right_vn')
                    self.trans_right_vn_subnets = [
                        get_random_cidr(af=self.inputs.get_af())]
                    self.trans_mgmt_vn_fixture = self.config_vn(
                        self.trans_mgmt_vn_name, self.trans_mgmt_vn_subnets)
                    self.trans_left_vn_fixture = self.config_vn(
                        self.trans_left_vn_name, self.trans_left_vn_subnets)
                    self.trans_right_vn_fixture = self.config_vn(
                        self.trans_right_vn_name, self.trans_right_vn_subnets)
                non_docker_zones = [x for x in self.nova_h.zones if x != 'nova/docker']
                for i in range(max_inst):
                    svm_name = get_random_name("pt_svm" + str(i))
                    pt_name = get_random_name("port_tuple" + str(i))
                    if svc_mode == 'transparent':
                        svm_vns = [self.trans_mgmt_vn_fixture, self.trans_left_vn_fixture, self.trans_right_vn_fixture]
                        if svc_type == 'analyzer':
                            svm_vns = [self.trans_left_vn_fixture]
                        svm_fixture = self.config_and_verify_vm(
                            svm_name, image_name=svc_img_name, vns=svm_vns, count=1, flavor='m1.large',
                            zone=random.choice(non_docker_zones))
                    else:
                        svm_vns = [mgmt_vn_fixture, left_vn_fixture,
                                   right_vn_fixture]
                        if svc_type == 'analyzer':
                            svm_vns = [left_vn_fixture]
                        svm_fixture = self.config_and_verify_vm(
                            svm_name, image_name=svc_img_name,
                            vns=svm_vns,
                            count=1, flavor='m1.large',
                            zone=random.choice(non_docker_zones))
                    si_fixture.add_port_tuple(svm_fixture, pt_name)
            si_fixture.verify_on_setup()
            si_fixtures.append(si_fixture)

        return (st_fixture, si_fixtures)

    def chain_si(self, si_count, si_prefix, project_name):
        action_list = []
        for i in range(0, si_count):
            si_name = si_prefix + str(i + 1)
            # chain services by appending to action list
            si_fq_name = self.connections.domain_name  + ':' + project_name + ':' + si_name
            action_list.append(si_fq_name)
        return action_list

    def config_policy(self, policy_name, rules):
        """Configures policy."""
        use_vnc_api = getattr(self, 'use_vnc_api', None)
        # create policy
        policy_fix = self.useFixture(PolicyFixture(
            policy_name=policy_name, rules_list=rules,
            inputs=self.inputs, connections=self.connections,
            api=use_vnc_api))
        return policy_fix

    def config_vn(self, vn_name, vn_net,**kwargs):
        vn_fixture = self.useFixture(VNFixture(
            project_name=self.inputs.project_name, connections=self.connections,
            vn_name=vn_name, inputs=self.inputs, subnets=vn_net,**kwargs))
        vn_fixture.read()
        assert vn_fixture.verify_on_setup()
        return vn_fixture

    def attach_policy_to_vn(self, policy_fix, vn_fix, policy_type=None):
        policy_attach_fix = self.useFixture(AttachPolicyFixture(
            self.inputs, self.connections, vn_fix, policy_fix, policy_type))
        return policy_attach_fix

    def config_and_verify_vm(self, vm_name, vn_fix=None, image_name='ubuntu-traffic', vns=[], count=1, flavor='contrail_flavor_small',
            zone=None,**kwargs):
        if vns:
            vn_objs = [vn.obj for vn in vns]
            vm_fixture = self.config_vm(
                vm_name, vns=vn_objs, image_name=image_name, count=count,
                flavor=flavor, zone=zone,**kwargs)
        else:
            vm_fixture = self.config_vm(
                vm_name, vn_fix=vn_fix, image_name=image_name, count=count,
                flavor=flavor, zone=zone,**kwargs)
        assert vm_fixture.verify_on_setup(), 'VM verification failed'
        assert vm_fixture.wait_till_vm_is_up(), 'VM does not seem to be up'
        return vm_fixture

    def config_vm(self, vm_name, vn_fix=None, node_name=None, image_name='ubuntu-traffic', flavor='contrail_flavor_small', vns=[], count=1,
            zone=None,**kwargs):
        if vn_fix:
            vm_fixture = self.useFixture(VMFixture(
                project_name=self.inputs.project_name, connections=self.connections,
                vn_obj=vn_fix.obj, vm_name=vm_name, node_name=node_name, image_name=image_name, flavor=flavor, count=count,
                zone=zone,**kwargs))
        elif vns:
            vm_fixture = self.useFixture(VMFixture(
                project_name=self.inputs.project_name, connections=self.connections,
                vm_name=vm_name, node_name=node_name, image_name=image_name, flavor=flavor, vn_objs=vns, count=count,
                zone=zone,**kwargs))

        return vm_fixture

    def config_fip(self, vn_id, pool_name):
        fip_fixture = self.useFixture(FloatingIPFixture(
            project_name=self.inputs.project_name, inputs=self.inputs,
            connections=self.connections, pool_name=pool_name,
            vn_id=vn_id))
        return fip_fixture

    def detach_policy(self, vn_policy_fix):
        self.logger.debug("Removing policy from '%s'",
                          vn_policy_fix.vn_fixture.vn_name)
        vn_policy_fix.cleanUp()
        self.remove_from_cleanups(vn_policy_fix.cleanUp)

    def unconfig_policy(self, policy_fix):
        """Un Configures policy."""
        self.logger.debug("Delete policy '%s'", policy_fix.policy_name)
        policy_fix.cleanUp()
        self.remove_from_cleanups(policy_fix.cleanUp)

    def delete_vn(self, vn_fix):
        self.logger.debug("Delete vn '%s'", vn_fix.vn_name)
        vn_fix.cleanUp()
        self.remove_from_cleanups(vn_fix.cleanUp)

    def delete_vm(self, vm_fix):
        self.logger.debug("Delete vm '%s'", vm_fix.vm_name)
        vm_fix.cleanUp()
        self.remove_from_cleanups(vm_fix.cleanUp)

    def get_svm_obj(self, vm_name):
        for vm_obj in self.nova_h.get_vm_list():
            if vm_obj.name == vm_name:
                return vm_obj
        errmsg = "No VM named '%s' found in the compute" % vm_name
        self.logger.error(errmsg)
        assert False, errmsg

    @retry(delay=10, tries=15)
    def is_svm_active(self, vm_name):
        vm_status = self.get_svm_obj(vm_name).status
        if vm_status == 'ACTIVE':
            self.logger.debug('SVM state is active')
            return True
        else:
            self.logger.warn('SVM %s is not yet active. Current state: %s' %
                             (vm_name, vm_status))
            return False

    def get_svm_compute(self, svm_name):
        svm_obj = self.get_svm_obj(svm_name)
        vm_nodeip = self.inputs.host_data[
            self.nova_h.get_nova_host_of_vm(svm_obj)]['host_ip']
        return self.inputs.host_data[vm_nodeip]

    def get_svm_tapintf(self, svm_name):
        self.is_svm_active(svm_name)
        svm_obj = self.get_svm_obj(svm_name)
        vm_nodeip = self.inputs.host_data[
            self.nova_h.get_nova_host_of_vm(svm_obj)]['host_ip']
        inspect_h = self.agent_inspect[vm_nodeip]
        self.logger.debug(
            "svm_obj:'%s' compute_ip:'%s' agent_inspect:'%s'", svm_obj.__dict__,
            vm_nodeip, inspect_h.get_vna_tap_interface_by_vm(vm_id=svm_obj.id))
        return inspect_h.get_vna_tap_interface_by_vm(vm_id=svm_obj.id)[0]['name']

    def get_bridge_svm_tapintf(self, svm_name, direction):
        self.is_svm_active(svm_name)
        svm_obj = self.get_svm_obj(svm_name)
        vm_nodeip = self.inputs.host_data[
            self.nova_h.get_nova_host_of_vm(svm_obj)]['host_ip']
        inspect_h = self.agent_inspect[vm_nodeip]
        self.logger.debug(
            "svm_obj:'%s' compute_ip:'%s' agent_inspect:'%s'", svm_obj.__dict__,
            vm_nodeip, inspect_h.get_vna_tap_interface_by_vm(vm_id=svm_obj.id))
        tap_intf_list = []
        vn = 'svc-vn-' + direction
        vrf = ':'.join(self.inputs.project_fq_name) + ':' + vn + ':' + vn
        for entry in inspect_h.get_vna_tap_interface_by_vm(vm_id=svm_obj.id):
            if entry['vrf_name'] == vrf:
                self.logger.debug(
                    'The %s tap-interface of %s is %s' %
                    (direction, svm_name, entry['name']))
                return entry['name']

    def get_svm_tapintf_of_vn(self, svm_name, vn):
        self.is_svm_active(svm_name)
        svm_obj = self.get_svm_obj(svm_name)
        vm_nodeip = self.inputs.host_data[
            self.nova_h.get_nova_host_of_vm(svm_obj)]['host_ip']
        inspect_h = self.agent_inspect[vm_nodeip]
        self.logger.debug(
            "svm_obj:'%s' compute_ip:'%s' agent_inspect:'%s'", svm_obj.__dict__,
            vm_nodeip, inspect_h.get_vna_tap_interface_by_vm(vm_id=svm_obj.id))
        tap_intf_list = []
        for entry in inspect_h.get_vna_tap_interface_by_vm(vm_id=svm_obj.id):
            if entry['vrf_name'] == vn.vrf_name:
                self.logger.debug(
                    'The tap interface corresponding to %s on %s is %s' %
                    (vn.vn_name, svm_name, entry['name']))
                return entry['name']

    def get_svm_metadata_ip(self, svm_name):
        tap_intf = self.get_svm_tapintf(svm_name)
        tap_object = inspect_h.get_vna_intf_details(tap_intf['name'])
        return tap_object['mdata_ip_addr']

    def start_tcpdump_on_intf(self, host, tapintf):
        session = ssh(host['host_ip'], host['username'], host['password'])
        cmd = 'tcpdump -nni %s -c 1 proto 1 > /tmp/%s_out.log 2>&1' % (
            tapintf, tapintf)
        execute_cmd(session, cmd, self.logger)
    # end start_tcpdump_on_intf

    def stop_tcpdump_on_intf(self, host, tapintf):
        session = ssh(host['host_ip'], host['username'], host['password'])
        self.logger.info('Waiting for tcpdump to complete')
        time.sleep(10)
        output_cmd = 'cat /tmp/%s_out.log' % tapintf
        out, err = execute_cmd_out(session, output_cmd, self.logger)
        return out
    # end stop_tcpdump_on_intf

    def setup_ecmp_config_hash_svc(self, si_count=1, svc_scaling=False,
                                   max_inst=1, svc_mode='in-network-nat',
                                   flavor='m1.medium',
                                   static_route=[None, None, None],
                                   ordered_interfaces=True, ci=False,
                                   svc_img_name='ubuntu-in-net', st_version=1,
                                   ecmp_hash='default',config_level='global'):

        """Validate the ECMP configuration hash with service chaining in network  datapath"""

        # Default ECMP hash with 5 tuple
        if ecmp_hash == 'default':
            ecmp_hash = {"source_ip": True, "destination_ip": True,
                         "source_port": True, "destination_port": True,
                         "ip_protocol": True}

        if ecmp_hash == 'None':
            ecmp_hash_config = {}
            ecmp_hash_config['hashing_configured'] = False
        else:
            ecmp_hash_config = ecmp_hash.copy()
            ecmp_hash_config['hashing_configured'] = True

        # Bringing up base setup. i.e 2 VNs (vn1 and vn2), 2 VMs, 3 service
        # instances, policy for service instance and applying policy on 2 VNs
        if svc_mode == 'in-network-nat' or svc_mode == 'in-network':
            ret_dict = self.verify_svc_in_network_datapath(si_count=1,
                                            svc_scaling=True,
                                            max_inst=max_inst,
                                            svc_mode=svc_mode,
                                            flavor=flavor,
                                            svc_img_name=svc_img_name,
                                            st_version=st_version,
                                            **self.common_args)
        elif svc_mode == 'transparent':
            ret_dict = self.verify_svc_transparent_datapath(si_count=1,
                                                svc_scaling=True,
                                                max_inst=max_inst,
                                                flavor=flavor,
                                                svc_img_name=svc_img_name,
                                                st_version=st_version,
                                                **self.common_args)

        # ECMP Hash at VMI interface of right_vm (right side)
        right_vm_fixture = ret_dict['right_vm_fixture']
        right_vn_fixture = ret_dict['right_vn_fixture']
        svm_list = [right_vm_fixture]

        if config_level == 'global' or config_level == 'all':
            self.config_ecmp_hash_global(ecmp_hash_config)
        elif config_level == 'vn' or config_level == 'all':
            right_vn_fixture.set_ecmp_hash(ecmp_hash_config)
        elif config_level ==  'vmi' or config_level == 'all':
            self.config_ecmp_hash_vmi(svm_list, ecmp_hash_config)
        return ret_dict
    # end setup_ecmp_config_hash_svc

    def modify_ecmp_config_hash(self, ecmp_hash='default',config_level='global',right_vm_fixture=None,right_vn_fixture=None):
        """Modify the ECMP configuration hash """

        # Default ECMP hash with 5 tuple
        if ecmp_hash == 'default':
            ecmp_hash = {"source_ip": True, "destination_ip": True,
                         "source_port": True, "destination_port": True,
                         "ip_protocol": True}


        if ecmp_hash == 'None':
            ecmp_hash_config = {}
            ecmp_hash_config['hashing_configured'] = False
        else:
            # Explicitly set "False" to individual tuple, incase not set
            ecmp_hash_config = ecmp_hash.copy()
            if not 'source_ip' in ecmp_hash_config:
                ecmp_hash_config['source_ip'] = False
            if not 'destination_ip' in ecmp_hash_config:
                ecmp_hash_config['destination_ip'] = False
            if not 'source_port' in ecmp_hash_config:
                ecmp_hash_config['source_port'] = False
            if not 'destination_port' in ecmp_hash_config:
                ecmp_hash_config['destination_port'] = False
            if not 'ip_protocol' in ecmp_hash_config:
                ecmp_hash_config['ip_protocol'] = False
            ecmp_hash_config['hashing_configured'] = True

        right_vm_fixture = right_vm_fixture or self.right_vm_fixture
        right_vn_fixture = right_vn_fixture or self.right_vn_fixture
        # ECMP Hash at VMI interface of VM2 (right side)
        svm_list = [right_vm_fixture]

        if config_level == 'global' or config_level == 'all':
            self.config_ecmp_hash_global(ecmp_hash_config)
        if config_level == 'vn' or config_level == 'all':
            right_vn_fixture.set_ecmp_hash(ecmp_hash_config)
        if config_level ==  'vmi' or config_level == 'all':
            self.config_ecmp_hash_vmi(svm_list, ecmp_hash_config)
    # end modify_ecmp_config_hash


    def config_ecmp_hash_vmi(self, svm_list, ecmp_hash=None):
        """Configure ecmp hash at vmi"""
        for svm in svm_list:
            for (vn_fq_name, vmi_uuid) in svm.get_vmi_ids().iteritems():
                if re.match(r".*in_network_vn2.*|.*bridge_vn2.*|.*right_.*", vn_fq_name):
                    self.logger.info('Updating ECMP Hash:%s at vmi:%s' % (ecmp_hash, vmi_uuid))
                    vmi_config = self.vnc_lib.virtual_machine_interface_read(id = str(vmi_uuid))
                    vmi_config.set_ecmp_hashing_include_fields(ecmp_hash)
                    self.vnc_lib.virtual_machine_interface_update(vmi_config)
    # end config_ecmp_hash_vmi

    def config_ecmp_hash_global(self, ecmp_hash=None):
        """Configure ecmp hash at global"""
        self.logger.info('Updating ECMP Hash:%s at Global Config Level' % ecmp_hash)
        global_vrouter_id = self.vnc_lib.get_default_global_vrouter_config_id()
        global_config = self.vnc_lib.global_vrouter_config_read(id = global_vrouter_id)
        global_config.set_ecmp_hashing_include_fields(ecmp_hash)
        self.vnc_lib.global_vrouter_config_update(global_config)
    # end config_ecmp_hash_global


    def del_ecmp_hash_config(self, vn_fixture=None, svm_list=None):
        """Delete ecmp hash at global, vn and vmi"""
        self.logger.info('Explicitly deleting ECMP Hash:%s at Global, VN and VMI Level')
        ecmp_hash = {"hashing_configured": False}
        self.config_ecmp_hash_global(ecmp_hash)
        self.config_ecmp_hash_vmi(svm_list, ecmp_hash)
        vn_fixture.set_ecmp_hash(ecmp_hash)
    # end del_ecmp_hash_config


