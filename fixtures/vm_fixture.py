#TODO integrate with vm_test.py
from contrail_fixtures import ContrailFixture
from tcutils.util import *
from vnc_api.vnc_api import VirtualMachine
from collections import defaultdict
import copy
from tcutils.util import safe_run
from tcutils.test_lib.contrail_utils import get_interested_computes

class VMFixture_v2 (ContrailFixture):

    vnc_class = VirtualMachine 

    def __init__ (self, connections, uuid=None, params=None, fixs=None):
        super(VMFixture_v2, self).__init__(
           uuid=uuid,
           connections=connections,
           params=params,
           fixs=fixs)
        self.api_s_inspects = connections.api_server_inspects
        self.api_s_inspect = connections.api_server_inspect
        self.agent_inspect = connections.agent_inspect
        self.cn_inspect = connections.cn_inspect
        self.analytics_obj = connections.analytics_obj
        self.vnc_lib_h = connections.get_vnc_lib_h()
        self.vnc_lib_fixture = connections.vnc_lib_fixture
        self.vm_ips = list()
        self.cs_vmi_obj = {}
        self.tap_intf = {}
        self.mac_addr = {}
        self.agent_vrf_name = {}
        self.agent_vrf_id = {}
        self.agent_path = {}
        self.agent_label = {}
        self.local_ips = {}
        self.agent_l2_path = {}
        self.agent_l2_label = {}
        self.agent_vxlan_id = {}

    def get_attr (self, lst):
        if lst == ['fq_name']:
            return self.fq_name
        return None

    def get_resource (self):
        return self.uuid

    def __str__ (self):
        #TODO: __str__
        if self._args:
            info = ''
        else:
            info = ''
        return '%s:%s' % (self.type_name, info)

    def _add_to_objs (self, objs, res_name, obj, args=None):
       objs['fixtures'][res_name] = obj
       objs['id-map'][obj.uuid] = obj
       objs['name-map'][obj.name] = obj
       if args:
           objs['args'][res_name] = args
       if obj.fq_name_str:
           objs['fqn-map'][obj.fq_name_str] = obj

    def _minimal_read (self):
        if self.uuid:
            ret, self.vm_details = self._read_orch_obj()
            if ret:
                self._name = self.vm_details.name
                #Nova does not have VM's fqname info, so getting it from VN fixture
                self._fq_name = copy.deepcopy(self.fixs['name-map'][self.vm_details.vn_names[0]].fq_name)
                self._fq_name[-1] = self._name
                self._fq_name_str = ':'.join(self._fq_name)
            else:
                self._name = None
                self._fq_name = None
                self._fq_name_str = None

    @retry(delay=1, tries=5)
    def _read_vnc_obj (self):
        obj = self._vnc.get_virtual_machine(self.uuid)
        found = 'not' if not obj else ''
        self.logger.debug('%s %s found in api-server' % (self, found))
        return obj != None, obj

    @retry(delay=1, tries=5)
    def _read_orch_obj (self):
        obj = self._ctrl.get_virtual_machine(self.uuid)
        found = 'not' if not obj else ''
        self.logger.debug('%s %s found in orchestrator' % (self, found))
        return obj != None, obj

    def _read (self):
        ret, obj = self._read_vnc_obj()
        if ret:
            self._vnc_obj = obj
        ret, self.vm_details = self._read_orch_obj()
        if ret:
            self._obj = self.vm_details.obj
            self._objs = [self._obj]
            self._name = self.vm_details.name
            self.vn_names = self.vm_details.vn_names
            self.vn_objs = [self.fixs['name-map'][x]._obj
                            for x in self.vn_names]
            self.vn_ids = [self.fixs['name-map'][x].uuid
                            for x in self.vn_names]
            self.vn_fq_names = [self.fixs['name-map'][x].fq_name_str
                                for x in self.vn_names]
            self.vn_name = self.vn_names[0]
            self.vn_fq_name = self.vn_fq_names[0]
        self.vm_ip_dict = self.get_vm_ip_dict()
        self.vm_ips = self.get_vm_ips()

    def _create (self):
        self.logger.info('Creating %s' % self)
        self.uuid = self._ctrl.create_virtual_machine(
            **self._args)

    def _delete (self):
        self.logger.info('Deleting %s' % self.name)
        self._ctrl.delete_virtual_machine(
            obj=self._obj, uuid=self.uuid)

    def _update (self):
        self.logger.info('Updating %s' % self.name)
        self._ctrl.update_virtual_machine(
            obj=self._obj, uuid=self.uuid, **self.args)

    def verify_on_setup (self, force=False):
        #<TBD> skip verification on vcenter gateway setup

        if not (self.inputs.verify_on_setup or force):
            self.logger.debug('Skipping VM %s verification' % (self.name))
            return True

        self._read()

        vm_status = self.vm_details.wait_till_vm_is_active(self._obj)
        if type(vm_status) is tuple:
            if vm_status[1] in 'ERROR':
                self.logger.warn("VM in error state.")
                return False
            if vm_status[1] != 'ACTIVE':
                return False
        elif not vm_status:
            return False

        self.assert_on_setup(*self._verify_in_api_server())
        self.assert_on_setup(*self._verify_in_orch())
        self.assert_on_setup(*self._verify_in_agent())
        #TODO: check if more verification is needed

    def verify_on_cleanup (self):
        self.assert_on_cleanup(*self._verify_not_in_api_server())
        self.assert_on_cleanup(*self._verify_not_in_orch())
        self.assert_on_cleanup(*self._verify_not_in_agent())
        #TODO: check if more verification is needed

    @retry(delay=1, tries=5)
    def get_vm_obj_from_api_server(self, cfgm_ip=None, refresh=False):
        cfgm_ip = cfgm_ip or self.inputs.cfgm_ip
        if not getattr(self, 'cs_vm_obj', None):
            self.cs_vm_obj = dict()
        if not self.cs_vm_obj.get(cfgm_ip) or refresh:
            vm_obj = self.api_s_inspects[
                cfgm_ip].get_cs_vm(self.uuid, refresh)
            self.cs_vm_obj[cfgm_ip] = vm_obj
        ret = True if self.cs_vm_obj[cfgm_ip] else False
        return (ret, self.cs_vm_obj[cfgm_ip])

    def get_vm_objs(self):
        for cfgm_ip in self.inputs.cfgm_ips:
            vm_obj = self.get_vm_obj_from_api_server(cfgm_ip)[1]
            if not vm_obj:
                return None
        return self.cs_vm_obj

    @retry(delay=1, tries=5)
    def get_vmi_obj_from_api_server(self, cfgm_ip=None, refresh=False):
        cfgm_ip = cfgm_ip or self.inputs.cfgm_ip
        if not getattr(self, 'cs_vmi_objs', None):
            self.cs_vmi_objs = dict()
        if not self.cs_vmi_objs.get(cfgm_ip) or refresh:
            vmi_obj = self.api_s_inspects[cfgm_ip].get_cs_vmi_of_vm(
                self.uuid, refresh=True)
            self.cs_vmi_objs[cfgm_ip] = vmi_obj
        ret = True if self.cs_vmi_objs[cfgm_ip] else False
        return (ret, self.cs_vmi_objs[cfgm_ip])

    def get_vmi_objs(self, refresh=False):
        for cfgm_ip in self.inputs.cfgm_ips:
            vmi_obj = self.get_vmi_obj_from_api_server(cfgm_ip, refresh)[1]
            if not vmi_obj:
                return None
        return self.cs_vmi_objs

    @retry(delay=1, tries=5)
    def get_iip_obj_from_api_server(self, cfgm_ip=None, refresh=False):
        cfgm_ip = cfgm_ip or self.inputs.cfgm_ip
        if not getattr(self, 'cs_instance_ip_objs', None):
            self.cs_instance_ip_objs = dict()
        if not self.cs_instance_ip_objs.get(cfgm_ip) or refresh:
            iip_objs = self.api_s_inspects[cfgm_ip].get_cs_instance_ips_of_vm(
                self.uuid, refresh)
            self.cs_instance_ip_objs[cfgm_ip] = iip_objs
        ret = True if self.cs_instance_ip_objs[cfgm_ip] else False
        return (ret, self.cs_instance_ip_objs[cfgm_ip])

    def get_iip_objs(self, refresh=False):
        for cfgm_ip in self.inputs.cfgm_ips:
            iip_obj = self.get_iip_obj_from_api_server(cfgm_ip, refresh)[1]
            if not iip_obj:
                return None
        return self.cs_instance_ip_objs

    def get_vm_ip_dict(self):
        if not getattr(self, 'vm_ip_dict', None):
            self.vm_ip_dict = defaultdict(list)
            iip_objs = self.get_iip_obj_from_api_server(refresh=True)[1]
            for iip_obj in iip_objs:
                ip = iip_obj.ip
                if self.hack_for_v6(ip):
                    continue
                self.vm_ip_dict[iip_obj.vn_fq_name].append(ip)
        return self.vm_ip_dict

    def get_uuid(self):
        return self.uuid

    def get_fq_name(self):
        return self.fq_name

    def get_name(self):
        return self.name

    def get_vm_ips(self, vn_fq_name=None, af=None):
        if not af:
            af = self.inputs.get_af()
        af = ['v4', 'v6'] if 'dual' in af else af
        if vn_fq_name:
            vm_ips = self.get_vm_ip_dict()[vn_fq_name]
        else:
            if not getattr(self, 'vm_ips', None):
                for obj in self._objs:
                    for vn_name in self.vn_names:
                        for ip in self.vm_details.get_vm_ip(obj, vn_name):
                            if self.hack_for_v6(ip):
                                continue
                            self.vm_ips.append(ip)
            vm_ips = self.vm_ips
        return [ip for ip in vm_ips if get_af_type(ip) in af]

    def hack_for_v6(self, ip):
        if 'v6' in self.inputs.get_af() and not is_v6(ip):
            return True
        return False

    @property
    def vm_ip(self):
        return self.vm_ips[0] if self.vm_ips else None

    @property
    def vm_node_ip(self):
        if not getattr(self, '_vm_node_ip', None):
            self._vm_node_ip = self.inputs.get_host_ip(self.get_host_of_vm())
        return self._vm_node_ip

    def get_host_of_vm(self, vm_obj=None):
        vm_obj = vm_obj or self._obj
        attr = '_host_' + vm_obj.name
        if not getattr(self, attr, None):
            setattr(self, attr, self.vm_details.get_host_of_vm(vm_obj))
        return getattr(self, attr, None)

    @property
    def vm_node_data_ip(self):
        if not getattr(self, '_vm_data_node_ip', None):
            self._vm_node_data_ip = self.inputs.get_host_data_ip(
                self.get_host_of_vm())
        return self._vm_node_data_ip

    def get_compute_host(self):
        return self.vm_node_data_ip

    def get_tap_intf_of_vmi(self, vmi_uuid):
        inspect_h = self.agent_inspect[self.vm_node_ip]
        vna_tap_id = inspect_h.get_vna_tap_interface_by_vmi(vmi_id=vmi_uuid)
        return vna_tap_id[0]

    def get_tap_intf_of_vm(self):
        inspect_h = self.agent_inspect[self.vm_node_ip]
        tap_intfs = inspect_h.get_vna_tap_interface_by_vm(vm_id=self.uuid)
        return tap_intfs

    def get_vmi_id(self, vn_fq_name):
        vmi_ids = self.get_vmi_ids()
        if vmi_ids and vn_fq_name in vmi_ids:
            return vmi_ids[vn_fq_name]

    def get_vmi_ids(self, refresh=False):
        if not getattr(self, 'vmi_ids', None) or refresh:
            self.vmi_ids = dict()
            vmi_objs = self.get_vmi_obj_from_api_server(refresh=refresh)[1]
            for vmi_obj in vmi_objs:
                self.vmi_ids[vmi_obj.vn_fq_name] = vmi_obj.uuid
        return self.vmi_ids

    def get_mac_addr_from_config(self):
        if not getattr(self, 'mac_addr', None):
            vmi_objs = self.get_vmi_obj_from_api_server()[1]
            for vmi_obj in vmi_objs:
                self.mac_addr[vmi_obj.vn_fq_name] = vmi_obj.mac_addr
        return self.mac_addr

    def get_matching_vrf(self, vrf_objs, vrf_name):
        return [x for x in vrf_objs if x['name'] == vrf_name][0]

    def get_agent_label(self):
        if not getattr(self, 'agent_label', None):
            for (vn_fq_name, vmi) in self.get_vmi_ids().iteritems():
                self.agent_label[
                    vn_fq_name] = self.get_tap_intf_of_vmi(vmi)['label']
        return self.agent_label

    def get_local_ips(self, refresh=False):
        if refresh or not getattr(self, 'local_ips', None):
            for (vn_fq_name, vmi) in self.get_vmi_ids().iteritems():
                self.local_ips[vn_fq_name] = self.get_tap_intf_of_vmi(
                    vmi)['mdata_ip_addr']
        return self.local_ips

    def get_local_ip(self, refresh=False):
        if refresh or not getattr(self, '_local_ip', None):
            local_ips = self.get_local_ips(refresh=refresh)
            for vn_fq_name in self.vn_fq_names:
                if self.vnc_lib_fixture.get_active_forwarding_mode(vn_fq_name) == 'l2':
                    self.logger.debug(
                        "skipping ping to one of the 169.254.x.x IPs")
                if vn_fq_name in local_ips and local_ips[vn_fq_name] != '0.0.0.0':
                    if self.ping_vm_from_host(vn_fq_name):
                        self._local_ip = self.local_ips[vn_fq_name]
                        break
        return getattr(self, '_local_ip', '')

    def clear_local_ips(self):
        self._local_ip = None
        self.local_ips = {}

    @property
    def local_ip(self):
        return self.get_local_ip()

    @property
    def vrf_ids(self):
        return self.get_vrf_ids()

    def get_vrf_ids(self, refresh=False):
        if getattr(self, '_vrf_ids', None) and not refresh:
            return self._vrf_ids

        self._vrf_ids = dict()
        try:
            for ip in self.inputs.compute_ips:
                inspect_h = self.agent_inspect[ip]
                dct = dict()
                for vn_fq_name in self.vn_fq_names:
                    vrf_id = inspect_h.get_vna_vrf_id(vn_fq_name)
                    if vrf_id:
                        dct.update({vn_fq_name: vrf_id})
                if dct:
                    self._vrf_ids[ip] = dct
        except Exception as e:
            self.logger.exception('Exception while getting VRF id')
        finally:
            return self._vrf_ids
    # end get_vrf_ids

    def ping_vm_from_host(self, vn_fq_name, timeout=2):
        ''' Ping the VM metadata IP from the host
        '''
        host = self.inputs.host_data[self.vm_node_ip]
        output = ''
        with hide('everything'):
            with settings(
                host_string='%s@%s' % (host['username'], self.vm_node_ip),
                password=host['password'],
                    warn_only=True, abort_on_prompts=False):
                #		output = run('ping %s -c 1' % (self.local_ips[vn_fq_name]))
                #                expected_result = ' 0% packet loss'
                output = safe_run('ping %s -c 2 -W %s' %
                                  (self.local_ips[vn_fq_name], timeout))
                failure = ' 100% packet loss'
                self.logger.debug(output)
            #   if expected_result not in output:
                if failure in output[1]:
                    self.logger.debug(
                    "Ping to Metadata IP %s of VM %s failed!" %
                    (self.local_ips[vn_fq_name], self.name))
                    vn_obj = self.vnc_lib_h.virtual_network_read(fq_name = vn_fq_name.split(":"))
                    #The below code is just to make sure that 
                    #vn is assigned a gateway.In some cases(specifically vcenter case),
                    #it was observed that the gateway was not assigned to the vn 
                    for ipam_ref in vn_obj.network_ipam_refs:
                        for ipam_subnet in ipam_ref['attr'].get_ipam_subnets():
                            gateway = ipam_subnet.get_default_gateway()
                            allocation_pool = ipam_subnet.get_allocation_pools()
                            if not gateway:
                                gateway = 'NOT set'
                            if not allocation_pool:
                                allocation_pool = 'NOT set'
                            self.logger.info("Gateway for vn %s is %s and allocation pool is %s"\
                                             %(vn_fq_name,gateway,allocation_pool))
                    return False
                else:
                    self.logger.info(
                    'Ping to Metadata IP %s of VM %s passed' %
                    (self.local_ips[vn_fq_name], self.name))
        return True
    # end ping_vm_from_host

    def _do_l2_verification(self, vn_fq_name, inspect_h):
        self.logger.debug('Starting Layer 2 verification in Agent')
        # L2 verification
        try:
            self.agent_l2_path[vn_fq_name] = inspect_h.get_vna_layer2_route(
                vrf_id=self.agent_vrf_id[vn_fq_name],
                mac=self.mac_addr[vn_fq_name])
        except Exception as e:
            self.agent_l2_path[vn_fq_name] = None
        if not self.agent_l2_path[vn_fq_name]:
            self.logger.warning('No Layer 2 path is seen for VM MAC '
                                '%s in agent %s' % (self.mac_addr[vn_fq_name],
                                                    self.vm_node_ip))
            self.vm_in_agent_flag = self.vm_in_agent_flag and False
            return False
        else:
            self.logger.debug('Layer 2 path is seen for VM MAC %s '
                              'in agent %s' % (self.mac_addr[vn_fq_name],
                                               self.vm_node_ip))
        if not self.agent_l2_path[vn_fq_name]['routes'][0]['path_list'][0]['nh'].get('itf', None):
            return True

        self.agent_l2_label[vn_fq_name] = self.agent_l2_path[
            vn_fq_name]['routes'][0]['path_list'][0]['label']
        self.agent_vxlan_id[vn_fq_name] = self.agent_l2_path[
            vn_fq_name]['routes'][0]['path_list'][0]['vxlan_id']

        # Check if Tap interface of VM is present in the Agent layer
        # route table
        if self.agent_l2_path[vn_fq_name]['routes'][0]['path_list'][0][
                'nh']['itf'] != self.tap_intf[vn_fq_name]['name']:
            self.logger.warn("Active layer 2 route in agent for %s "
                             "is not pointing to right tap interface."
                             " It is %s "
                             % (self.vm_ip_dict[vn_fq_name],
                                self.agent_l2_path[vn_fq_name][
                                 'routes'][0]['path_list'][0]['nh']['itf']))
            self.vm_in_agent_flag = self.vm_in_agent_flag and False
            return False
        else:
            self.logger.debug(
                'Active layer 2 route in agent is present for VMI %s ' %
                (self.tap_intf[vn_fq_name]['name']))
        if self.agent_l2_path[vn_fq_name]['routes'][0]['path_list'][0]['active_tunnel_type'] == 'VXLAN':
            if self.agent_vxlan_id[vn_fq_name] != \
                    self.tap_intf[vn_fq_name]['vxlan_id']:
                self.logger.warn("vxlan_id  mismatch between interface "
                                 "introspect %s and l2 route table %s"
                                 % (self.tap_intf[vn_fq_name]['vxlan_id'],
                                    self.agent_vxlan_id[vn_fq_name]))
                self.vm_in_agent_flag = self.vm_in_agent_flag and False
                return False

            else:
                self.logger.debug('vxlan_id (%s) matches bw route table'
                                  ' and interface table'
                                  % self.agent_vxlan_id[vn_fq_name])

        else:

            if self.agent_l2_label[vn_fq_name] !=\
                    self.tap_intf[vn_fq_name]['l2_label']:
                self.logger.warn("L2 label mismatch between interface "
                                 "introspect %s and l2 route table %s"
                                 % (self.tap_intf[vn_fq_name]['l2_label'],
                                    self.agent_l2_label[vn_fq_name]))
                self.vm_in_agent_flag = self.vm_in_agent_flag and False
                return False
            else:
                self.logger.debug('L2 label(%s) matches bw route table'

                                  ' and interface table'
                                  % self.agent_l2_label[vn_fq_name])

        # api_s_vn_obj = self.api_s_inspect.get_cs_vn(
        # project=vn_fq_name.split(':')[1], vn=vn_fq_name.split(':')[2], refresh=True)
        # if api_s_vn_obj['virtual-network']['network_ipam_refs'][0]['attr']['ipam_subnets'][0]['enable_dhcp']:
        #   if (self.agent_l2_path[vn_fq_name]['routes'][0]['path_list'][0]['flood_dhcp']) != 'false':
        #          with self.printlock:
        #            self.logger.warn("flood_dhcp flag is set to True \
        #                             for mac %s "
        #                             %(self.agent_l2_path[vn_fq_name]['mac']) )
        #          self.vm_in_agent_flag = self.vm_in_agent_flag and False
        #          return False
        # else:
        #   if (self.agent_l2_path[vn_fq_name]['routes'][0]['path_list'][0]['flood_dhcp']) != 'true':
        #          with self.printlock:
        #            self.logger.warn("flood_dhcp flag is set to False \
        #                             for mac %s "
        #                             %(self.agent_l2_path[vn_fq_name]['mac']) )
        #          self.vm_in_agent_flag = self.vm_in_agent_flag and False
        #          return False
        return True
        # L2 verification end here

    @retry(delay=2, tries=15)
    def _verify_in_api_server (self):

        #Read the VM from orch to verify it in api server
        self._read()
        #Get the objs from api server
        self.get_vm_objs()
        self.get_vmi_objs(refresh=True)
        self.get_iip_objs(refresh=True)

        for cfgm_ip in self.inputs.cfgm_ips:
            self.logger.debug("Verifying in api server %s" % (cfgm_ip))
            if not self.cs_instance_ip_objs[cfgm_ip]:
                msg = 'Instance IP of VM ID %s not seen in API Server ' % (
                        self.uuid)
                return False, msg

        for ips in self.get_vm_ip_dict().values():
            if len((set(ips).intersection(set(self.vm_ips)))) < 1:
                msg = 'Instance IP %s from API Server is not found in '\
                        'VM IP list %s' % (ips, str(self.vm_ips))
                return False, msg
        for vmi_obj in self.cs_vmi_objs[self.inputs.cfgm_ip]:
            vmi_vn_id = vmi_obj.vn_uuid
            vmi_vn_fq_name = vmi_obj.vn_fq_name
            # ToDo: msenthil the checks have to be other way around
            if vmi_vn_id not in self.vn_ids:
                msg = 'VMI %s of VM %s is not mapped to the '\
                    'right VN ID in API Server' % (vmi_vn_id, self.name)
                return False, msg
            self.cs_vmi_obj[vmi_vn_fq_name] = vmi_obj
        self.logger.info('VM %s verfication in all API Servers passed' % (
            self.name))
        return True, None
    #end _verify_in_api_server

    @retry(delay=5, tries=6)
    def _verify_not_in_api_server (self):
        if self._vnc.get_virtual_machine(self.uuid):
            msg = '%s not removed from api-server' % self.name
            self.logger.debug(msg)
            return False, msg

        for ip in self.inputs.cfgm_ips:
            self.logger.debug("Verifying in api server %s" % (ip))
            api_inspect = self.api_s_inspects[ip]
            if api_inspect.get_cs_vm(self.uuid, refresh=True) is not None:
                msg = "VM ID %s of VM %s is still found in API Server"\
                    % (self.uuid, self.name)
                return False, msg
            if api_inspect.get_cs_vr_of_vm(self.uuid, refresh=True) is not None:
                msg = 'API-Server still seems to have VM reference '\
                    'for VM %s' % (self.name)
                return False, msg
            if api_inspect.get_cs_vmi_of_vm(self.uuid,
                                            refresh=True):
                msg = "API-Server still has VMI info of VM %s"\
                    % (self.name)
                return False, msg
        # end for

        self.logger.debug('%s removed from api-server' % self.name)
        return True, None

    def _verify_in_orch (self):
        if not self._read_orch_obj()[0]:
            return False, '%s not found in orchestrator' % self
        return True, None

    @retry(delay=5, tries=6)
    def _verify_not_in_orch (self):
        if self._ctrl.get_virtual_machine(self.uuid):
            msg = '%s not removed from orchestrator' % self
            self.logger.debug(msg)
            return False, msg
        self.logger.debug('%s removed from orchestrator' % self)
        return True, None

    @retry(delay=2, tries=20)
    def _verify_in_agent(self):
        ''' Verifies whether VM has got created properly in agent.

        '''
        self.vm_in_agent_flag = True

        # Verification in vcenter plugin introspect
        # vcenter introspect not working.disabling vcenter verification till.
        # if getattr(self.orch,'verify_vm_in_vcenter',None):
        #    assert self.orch.verify_vm_in_vcenter(self.vm_obj)

        inspect_h = self.agent_inspect[self.vm_node_ip]
        for vn_fq_name in self.vn_fq_names:
            (domain, project, vn) = vn_fq_name.split(':')
            agent_vn_obj = inspect_h.get_vna_vn(domain, project, vn)
            if not agent_vn_obj:
                msg = 'VN %s is not seen in agent %s' % (
                    vn_fq_name, self.vm_node_ip)
                self.vm_in_agent_flag = self.vm_in_agent_flag and False
                return False, msg

            # Check if the VN ID matches between the Orchestration S and Agent
            # ToDo: msenthil should be == check of vn_id[vn_fq_name] rather
            # than list match
            if agent_vn_obj['uuid'] not in self.vn_ids:
                msg = 'Unexpected VN UUID %s found in agent %s '\
                    'Expected: One of %s' % (agent_vn_obj['uuid'],
                    self.vm_node_ip, self.vn_ids)
                self.vm_in_agent_flag = self.vm_in_agent_flag and False
                return False, msg
            try:
                vna_tap_id = self.get_tap_intf_of_vmi(
                    self.get_vmi_ids()[vn_fq_name])
            except Exception as e:
                vna_tap_id = None

            self.tap_intf[vn_fq_name] = vna_tap_id
            if not self.tap_intf[vn_fq_name]:
                msg = 'Tap interface in VN %s for VM %s not'\
                    'seen in agent %s ' % (
                    vn_fq_name, self.name, self.vm_node_ip)
                self.vm_in_agent_flag = self.vm_in_agent_flag and False
                return False, msg
            mac_addr = self.tap_intf[vn_fq_name]['mac_addr']
            #For vcenter gateway case, mac in tap interface was in lower case,but mac
            # in api server was in upper case, though the value was same
            if mac_addr.lower() != self.get_mac_addr_from_config()[vn_fq_name].lower():
                msg = 'VM Mac address for VM %s not seen in'\
                    'agent %s or VMI mac is not matching with API'\
                    'Server information' % (self.name, self.vm_node_ip)
                self.vm_in_agent_flag = self.vm_in_agent_flag and False
                return False, msg
            try:
                self.tap_intf[vn_fq_name] = inspect_h.get_vna_intf_details(
                    self.tap_intf[vn_fq_name]['name'])[0]
            except Exception as e:
                return False, e 

            self.logger.debug("VM %s Tap interface: %s" % (self.name,
                                                           str(self.tap_intf[vn_fq_name])))

            self.agent_vrf_name[vn_fq_name] = self.tap_intf[
                vn_fq_name]['vrf_name']

            self.logger.debug("Agent %s vrf name: %s" %
                              (self.vm_node_ip, str(self.agent_vrf_name[vn_fq_name])))

            try:
                agent_vrf_objs = inspect_h.get_vna_vrf_objs(
                    domain, project, vn)
            except Exception as e:
                agent_vrf_objs = None

            self.logger.debug("Agent VRF Object : %s" % (str(agent_vrf_objs)))
            if not agent_vrf_objs:
                return False, None
            # Bug 1372858
            try:
                agent_vrf_obj = self.get_matching_vrf(
                    agent_vrf_objs['vrf_list'],
                    self.agent_vrf_name[vn_fq_name])
            except Exception as e:
                self.logger.warn("Exception: %s" % (e))
                return False, e

            self.agent_vrf_id[vn_fq_name] = agent_vrf_obj['ucindex']
            self.agent_path[vn_fq_name] = list()
            self.agent_label[vn_fq_name] = list()
            if self.vnc_lib_fixture.get_active_forwarding_mode(vn_fq_name) != 'l2':
                try:
                    for vm_ip in self.vm_ip_dict[vn_fq_name]:
                        agent_path = inspect_h.get_vna_active_route(
                            vrf_id=self.agent_vrf_id[vn_fq_name],
                            ip=vm_ip)
                        if agent_path is None:
                            return False, None
                        self.agent_path[vn_fq_name].append(agent_path)
                except Exception as e:
                    self.logger.exception('Error while getting agent route')
                    return False, e
                if not self.agent_path[vn_fq_name]:
                    msg = 'No path seen for VM IP %s in agent %s'\
                        % (self.vm_ip_dict[vn_fq_name], self.vm_node_ip)
                    self.vm_in_agent_flag = self.vm_in_agent_flag and False
                    return False, msg
                for agent_path in self.agent_path[vn_fq_name]:
                    for intf in agent_path['path_list']:
                        if 'itf' in intf['nh']:
                            intf_name = intf['nh']['itf']
                            if not intf['nh'].get('mc_list', None):
                                agent_label = intf['label']
                            break
                        self.agent_label[vn_fq_name].append(agent_label)

                        if intf_name != \
                              self.tap_intf[vn_fq_name]['name']:
                           msg = "Active route in agent for %s is "\
                            "not pointing to right tap interface. It is %s "\
                            % (self.vm_ip_dict[vn_fq_name],
                           agent_path['path_list'][0]['nh']['itf']) 
                           self.vm_in_agent_flag = self.vm_in_agent_flag and False
                           return False, msg
                        else:
                            self.logger.debug('Active route in agent is present for'
                                              ' VMI %s ' % (self.tap_intf[vn_fq_name]['name']))

                        if self.tap_intf[vn_fq_name]['label'] != agent_label:
                            msg = 'VM %s label mismatch! ,'\
                                ' Expected : %s , Got : %s' % (self.name,
                                self.tap_intf[vn_fq_name]['label'], agent_label) 
                            self.vm_in_agent_flag = self.vm_in_agent_flag and False
                            return False, msg
                        else:
                            self.logger.debug('VM %s labels in tap-interface and '
                                              'the route do match' % (self.name))

            # Check if tap interface is set to Active
            if self.tap_intf[vn_fq_name]['active'] != 'Active':
                self.logger.warn('VM %s : Tap interface %s is not set to '
                                 'Active, it is : %s ' % (self.name,
                                                          self.tap_intf[
                                                              vn_fq_name]['name'],
                                                          self.tap_intf[vn_fq_name]['active']))
            else:
                self.logger.debug('VM %s : Tap interface %s is set to '
                                  ' Active' % (self.name,
                                               self.tap_intf[vn_fq_name]['name']))
            self.local_ips[vn_fq_name] = self.tap_intf[
                vn_fq_name]['mdata_ip_addr']
            self.logger.debug('Tap interface %s detail : %s' % (
                self.tap_intf[vn_fq_name]['name'], self.tap_intf[vn_fq_name]))

            if 'l2' in self.vnc_lib_fixture.get_active_forwarding_mode(vn_fq_name):
                if not self._do_l2_verification(vn_fq_name, inspect_h):
                    return False, None

            # Check if VN for the VM and route for the VM is present on all
            # compute nodes
            if not self.verify_in_all_agents(vn_fq_name):
                self.vm_in_agent_flag = self.vm_in_agent_flag and False
                return False, None

        # end for vn_fq_name in self.vn_fq_names


        # Ping to VM IP from host
        if not self.local_ip:
            msg = 'Ping to one of the 169.254.x.x IPs of the VM'\
                ' should have passed. It failed! '
            self.vm_in_agent_flag = self.vm_in_agent_flag and False
            return False, msg
        self.logger.info("VM %s verifications in Compute nodes passed" %
                         (self.name))
        self.vm_in_agent_flag = self.vm_in_agent_flag and True

        if self.inputs.many_computes:
            self.get_interested_computes()
        return True, None
    #end _verify_in_agent 

    def verify_in_all_agents(self, vn_fq_name):
        ''' Verify if the corresponding VN for a VM is present in all compute nodes.
            Also verifies that a route is present in all compute nodes for the VM IP
        '''
        if self.inputs.many_computes:
            self.logger.warn('Skipping verification on all agents since '
                             'there are more than 10 computes in the box, '
                             'until the subroutine supports gevent/mp')
            return True
        (domain, project, vn_name) = vn_fq_name.split(':')
        for compute_ip in self.inputs.compute_ips:
            inspect_h = self.agent_inspect[compute_ip]
            vn = inspect_h.get_vna_vn(domain, project, vn_name)
            # The VN for the VM under test may or may not be present on other agent
            # nodes. Proceed to check only if VN is present
            if vn is None:
                continue

            if vn['name'] != vn_fq_name:
                self.logger.warn(
                    'VN %s in agent is not the same as expected : %s ' %
                    (vn['name'], vn_fq_name))
                return False
            else:
                self.logger.debug('VN %s is found in Agent of node %s' %
                                  (vn['name'], compute_ip))
            if not vn['uuid'] in self.vn_ids:
                self.logger.warn(
                    'VN ID %s from agent is in VN IDs list %s of the VM in '
                    'Agent node %s' % (vn['uuid'], self.vn_ids, compute_ip))
                return False
