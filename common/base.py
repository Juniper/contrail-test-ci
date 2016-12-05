import test_v1
from netaddr import *
from vnc_api.vnc_api import *
from vn_test import VNFixture
from vm_test import VMFixture
from policy_test import PolicyFixture
from port_fixture import PortFixture
from interface_route_table_fixture import InterfaceRouteTableFixture
from tcutils.util import get_random_name, get_random_cidr
from contrailapi import ContrailVncApi

class GenericTestBase(test_v1.BaseTestCase_v1):

    @classmethod
    def setUpClass(cls):
        super(GenericTestBase, cls).setUpClass()
        cls.quantum_h = cls.connections.quantum_h
        cls.nova_h = cls.connections.nova_h
        cls.vnc_lib = cls.connections.vnc_lib
        cls.agent_inspect = cls.connections.agent_inspect
        cls.cn_inspect = cls.connections.cn_inspect
        cls.analytics_obj = cls.connections.analytics_obj
        cls.api_s_inspect = cls.connections.api_server_inspect
        cls.vnc_h = ContrailVncApi(cls.vnc_lib, cls.logger)
        try:
            address_family = cls.address_family or 'v4'
        except AttributeError:
            cls.address_family = 'v4'
    # end setUpClass

    @classmethod
    def tearDownClass(cls):
        super(GenericTestBase, cls).tearDownClass()
    # end tearDownClass

    @classmethod
    def create_only_vn(cls, vn_name=None, vn_subnets=None, vxlan_id=None,
                   enable_dhcp=True, **kwargs):
        '''Classmethod to do only VN creation
        '''
        if not vn_name:
            vn_name = get_random_name('vn')
        vn_fixture = VNFixture(project_name=cls.inputs.project_name,
                      connections=cls.connections,
                      inputs=cls.inputs,
                      vn_name=vn_name,
                      subnets=vn_subnets,
                      vxlan_id=vxlan_id,
                      enable_dhcp=enable_dhcp,
                      **kwargs)
        vn_fixture.setUp()
        return vn_fixture
    # end create_only_vn

    def create_vn(self, vn_name=None, vn_subnets=None, vxlan_id=None,
        enable_dhcp=True, cleanup=True, **kwargs):
        vn_fixture = self.create_only_vn(vn_name=vn_name,
                                     vn_subnets=vn_subnets,
                                     vxlan_id=vxlan_id,
                                     enable_dhcp=enable_dhcp,
                                     **kwargs)
        if cleanup:
            self.addCleanup(vn_fixture.cleanUp)

        return vn_fixture
    # end create_vn

    @classmethod
    def create_only_vm(cls, vn_fixture=None, vm_name=None, node_name=None,
                  flavor='contrail_flavor_small',
                  image_name='ubuntu-traffic',
                  port_ids=[], **kwargs):
        vn_obj = None
        if vn_fixture:
            vn_obj = vn_fixture.obj
        vm_obj = VMFixture(
                    project_name=cls.inputs.project_name,
                    connections=cls.connections,
                    vn_obj=vn_obj,
                    vm_name=vm_name,
                    image_name=image_name,
                    flavor=flavor,
                    node_name=node_name,
                    port_ids=port_ids,
                    **kwargs)
        vm_obj.setUp()
        return vm_obj
    # end create_only_vm

    def create_vm(self, vn_fixture=None, vm_name=None, node_name=None,
                  flavor='contrail_flavor_small',
                  image_name='ubuntu-traffic',
                  port_ids=[], **kwargs):
        cleanup = kwargs.get('cleanup', True)
        vm_fixture = self.create_only_vm(vn_fixture=vn_fixture,
                        vm_name=vm_name,
                        node_name=node_name,
                        flavor=flavor,
                        image_name=image_name,
                        port_ids=port_ids,
                        **kwargs)
        if cleanup:
            self.addCleanup(vm_fixture.cleanUp)
        return vm_fixture

    def create_router(self, router_name=None, connections=None):
        if not connections:
            neutron_handle = self.quantum_h
        else:
            neutron_handle = connections.quantum_h
        if not router_name:
            router_name = 'router-%s' % (get_random_name())
        obj = neutron_handle.create_router(router_name)
        if obj:
            self.addCleanup(neutron_handle.delete_router, obj['id'])
        return obj

    def delete_router(self, router_id=None):
        val = self.quantum_h.delete_router(router_id)

    def create_port(self, net_id, fixed_ips=[],
                    mac_address=None, no_security_group=False,
                    security_groups=[], extra_dhcp_opts=None):
        port_rsp = self.quantum_h.create_port(
            net_id,
            fixed_ips,
            mac_address,
            no_security_group,
            security_groups,
            extra_dhcp_opts)
        self.addCleanup(self.delete_port, port_rsp['id'], quiet=True)
        return port_rsp

    def delete_port(self, port_id, quiet=False):
        self.remove_from_cleanups(self.quantum_h.delete_port, (port_id))
        if quiet and not self.quantum_h.get_port(port_id):
            return
        self.quantum_h.delete_port(port_id)

    def update_port(self, port_id, port_dict):
        if not self.quantum_h.get_port(port_id):
            self.logger.error('Port with port_id %s not found' % port_id)
            return
        else:
            port_rsp = self.quantum_h.update_port(port_id, port_dict)
        return port_rsp

    def add_router_interface(self, router_id, subnet_id=None, port_id=None,
                             cleanup=True):
        if subnet_id:
            result = self.quantum_h.add_router_interface(
                router_id, subnet_id)
        elif port_id:
            result = self.quantum_h.add_router_interface(router_id,
                                                         port_id=port_id)

        if cleanup:
            self.addCleanup(self.delete_router_interface,
                            router_id, subnet_id, port_id)
        return result

    def delete_router_interface(self, router_id, subnet_id=None, port_id=None):
        self.remove_from_cleanups(self.delete_router_interface,
                                  (router_id, subnet_id, port_id))
        self.quantum_h.delete_router_interface(
            router_id, subnet_id, port_id)

    def add_vn_to_router(self, router_id, vn_fixture, cleanup=True):
        return self.add_router_interface(
            router_id,
            subnet_id=vn_fixture.vn_subnet_objs[0]['id'], cleanup=cleanup)

    def delete_vn_from_router(self, router_id, vn_fixture):
        return self.delete_router_interface(
            router_id,
            vn_fixture.vn_subnet_objs[0]['id'])

    def create_security_group(self, name, quantum_handle=None):
        q_h = None
        if quantum_handle:
            q_h = quantum_handle
        else:
            q_h = self.quantum_h
        obj = q_h.create_security_group(name)
        if obj:
            self.addCleanup(self.delete_security_group, obj['id'])
        return obj
    # end create_security_group

    def delete_security_group(self, sg_id, quantum_handle=None):
        q_h = None
        if quantum_handle:
            q_h = quantum_handle
        else:
            q_h = self.quantum_h
        q_h.delete_security_group(sg_id)

    def create_fip(self, fip_fixture):
        self.logger.info('Creating FIP from %s'%fip_fixture.pool_name)
        return self.vnc_h.create_floating_ip(fip_fixture.fip_pool_obj, fip_fixture.project_obj)
    
    def assoc_fip(self, fip_id, vm_id):
        return self.vnc_h.assoc_floating_ip(fip_id, vm_id)

    def disassoc_fip(self, fip_id):
        self.vnc_h.disassoc_floating_ip(fip_id)
    
    def del_fip(self, fip_id):
        self.vnc_h.delete_floating_ip(fip_id)

    def config_aap(self, port, prefix, prefix_len=32, mac='', aap_mode='active-standby', contrail_api=False):
        self.logger.info('Configuring AAP on port %s' %port['id'])
        if is_v6(prefix):
            prefix_len = 128
        if contrail_api:
            self.vnc_h.add_allowed_pair(port['id'], prefix, prefix_len, mac, aap_mode)
        else:
            port_dict = {'allowed_address_pairs': [
                {"ip_address": prefix + '/' + str(prefix_len) , "mac_address": mac}]}
            port_rsp = self.update_port(port['id'], port_dict)
        return True
    # end config_aap

    def config_vrrp_on_vsrx(self, vm_fix, vip, priority):
        cmdList = []
        cmdList.append('deactivate security nat source rule-set TestNat')
        cmdList.append(
            'deactivate interfaces ge-0/0/1 unit 0 family inet filter')
        cmdList.append('deactivate interfaces ge-0/0/1.0 family inet dhcp')
        cmdList.append('deactivate security policies')
        cmdList.append(
            'set security forwarding-options family inet6 mode packet-based')
        cmdList.append(
            'set security forwarding-options family mpls mode packet-based')
        cmdList.append(
            'set security forwarding-options family iso mode packet-based')
        vsrx_vrrp_config = ['set interfaces ge-0/0/1.0 family inet address ' + vm_fix.vm_ips[
            1] + '/' + '24 vrrp-group 1 priority ' + priority + ' virtual-address ' + vip + ' accept-data']
        cmdList = cmdList + vsrx_vrrp_config
        cmd_string = (';').join(cmdList)
        result = vm_fix.set_config_via_netconf(
            cmd_string, timeout=10, device='junos', hostkey_verify="False")
        return result
    # end config_vrrp_on_vsrx

    @retry(delay=5, tries=10)
    def config_vrrp(self, vm_fix, vip, priority):
        self.logger.info('Configuring VRRP on %s ' % vm_fix.vm_name)
        vrrp_cmd = 'nohup vrrpd -n -D -i eth0 -v 1 -a none -p %s -d 3 %s' % (
            priority, vip)
        vm_fix.run_cmd_on_vm(cmds=[vrrp_cmd], as_sudo=True)
        result = self.vrrp_chk(vm_fix)
        return result
    # end config_vrrp

    def vrrp_chk(self, vm):
        vrrp_chk_cmd = 'netstat -anp | grep vrrpd'
        vm.run_cmd_on_vm(cmds=[vrrp_chk_cmd], as_sudo=True)
        vrrp_op = vm.return_output_cmd_dict[vrrp_chk_cmd]
        if '/vrrpd' in vrrp_op:
            result = True
            self.logger.info('vrrpd running in %s' % vm.vm_name)
        else:
            result = False
            self.logger.error('vrrpd not running in %s' % vm.vm_name)
        return result
    # end vrrp_chk

    @retry(delay=5, tries=10)
    def vrrp_mas_chk(self, vm, vn, ip, vsrx=False):
        self.logger.info(
            'Will verify who the VRRP master is and the corresponding route entries in the Agent')
        if is_v4(ip):
            prefix_len = '32'
            vrrp_mas_chk_cmd = 'ip -4 addr ls'
        elif is_v6(ip):
            prefix_len = '128'
            vrrp_mas_chk_cmd = 'ip -6 addr ls'

        if vsrx:
            vrrp_mas_chk_cmd = 'show vrrp'
            result = vm.get_config_via_netconf(
                cmd=vrrp_mas_chk_cmd, timeout=10, device='junos', hostkey_verify="False", format='text')
            if 'master' in result:
                self.logger.info(
                    '%s is selected as the VRRP Master' % vm.vm_name)
                result = True
            else:
                result = False
                self.logger.error('VRRP Master not selected')
        else:
            vm.run_cmd_on_vm(cmds=[vrrp_mas_chk_cmd], as_sudo=True)
            output = vm.return_output_cmd_dict[vrrp_mas_chk_cmd]
            result = False
            if ip in output:
                self.logger.info(
                    '%s is selected as the VRRP Master' % vm.vm_name)
                result = True
            else:
                result = False
                self.logger.error('VRRP Master not selected')
        result = result and self.check_master_in_agent(vm, vn, ip, prefix_len)
        return result
    # end vrrp_mas_chk

    @retry(delay=3, tries=5)
    def check_master_in_agent(self, vm, vn, ip, prefix_len='32', ecmp=False):
        inspect_h = self.agent_inspect[vm.vm_node_ip]
        (domain, project, vnw) = vn.vn_fq_name.split(':')
        agent_vrf_objs = inspect_h.get_vna_vrf_objs(domain, project, vnw)
        agent_vrf_obj = vm.get_matching_vrf(
            agent_vrf_objs['vrf_list'], vn.vrf_name)
        vn1_vrf_id = agent_vrf_obj['ucindex']
        result = False
        paths = []
        try:
            paths = inspect_h.get_vna_active_route(
                vrf_id=vn1_vrf_id, ip=ip, prefix=prefix_len)['path_list']
        except TypeError:
            self.logger.info('Unable to retreive path info')
        for path in paths:
            if path['peer'] == 'LocalVmPort' and path['path_preference_data']['wait_for_traffic'] == 'false':
                result = True
                if ecmp:
                    if path['path_preference_data']['ecmp'] == 'true':
                        result = True
                        break
                    else:
                        result = False
                        return result
                else:
                    break
            else:
                result = False
        return result
    # end check_master_in_agent

    @retry(delay=5, tries=10)
    def verify_vrrp_action(self, src_vm, dst_vm, ip, vsrx=False):
        result = False
        self.logger.info('Will ping %s from %s and check if %s responds' % (
            ip, src_vm.vm_name, dst_vm.vm_name))
        compute_ip = dst_vm.vm_node_ip
        compute_user = self.inputs.host_data[compute_ip]['username']
        compute_password = self.inputs.host_data[compute_ip]['password']
        session = ssh(compute_ip, compute_user, compute_password)
        if vsrx:
            vm_tapintf = dst_vm.tap_intf[dst_vm.vn_fq_names[1]]['name']
        else:
            vm_tapintf = dst_vm.tap_intf[dst_vm.vn_fq_name]['name']
        cmd = 'tcpdump -nni %s -c 10 > /tmp/%s_out.log' % (
            vm_tapintf, vm_tapintf)
        execute_cmd(session, cmd, self.logger)
        assert src_vm.ping_with_certainty(ip), 'Ping to vIP failure'
        output_cmd = 'cat /tmp/%s_out.log' % vm_tapintf
        output, err = execute_cmd_out(session, output_cmd, self.logger)
        if ip in output:
            result = True
            self.logger.info(
                '%s is seen responding to ICMP Requests' % dst_vm.vm_name)
        else:
            self.logger.error('ICMP Requests not seen on the VRRP Master')
            result = False
        return result
    # end verify_vrrp_sction

    def _remove_from_cleanup(self, func_call, *args):
        for cleanup in self._cleanups:
            if func_call in cleanup and args == cleanup[1]:
                self._cleanups.remove(cleanup)
                return True
        return False

    def remove_method_from_cleanups(self, method):
        for cleanup in self._cleanups:
            if method == cleanup:
                self._cleanups.remove(cleanup)
                break
   # end remove_method_from_cleanups

    def allow_all_traffic_between_vns(self, vn1_fixture, vn2_fixture):
        policy_name = get_random_name('policy-allow-all')
        rules = [
            {
                'direction': '<>', 'simple_action': 'pass',
                'protocol': 'any',
                'source_network': vn1_fixture.vn_name,
                'dest_network': vn2_fixture.vn_name,
            },
        ]
        policy_fixture = self.useFixture(
            PolicyFixture(
                policy_name=policy_name, rules_list=rules, inputs=self.inputs,
                connections=self.connections))

        vn1_fixture.bind_policies(
            [policy_fixture.policy_fq_name], vn1_fixture.vn_id)
        self.addCleanup(vn1_fixture.unbind_policies,
                        vn1_fixture.vn_id, [policy_fixture.policy_fq_name])

        vn2_fixture.bind_policies(
            [policy_fixture.policy_fq_name], vn2_fixture.vn_id)
        self.addCleanup(vn2_fixture.unbind_policies,
                        vn2_fixture.vn_id, [policy_fixture.policy_fq_name])
    # end allow_all_traffic_between_vns

    def create_dhcp_server_vm(self,
                              vn1_fixture,
                              vn2_fixture,
                              vm_name=None,
                              node_name=None,
                              flavor='contrail_flavor_large',
                              image_name='ubuntu-dns-server',
                              port_ids=[]):
        if not vm_name:
            vm_name = get_random_name('dhcp-server')
        vm_fixture = self.useFixture(
            VMFixture(
                project_name=self.inputs.project_name,
                connections=self.connections,
                vn_objs=[vn1_fixture.obj, vn2_fixture.obj],
                vm_name=vm_name,
                image_name=image_name,
                flavor=flavor,
                node_name=node_name,
                port_ids=port_ids))
        assert vm_fixture.verify_on_setup(), (
            "DHCP Server VM Verification failed ")
        assert vm_fixture.wait_till_vm_is_up()
        vn2_fq_name = vn2_fixture.vn_fq_name
        vm_ip = vm_fixture.vm_ip_dict[vn2_fq_name][0]
        cmds = ['ifconfig eth1 up',
                'ifconfig eth1 %s netmask 255.255.255.0' % (vm_ip),
                'service isc-dhcp-server restart']
        vm_fixture.run_cmd_on_vm(cmds, as_sudo=True)
        self.sleep(5)
        return vm_fixture

    # end create_dhcp_server_vm

    @classmethod
    def setup_only_vmi(cls, vn_id, fixed_ips=[],
                  mac_address=None,
                  security_groups=[],
                  extra_dhcp_opts=[],
                  **kwargs):
        if mac_address:
            mac_address = EUI(mac_address)
            mac_address.dialect = mac_unix
        port_fixture = PortFixture(
            vn_id,
            mac_address=mac_address,
            fixed_ips=fixed_ips,
            security_groups=security_groups,
            extra_dhcp_opts=extra_dhcp_opts,
            connections=cls.connections,
            **kwargs
        )
        port_fixture.setUp()
        return port_fixture
    # end setup_only_vmi

    def setup_vmi(self, vn_id, fixed_ips=[],
                  mac_address=None,
                  security_groups=[],
                  extra_dhcp_opts=[],
                  **kwargs):
        cleanup = kwargs.get('cleanup', True)
        port_fixture = self.setup_only_vmi(vn_id,fixed_ips=fixed_ips,
                                           mac_address=mac_address,
                                           security_groups=security_groups,
                                           extra_dhcp_opts=extra_dhcp_opts,
                                           **kwargs)
        if cleanup:
            self.addCleanup(port_fixture.cleanUp)
        return port_fixture
    # end setup_vmi

    def setup_interface_route_table(
            self,
            obj=None,
            name=None,
            cleanup=True,
            **kwargs):
        '''
        Create interface route table and optionally add it to obj
        obj : Example : PortFixture instance
        '''
        name = name or get_random_name('irtb')
        intf_route_table = InterfaceRouteTableFixture(
            name=name,
            cleanup=cleanup,
            connections=self.connections,
            **kwargs)
        intf_route_table.setUp()
        if cleanup:
            self.sleep(1)
            self.addCleanup(intf_route_table.cleanUp)
        if obj:
            self.add_interface_route_table(obj,intf_route_table.obj, cleanup)
        return intf_route_table
    # end setup_interface_route_table

    def add_interface_route_table(self, obj, intf_route_table_obj,
        cleanup=True):
        ''' Calls add_interface_route_table on obj object
            intf_route_table_obj is InterfaceRouteTable instance
        '''
        obj.add_interface_route_table(intf_route_table_obj)
        if cleanup:
            self.addCleanup(obj.del_interface_route_table,
                            intf_route_table_obj.uuid)
    # end add_inteface_route_table

    def del_interface_route_table(self, obj, uuid):
        self.remove_from_cleanups(obj.del_interface_route_table, (uuid))
        obj.del_interface_route_table(uuid)
    # end del_interface_route_table

    def do_ping_test(self, fixture_obj, sip, dip, expectation=True):
        assert fixture_obj.ping_with_certainty(dip, expectation=expectation),\
            'Ping from %s to %s with expectation %s failed!' % (
                sip, dip, str(expectation))
        self.logger.info('Ping test from %s to %s with expectation %s passed' % (sip,
                          dip, str(expectation)))
    # end do_ping_test

    @classmethod
    def check_vms_booted(cls, vms_list):
        for vm_fixture in vms_list:
            assert vm_fixture.wait_till_vm_is_up(), 'VM %s has not booted' % (
                vm_fixture.vm_name)
    # end check_vms_booted

    @classmethod
    def set_af(cls, family='v4'):
        cls.address_family = family

    @classmethod
    def get_af(cls):
        return cls.address_family

    @classmethod
    def safe_cleanup(cls, obj_name):
        '''
        Check if the fixture object exists and 'created' attribute
        is set in it. If so, call the cleanUp() of the fixture object
        '''
        obj = getattr(cls, obj_name, None)
        if obj and getattr(obj, 'created', False):
            return obj.cleanUp()
    # end cleanup