# TODO : To be uncommented once the sandesh query with service-chaining works
#            if vn['vrf_name'] != self.agent_vrf_name :
#                self.logger.warn('VN VRF of %s in agent is not the same as expected VRF of %s' %( vn['vrf_name'], self.agent_vrf_name ))
#                return False
            agent_vrf_objs = inspect_h.get_vna_vrf_objs(
                domain, project, vn_name)
            agent_vrf_obj = self.get_matching_vrf(
                agent_vrf_objs['vrf_list'],
                self.agent_vrf_name[vn_fq_name])
            agent_vrf_id = agent_vrf_obj['ucindex']
            if self.vnc_lib_fixture.get_active_forwarding_mode(vn_fq_name) != 'l2':
                for vm_ip in self.vm_ip_dict[vn_fq_name]:
                    agent_path = inspect_h.get_vna_active_route(
                        vrf_id=agent_vrf_id, ip=vm_ip)
                    for path in agent_path['path_list']:
                        if not path['nh'].get('mc_list', None):
                            agent_label = path['label']
                            self.agent_label[vn_fq_name].append(agent_label)
                            break
                        if agent_label not in self.agent_label[vn_fq_name]:
                            self.logger.warn(
                                'The route for VM IP %s in Node %s is having '
                                'incorrect label. Expected: %s, Seen : %s' % (
                                    vm_ip, compute_ip,
                                    self.agent_label[vn_fq_name], agent_label))
                            return False

            self.logger.debug(
                'VRF IDs of VN %s is consistent in agent %s' %
                (vn_fq_name, compute_ip))
            self.logger.debug(
                'Route for VM IP %s is consistent in agent %s ' %
                (self.vm_ip_dict[vn_fq_name], compute_ip))
            self.logger.debug(
                'VN %s verification for VM %s  in Agent %s passed ' %
                (vn_fq_name, self.name, compute_ip))

            if 'l2' in self.vnc_lib_fixture.get_active_forwarding_mode(vn_fq_name):
                self.logger.debug(
                    'Starting all layer 2 verification in agent %s' % (compute_ip))
                agent_l2_path = inspect_h.get_vna_layer2_route(
                    vrf_id=agent_vrf_id,
                    mac=self.get_mac_addr_from_config()[vn_fq_name])
                agent_l2_label = agent_l2_path[
                    'routes'][0]['path_list'][0]['label']
                if agent_l2_label != self.agent_l2_label[vn_fq_name]:
                    self.logger.warn('The route for VM MAC %s in Node %s '
                                     'is having incorrect label. Expected: %s, Seen: %s'
                                     % (self.mac_addr[vn_fq_name], compute_ip,
                                        self.agent_l2_label[vn_fq_name], agent_l2_label))
                    return False
                self.logger.debug(
                    'Route for VM MAC %s is consistent in agent %s ' %
                    (self.mac_addr[vn_fq_name], compute_ip))
        # end for
        return True
    # end verify_in_all_agents

    @property
    def interested_computes(self):
        return self.get_interested_computes()

    def get_interested_computes(self, refresh=False):
        ''' Query control node to get a list of compute nodes
            interested in the VMs vrfs
        '''
        if getattr(self, '_interested_computes', None) and not refresh:
            return self._interested_computes
        self._interested_computes = get_interested_computes(self.connections,
                                                            self.vn_fq_names)
        return self._interested_computes
    # end get_interested_computes

    @retry(delay=2, tries=20)
    def _verify_not_in_agent(self):
        '''Verify that the VM is fully removed in all Agents and vrouters

        '''
        # Verification in vcenter plugin introspect
        # if getattr(self.orch,'verify_vm_not_in_vcenter',None):
        #    assert self.orch.verify_vm_not_in_vcenter(self.vm_obj)

        result = True
        msg = []
        self.verify_vm_not_in_agent_flag = True
        vrfs = self.get_vrf_ids()
        inspect_h = self.agent_inspect[self.vm_node_ip]
        # Check if VM is in agent's active VMList:
        if self.uuid in inspect_h.get_vna_vm_list():
            msg.append("VM %s is still present in agent's active VMList" % (
                self.name))
            self.verify_vm_not_in_agent_flag = self.verify_vm_not_in_agent_flag and False
            result = result and False
        if len(inspect_h.get_vna_tap_interface_by_vm(vm_id=self.uuid)) != 0:
            msg.append("VMI/TAP interface(s) is still seen for VM "\
                "%s in agent" % (self.name))
            self.verify_vm_not_in_agent_flag = \
                self.verify_vm_not_in_agent_flag and False
            result = result and False
        for k, v in vrfs.items():
            inspect_h = self.agent_inspect[k]
            for vn_fq_name in self.vn_fq_names:
                if vn_fq_name in v:
                    for vm_ip in self.get_vm_ip_dict()[vn_fq_name]:
                        if inspect_h.get_vna_active_route(
                                vrf_id=v[vn_fq_name],
                                ip=vm_ip) is not None:
                            msg.append("Route for VM %s, IP %s is still seen "\
                                "in agent %s" % (self.name, vm_ip,
                                self.vm_node_ip))
                            self.verify_vm_not_in_agent_flag = \
                                self.verify_vm_not_in_agent_flag and False
                            result = result and False
                else:
                    continue
        # end for

        # Do validations in vrouter
        for vn_fq_name in self.vn_fq_names:
            result = result and self._verify_not_in_vrouter(vn_fq_name)
        if result:
            self.logger.info(
                "VM %s is removed in Compute, and routes are removed "
                "in all compute nodes" % (self.name))
        return result, msg
    #end _verify_not_in_agent

    @retry(delay=2, tries=5)
    def _verify_not_in_vrouter(self, vn_fq_name):
        ''' For each compute node, for Vn's vrf, if vrf is still in agent,
            check that VM's /32 route is removed
            If the vrf is not in agent, Check that the route table in vrouter
            is also cleared
        '''
        compute_ips = self.inputs.compute_ips
        # If large number of compute nodes, try to query less number of them
        if self.inputs.many_computes:
            compute_ips = self.interested_computes
        if not compute_ips:
            self.logger.debug('No interested compute node info present.'
                              ' Skipping vm cleanup check in vrouter')
            return True
        curr_vrf_ids = self.get_vrf_ids(refresh=True)
        for compute_ip in compute_ips:
            vrf_id = None
            earlier_agent_vrfs = self.vrf_ids.get(compute_ip)
            inspect_h = self.agent_inspect[compute_ip]
            if earlier_agent_vrfs:
                vrf_id = earlier_agent_vrfs.get(vn_fq_name)
            curr_vrf_id = curr_vrf_ids.get(compute_ip, {}).get(vn_fq_name)
            if vrf_id and not curr_vrf_id:
                # The vrf is deleted in agent. Check the same in vrouter
                vrouter_route_table = inspect_h.get_vrouter_route_table(
                    vrf_id)
                if vrouter_route_table:
                    self.logger.warn('Vrouter on Compute node %s still has vrf '
                        ' %s for VN %s. Check introspect logs' %(
                            compute_ip, vrf_id, vn_fq_name))
                    return False
                else:
                    self.logger.debug('Vrouter on Compute %s has deleted the '
                        'vrf %s for VN %s' % (compute_ip, vrf_id, vn_fq_name))
                # endif
            elif curr_vrf_id:
                # vrf is in agent. Check that VM route is removed in vrouter
                curr_vrf_dict = inspect_h.get_vna_vrf_by_id(curr_vrf_id)
                if vn_fq_name not in curr_vrf_dict.get('name'):
                    self.logger.debug('VRF %s already used by some other VN %s'
                        '. Would have to skip vrouter check on %s' % (
                        curr_vrf_id, curr_vrf_dict.get('name'), compute_ip))
                    return True
                prefixes = self.vm_ip_dict[vn_fq_name]
                for prefix in prefixes:
                    route_table = inspect_h.get_vrouter_route_table(
                        curr_vrf_id,
                        prefix=prefix,
                        prefix_len='32',
                        get_nh_details=True)
                    if len(route_table):
                        # If the route exists, it should be a discard route
                        # A change is pending in agent for label to be marked
                        # as 0 always. Until then, check for 1048575 also
                        if route_table[0]['nh_id'] != '1' or \
                            route_table[0]['label'] not in ['0', '1048575']:
                            self.logger.warn('VM route %s still in vrf %s of '
                            ' VN %s of compute %s' %(prefix, curr_vrf_id,
                                                     vn_fq_name, compute_ip))
                            return False
                        else:
                            self.logger.debug('VM route %s has been marked '
                                'for discard in VN %s of compute %s' % (
                                prefix, vn_fq_name, compute_ip))
                    else:
                        self.logger.debug('VM route %s is not in vrf %s of VN'
                            ' %s of compute %s' %(prefix, curr_vrf_id,
                                                  vn_fq_name, compute_ip))
                # end for prefix
                # end if
            # end if
            self.logger.debug('Validated that vrouter  %s does not '
                ' have VMs route for VN %s' %(compute_ip,
                    vn_fq_name))
        # end for compute_ip
        self.logger.info('Validated that all vrouters do not '
            ' have VMs route for VN %s' %(vn_fq_name))
        return True
    # end _verify_not_in_vrouter

class VMFixture(VMFixture_v2):
   ''' Fixture for backward compatiblity '''
   #vn_fixtures arg need to be passed in place of vn_obj to use VMFixture
   def __init__ (self, connections,
                 **kwargs):
       domain = connections.domain_name
       prj = kwargs.get('project_name') or connections.project_name
       prj_fqn = domain + ':' + prj
       name = kwargs.get('vm_name')
       self.inputs = connections.inputs
       self.vn_fixtures = kwargs.get('vn_fixtures')
       objs = {'fixtures': {}, 'args': {}, 'id-map': {}, 'fqn-map': {}, 'name-map': {}}

       self._add_to_objs(objs, self.vn_fixtures[0].name, self.vn_fixtures[0])
       if name:
           uuid = self._check_if_present(connections, name, [domain, prj])
           if uuid:
               super(VMFixture, self).__init__(connections=connections,
                                               uuid=uuid)
               return
       else:
           name = get_random_name(prj)

       self._construct_nova_params(name, prj_fqn, kwargs)
       super(VMFixture, self).__init__(connections=connections,
                                       params=self._params, fixs=objs)

   def _check_if_present (self, conn, name, prj_fqn):
       uuid = prj_fqn + [name]
       obj = conn.get_orch_ctrl().get_api('vnc').get_virtual_network(uuid)
       if not obj:
           return None
       return uuid

   def setUp (self):
       super(VMFixture, self).setUp()
       self.vnc_api = self._vnc._vnc # direct handle to vnc library
       self._qh = self._ctrl.get_api('openstack').nova_handle

   def cleanUp (self):
       super(VMFixture, self).cleanUp()

   def _construct_nova_params (self, name, prj_fqn, kwargs):
       vn_fixtures = kwargs.get('vn_fixtures', None)
       if not vn_fixtures:
            return False
       self._params = {
           'type': 'OS::Nova::Server',
           'name': name,
           'image': kwargs.get('image', 'cirros'),
           'flavor': kwargs.get('flavor', 'contrail_flavor_tiny'),
           #<TBD>Need to revisit this to support multiple VNs
           'networks': [{'network': vn_fixtures[0].uuid}]
       }

