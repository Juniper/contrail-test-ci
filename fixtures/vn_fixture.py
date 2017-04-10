#TODO: integrate with vn_test.py
#TODO: [D] replace get_uuid -> uuid
#TODO: [D] replace vn_id -> uuid
#TODO: [D] replace get_vn_fq_name -> fq_name_str
#TODO: [D] replace get_name -> name
#TODO: remove ref get_api_obj, get_obj, getObj
#TODO: replace create_port, delete_port update_port
#      to def in base.py
#TODO: replace get_vrf_id to def in ComputeNodeFixture
#TODO: add_forwarding_mode -> set_forwarding_mode
#TODO: remove refs to add_host_routes, del_host_routes

from contrail_fixtures import ContrailFixture
from tcutils.util import retry
from vnc_api.vnc_api import VirtualNetwork
from tcutils.test_lib.contrail_utils import get_interested_computes
from common.policy import policy_test_utils
from netaddr import IPNetwork

class VNFixture_v2 (ContrailFixture):

   vnc_class = VirtualNetwork

   def __init__ (self, connections, uuid=None, params=None, fixs=None):
       super(VNFixture_v2, self).__init__(
           uuid=uuid,
           connections=connections,
           params=params,
           fixs=fixs)
       self.api_s_inspect = connections.api_server_inspect
       self.agent_inspect = connections.agent_inspect
       self.cn_inspect = connections.cn_inspect
       self.analytics_obj = connections.analytics_obj
       self._interested_computes = []
       self._vrf_ids = {}

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

   @retry(delay=1, tries=5)
   def _read_vnc_obj (self):
       obj = self._vnc.get_virtual_network(self.uuid)
       found = 'not' if not obj else ''
       self.logger.warn('%s %s found in api-server' % (self, found))
       return obj != None, obj

   @retry(delay=1, tries=5)
   def _read_orch_obj (self):
       obj = self._ctrl.get_virtual_network(self.uuid)
       found = 'not' if not obj else ''
       self.logger.warn('%s %s found in orchestrator' % (self, found))
       return obj != None, obj

   def _read (self):
       ret, obj = self._read_vnc_obj()
       if ret:
           self._vnc_obj = obj
       ret, obj = self._read_orch_obj()
       if ret:
           self._obj = obj

   def _create (self):
       self.logger.info('Creating %s' % self)
       self.uuid = self._ctrl.create_virtual_network(
           **self._args)

   def _delete (self):
       self.logger.info('Deleting %s' % self)
       self._ctrl.delete_virtual_network(
           obj=self._obj, uuid=self.uuid)

   def _update (self):
       self.logger.info('Updating %s' % self)
       self._ctrl.update_virtual_network(
           obj=self._obj, uuid=self.uuid, **self.args)

   @property
   def ri_name (self):
       return self.fq_name_str + ':' + self.name

   @property
   def vrf_name (self):
       return self.ri_name

   def verify_on_setup (self):
       self.assert_on_setup(*self._verify_in_api_server())
       self.assert_on_setup(*self._verify_in_control_nodes())
       self.assert_on_setup(*self._verify_policy_in_api_server())
       self.assert_on_setup(*self._verify_in_opserver())
       self.assert_on_setup(*self._verify_in_agent())

   def verify_on_cleanup (self):
       self.assert_on_cleanup(*self._verify_not_in_api_server())
       self.assert_on_cleanup(*self._verify_not_in_agent())
       self.assert_on_cleanup(*self._verify_not_in_vrouter())
       self.assert_on_cleanup(*self._verify_not_in_control_nodes())

   def verify_on_setup_without_collector (self):
       self.assert_on_setup(*self._verify_in_api_server())
       self.assert_on_setup(*self._verify_in_control_nodes())
       self.assert_on_setup(*self._verify_policy_in_api_server())
       self.assert_on_setup(*self._verify_in_opserver())

   def _read_interested_computes (self):
       # Query control node to get a list of compute nodes
       # interested in the VNs vrf
       self._interested_computes = get_interested_computes(self.connections,
                                                           [self.fq_name_str])

   def _read_vrf_ids (self):
       vrf_id_dict = {}
       for ip in self.inputs.compute_ips:
           inspect_h = self.agent_inspect[ip]
           vrf_id = inspect_h.get_vna_vrf_id(self.fq_name_str)
           if vrf_id:
               vrf_id_dict.update({ip:vrf_id})
       self._vrf_ids = vrf_id_dict

   def get_allowed_peer_vns_by_policy (self):
       # This is allowed list and not actual peer list, which is
       # based on action by both peers
       domain, project, name = *self.fq_name
       pol_name_list = []
       allowed_peer_vns = []
       pol_list_ref = self._vnc_obj.get_network_policy_refs()
       if pol_list_ref:
           for pol in pol_list_ref:
               pol_name_list.append(str(pol['to'][2]))
       if pol_name_list:
           for pol in pol_name_list:
               pol_object = self.api_s_inspect.get_cs_policy(domain=domain,
                               project=project, policy=pol, refresh=True)
               pol_rules = pol_object['network-policy'][
                                      'network_policy_entries'][
                                      'policy_rule']
               for rule in pol_rules:
                   # Only for those rules, where local vn is listed, 
                   # pick the peer...
                   # Also, local vn can appear as source or dest vn
                   rule_vns = []
                   src_vn = rule['src_addresses'][0]['virtual_network']
                   rule_vns.append(src_vn)
                   dst_vn = rule['dst_addresses'][0]['virtual_network']
                   rule_vns.append(dst_vn)
                   if self.fq_name_str in rule_vns:
                       rule_vns.remove(self.fq_name_str)
                       # Consider peer VN route only if the action is
                       # set to pass
                       if rule['action_list']['simple_action'] == 'pass':
                            allowed_peer_vns.append(rule_vns[0])
                   elif 'any' in rule_vns:
                       if rule['action_list']['simple_action'] == 'pass':
                            allowed_peer_vns.append('any')
       return allowed_peer_vns

   def _verify_network_id (self):
       # Verify basic VN network id allocation
       # Currently just checks if it is not 0
       try:
           vn_network_id = self._vnc_obj.virtual_network_network_id
       except AttributeError:
           return False, 'VN id not seen in api-server for Vn %s' % self
       if int(vn_network_id) == int(0):
           return False, 'VN id for Vn %s is set to 0' % self
       return True, None

   def _get_rt_info (self, policy_peer_vns):
       pol_name_list = []
       rt_import_list = []
       rt_export_list = []
       rt_list1 = self.api_s_inspect.get_cs_route_targets(vn_id=self.uuid)
       rt_name1 = self.api_s_inspect.get_cs_rt_names(rt_obj=rt_list1)
       rt_export_list = rt_name1
       rt_import_list.append(rt_name1[0])

       # Get the valid peer VN list for route exchange from calling code
       # as it needs to be looked from outside of VN fixture...
       # Get the RT for each VN found in policy list
       if policy_peer_vns:
           for vn_name in policy_peer_vns:
               vn_id = self._vnc.get_virtual_network(vn_name.split(':')).uuid
               rt_list = self.api_s_inspect.get_cs_route_targets(vn_id=vn_id)
               rt_names = self.api_s_inspect.get_cs_rt_names(rt_obj=rt_list)
               for rt_name in rt_names:
                   rt_import_list.append(rt_name)
       return {'rt_export': rt_export_list, 'rt_import': rt_import_list}

   def verify_route_target (self, policy_peer_vns):
       # For expected rt_import data, we need to inspect policy attached
       # to both the VNs under test.. Both VNs need to have rule in
       # policy with action as pass to other VN..  This data needs to
       # come from calling test code as policy_peer_vns
       for i in range(len(self.inputs.bgp_ips)):
           cn = self.inputs.bgp_ips[i]
           self.logger.debug("Checking VN RT in control node %s" % cn)
           cn_ref = self.cn_inspect[cn]
           vn_ri = cn_ref.get_cn_routing_instance(ri_name=self.ri_name)
           act_rt_import = vn_ri['import_target']
           act_rt_export = vn_ri['export_target']
           self.logger.debug("act_rt_import is %s, act_rt_export is %s" %
                            (act_rt_import, act_rt_export))
           exp_rt = self._get_rt_info(policy_peer_vns)
           self.logger.debug("exp_rt_import is %s, exp_rt_export is %s" %
                            (exp_rt['rt_import'], exp_rt['rt_export']))
           compare_rt_export = policy_test_utils.compare_list(
                self, exp_rt['rt_export'], act_rt_export)
           compare_rt_import = policy_test_utils.compare_list(
                self, exp_rt['rt_import'], act_rt_import)
           self.logger.debug(
               "compare_rt_export is %s, compare_rt_import is %s" % (
               compare_rt_export, compare_rt_import))
           if compare_rt_export and compare_rt_import:
               return True, None
           else:
               msg = '%s verify_route_target failed in control node %s' % (
                     self, cn)
               return False, msg

   def _verify_in_opserver (self):
       return self.analytics_obj.verify_vn_link(self.fq_name_str)

   @retry(delay=5, tries=30)
   def _verify_not_in_agent (self):
       for compute_ip in self.inputs.compute_ips:
           inspect_h = self.agent_inspect[compute_ip]
           domain, project, name = *self.fq_name
           vn = inspect_h.get_vna_vn(domain=domain, project=project,
                                     vn_name=name)
           if vn:
               msg = 'VN %s is still found in %s' % (name, compute_ip)
               return False, msg
           vrf_objs = inspect_h.get_vna_vrf_objs(domain=domain,
                            project=project, vn_name=name)
           if len(vrf_objs['vrf_list']) != 0:
               msg = 'VRF %s for VN %s is still found in agent %s' % (str(
                      self.ri_name), self.name, compute_ip))
               return False, msg
        return True, None

   @retry(delay=5, tries=10)
   def _verify_in_api_server (self):
       domain, project, name = *self.fq_name
       api_s_vn_obj = self.api_s_inspect.get_cs_vn(domain=domain,
               project=project, vn=name, refresh=True)
       if not api_s_vn_obj:
           msg = "VN %s is not found in API-Server" % self.name
           return False, msg
       if api_s_vn_obj['virtual-network']['uuid'] != self.uuid:
           msg = "VN %s ID mismatch in API-Server" % self.uuid
           return False, msg

       subnets = api_s_vn_obj['virtual-network']['network_ipam_refs'][0][
                              'attr']['ipam_subnets']
       for vn_subnet in self._subnets:
           subnet_found = False
           vn_subnet_cidr = str(IPNetwork(vn_subnet).ip)
           for subnet in subnets:
               if subnet['subnet']['ip_prefix'] == vn_subnet_cidr:
                   subnet_found = True
           if not subnet_found:
               msg = "Subnet IP %s not found in API-Server for VN %s" % (
                      vn_subnet_cidr, self.vn_name)
               return False, msg

       api_s_route_targets = self.api_s_inspect.get_cs_route_targets(
               vn_id=self.uuid)
       if not api_s_route_targets:
           errmsg = "Route targets not found in API-Server for VN %s" % (
                     self.name)
           return False, msg
       rt_names = self.api_s_inspect.get_cs_rt_names(api_s_route_targets)
       if not rt_names:
           msg = 'RT names not yet present for VN %s' % self.vn_name
           return False, msg

       if self._rt_number:
           if not any(item.endswith(self.rt_number) for item in rt_names):
               msg = 'RT %s is not found in API Server RT list %s' % (
                      self._rt_number, rt_names)
               return False, msg

       api_s_routing_instance = self.api_s_inspect.get_cs_routing_instances(
               vn_id=self.uuid)
       if not api_s_routing_instance:
           msg = "Routing Instances not found in API-Server for VN %s" % (
               self.name)
           return False, msg

       self._ri_ref = api_s_routing_instance['routing_instances'][0][
                                             'routing-instance']
       return self._verify_network_id()

   @retry(delay=5, tries=3)
   def _verify_not_in_api_server (self):
       if self.api_s_inspect.get_cs_ri_by_id(self._ri_ref['uuid']):
           msg = "RI %s is still found in API-Server" % self.ri_ref['name']
           return False, msg
       domain, project, name = *self.fq_name
       if self.api_s_inspect.get_cs_vn(domain=domain, project=project,
                                       vn=name, refresh=True):
           msg = "VN %s is still found in API-Server" % self.name
           return False, msg
       return True, None

   @retry(delay=5, tries=25)
   def _verify_in_agent (self):
       # No real verification for now, collect vrfs so that they can be
       # verified during cleanup
       self._read_vrf_ids()
       if self.inputs.many_computes:
           self._read_interested_computes()
       return True, None

   @retry(delay=5, tries=25)
   def _verify_in_control_nodes (self):
       api_s_route_targets = self.api_s_inspect.get_cs_route_targets(
               vn_id=self.uuid)
       domain, project, name = *self.fq_name
       for cn in self.inputs.bgp_ips:
           cn_config_vn_obj = self.cn_inspect[cn].get_cn_config_vn(
               vn_name=name, project=project, domain=domain)
           if not cn_config_vn_obj:
               msg = 'Control-node %s does not have VN %s info' % (cn,
                      self.name)
               return False, msg
           if self.fq_name_str not in cn_config_vn_obj['node_name']:
               msg = 'VN %s not found in IFMAP View of Control-node' % (
                      self.fq_name_str))
               return False, msg
           # TODO UUID verification to be done once the API is available
           cn_object = self.cn_inspect[cn].get_cn_routing_instance(
                       ri_name=self.ri_name)
           if not cn_object:
               msg = 'No Routing Instance found in CN %s with name %s' % (
                      cn, self.ri_name)
               return False, msg
           try:
               rt_names = self.api_s_inspect.get_cs_rt_names(
                           api_s_route_targets)
               if cn_object['export_target'][0] not in rt_names:
                   msg = "Route target %s (VN %s) not found in Control %s" % (
                          rt_names, self.name, cn)
                   return False, msg
           except Exception as e:
               msg = "Got exception from control verification as %s" % e
               return False, msg
        return True, None

   @retry(delay=5, tries=20)
   def _verify_not_in_control_nodes (self):
       for cn in self.inputs.bgp_ips:
           cn_object = self.cn_inspect[cn].get_cn_routing_instance(
               ri_name=self.ri_name)
           if cn_object:
               msg = "Routing instance (VN %s) still found in Control%s" % (
                     self.name, cn)
       domain, project, name = *self.fq_name
       if self.cn_inspect[cn].get_cn_config_vn(vn_name=name,
               project=project, domain=domain):
            msg = "Control-node config DB still has VN %s" % (self.name)
            return False, msg
        return True, None

   @retry(delay=2, tries=20)
   def _verify_not_in_vrouter (self):
       compute_ips = self.inputs.compute_ips
       # If large number of compute nodes, try to optimize
       if self.inputs.many_computes:
           compute_ips = self._interested_computes
       if not compute_ips:
           self.logger.debug('No interested compute node info present.'
                             ' Skipping VN cleanup check in vrouter')
           return True, None
       for compute_ip in compute_ips:
           if not compute_ip in self._vrf_ids.keys():
               continue
           inspect_h = self.agent_inspect[compute_ip]
           vrf_id = self._vrf_ids[compute_ip]
           # Check again if agent does not have this vrf by chance
           curr_vrf = inspect_h.get_vna_vrf_by_id(vrf_id)
           if curr_vrf:
               if curr_vrf.get('name') == self.vrf_name:
                   msg = 'VRF %s is still seen in agent %s' % (curr_vrf,
                           compute_ip)
                   return False, msg
               else:
                   self.logger.info('VRF id %s already used by some other '
                                    'vrf %s, will have to skip vrouter '
                                    'verification on %s' % (vrf_id,
                                    curr_vrf.get('name'), compute_ip))
                   return True, None

           # Agent has deleted this vrf. Check in kernel too that 
           # it is gone
           vrouter_route_table = inspect_h.get_vrouter_route_table(vrf_id)
           if vrouter_route_table:
               msg = 'Vrouter %s still has vrf %s for VN %s' % (compute_ip,
                      vrf_id, self.name)
               return False, msg
       return True, None

   def _verify_policy_in_api_server (self):
       domain, project, name = *self.fq_name
       api_s_vn_obj = self.api_s_inspect.get_cs_vn(domain=domain,
               project=project, vn=name, refresh=True)
       try:
           vn_pol = api_s_vn_obj['virtual-network']['network_policy_refs']
       except:
           # VN has no policy to be verified
           return True, None

        # vn_pol is a list of dicts with policy info
        # check no. of policies in api-s and user given
        if len(vn_pol) != len(self._policies):
            msg = "Mis-match in number of policies %d - %d" % (len(vn_pol),
                   len(self._policies))
            self.logger.error(msg)
            self.logger.error("Data in API-S: \n")
            for policy in vn_pol:
                self.logger.error('%s' % policy['to'])
            self.logger.error("User specified: \n")
            for policy in self._policies:
                self.logger.error('%s' % policy)
            return False, msg
        return True, None


from tcutils.util import get_random_cidrs, get_af_from_cidrs, get_af_type,
                         get_random_name, is_v6
from vnc_api.vnc_api import VirtualNetworkType, RouteTargetList,
                            NetworkIpam

class VNFixture (VNFixture_v2):

    ''' Fixture for backward compatiblity '''

   @property
   def vn_fq_name (self):
       return self.fq_name_str

   @property
   def vn_name (self):
       return self.name

   @property
   def vn_subnet_objs (self):
       if getattr(self, '_subnet_objs') and self._subnet_objs:
           return self._subnet_objs
       else:
           return self.get_subnets()

   #TODO:
   def __init__ (self, connections,
                 **kwargs):
       domain = self.connections.domain_name
       prj = kwargs.get('project_name') or self.connections.project_name
       prj_fqn = domain + ':' + prj
       name = kwargs.get('vn_name')
       self._api = kwargs('option', 'quantum')

       if self._api == 'quantum':
           self._qh = self._ctrl.get_api('openstack').quantum_handle

       if name:
           uid = self._check_if_present(name, [domain, prj])
           if uid:
               super(VNFixture, self).__init__(connections=connections,
                                               uuid=uid)
               self._read_on_setup = True
               return
       else:
           name = get_random_name(prj)

       kwargs['subnets'] = self._check_subnets(kwargs.get('subnets'),
                                           kwargs.get('empty_vn'))
       if self._api == 'contrail':
           self._construct_contrail_params(name, prj_fqn, kwargs)
       else:
           self._construct_quantum_params(name, prj_fqn, kwargs)
       super(VNFixture, self).__init__(connections=connections,
                                       params=self._params)

   def _check_if_present (self, vn_name, prj_fqn):
       uid = prj_fqn + vn_name
       obj = self._ctrl.get_virtual_network(uid)
       if not obj:
           return None
       return uid

   def setUp (self):
       super(VNFixture, self).setUp()
       if self._read_on_setup:
           self._fetch_info()
       if self._subnets_pending:
           self._create_subnets()

   def cleanUp (self):
       if self._subnet_ids:
           self._delete_subnets()
       super(VNFixture, self).cleanUp()

   def _fetch_info (self):
       # policies
       self._policies = []
       for policy in self._vnc_obj.get_network_policy_refs():
           self._policies.append(policy['to'].split(':'))

   def _construct_contrail_params (self, name, prj_fqn, kwargs)
       self.params = {
           'type': 'OS::ContrailV2::VirtualNetwork'
           'name' : name,
           'project': prj_fqn,
           'is_shared': kwargs.get('shared', False)
           'router_external' : kwargs.get('router_external', False),
       }

       ipam_fqn = kwargs.get('ipam_fq_name') or NetworkIpam().get_fq_name()
       dhcp = kwargs.get('enable_dhcp', True),
       dhcp_opts = kwargs.get('dhcp_option_list')
       ipam_fqn = ipam_fqn or prj_fqn + ':' + 'default-network-ipam'
       subnets = kwargs.get('subnets', [])
       self._subnets = []
       lst = []
       for subnet in subnets:
           prefix, prefix_len = subnet.split('/')
           self._subnets.append(str(prefix) + '/' + str(prefix_len))
           dd = {'subnet': {'ip_prefix': prefix,
                            'ip_prefix_len': prefix_len},
                 'enable_dhcp' : dhcp,
                 'dhcp_option_list': dhcp_opts,
                }
           lst.append(dd)
       self.params['network_ipam_refs'] = [ipam_fqn]
       self.params['network_ipam_refs_data'] = [{'ipam_subnets':lst}]

       ecmp_hash = kwargs.get('ecmp_hash')
       if ecmp_hash:
           self.params['ecmp_hashing_include_fields'] = ecmp_hash.copy()

       vxlan_id = kwargs.get('vxlan_id')
       if vxlan_id:
           props = self.params.get('virtual_network_properties', {})
           props['vxlan_network_identifier'] = vxlan_id
           self.params['virtual_network_properties'] = props

       mode = kwargs.get('forwarding_mode')
       if mode:
           props = self.params.get('virtual_network_properties', {})
           props['forwarding_mode'] = mode
           self.params['virtual_network_properties'] = props

       asn, tgt = kwargs.get('router_asn'), kwargs.get('rt_number')
       self._rt_number = tgt
       if asn and tgt:
           lst = ["target:%s:%s" % (asn, tgt)]
           self.params['route_target_list']['route_target'] = lst

       policy_refs = []
       policy_refs_data = []
       for seq, policy in enumerate(kwargs.get('policy_objs', [])):
           policy_refs.append(policy.fq_name)
           policy_refs_data.append({
               'data_sequence': {
                   'major': seq,
                   'minor':0
               }})
       self.params['network_policy_refs'] = policy_refs
       self.params['network_policy_refs_data'] = policy_refs_data
       self._policies = policy_refs

   def _construct_quantum_params (self, name, prj_fqn, kwargs)
       self.params = {
           'type': 'OS::Neutron::Net',
           'name': name,
           'shared': kwargs.get('shared', False),
           'value_specs': {
               'router:external': kwargs.get('router_external', False),
           },
       }

       if kwargs.get('sriov_enable'):
           dd = self.params['value_specs']
           dd['provider:physical_network'] = kwargs['sriov_provider_network']
           dd['provider:segmentation_id'] = kwargs['sriov_vlan']


       policy_refs = []
       for policy in kwargs.get('policy_objs', []):
           policy_refs.append(policy.fq_name)
       self.params['contrail:policys'] = policy_refs
       self._policies = policy_refs

       ipam_fqn = kwargs.get('ipam_fq_name') or NetworkIpam().get_fq_name()
       gw = kwargs.get('disable_gateway')
       dhcp = kwargs.get('enable_dhcp', True),
       ipam_fqn = ipam_fqn or prj_fqn + ':' + 'default-network-ipam'
       self._subnets = kwargs.get('subnets', [])
       self._subnets_pending = []
       for subnet in self._subnets:
           dd = {
               'enable_dhcp': enable_dhcp,
               'ip_version': '6' if is_v6(subnet) else '4',
               'cidr': subnet,
               'contrail:ipam_fq_name': ipam_fqn,
           }
           if gw:
               dd['gateway_ip'] = None
           self._subnets_pending.append(dd)

   def _create_subnets (self):
       self._subnet_ids = []
       for subnet in self._subnets_pending:
           subnet['network_id'] = self.uuid
           rsp = self._qh.create_subnet({'subnet': subnet})
           self._subnet_ids.append(rsp['subnet']['id'])

   def _delete_subnets (self):
       for subnet in self._subnet_ids:
           self._qh.delete_subnet(subnet)

   def _check_subnets (self, subnets, empty_vn):
       af = self.inputs.get_af()
       if not subnets and not empty_vn:
           subnets = get_random_cidrs(stack=af)
       #Force add v6 subnet for dual stack when only v4 subnet is passed
       if af == 'dual' and subnets and get_af_from_cidrs(cidrs=subnets) == 'v4':
           subnets.extend(get_random_cidrs(stack='v6'))
       #Force add v4 subnet when only v6 subnet is passed
       if subnets and get_af_from_cidrs(cidrs=subnets) == 'v6':
           subnets.extend(get_random_cidrs(stack='v4'))
       return subnets

   def get_cidrs (self, af=None):
       subnets = []
       for ipam in self._vnc_obj.get_network_ipam_refs():
           for subnet in ipam['attr'].ipam_subnets:
               subnets.append(str(subnet.subnet.ip_prefix) + '/' +
                          str(subnet.subnet.ip_prefix_len))
       if not af or af == 'dual':
           return subnets
       return [x for x in subnets if af == get_af_type(x)]

   def get_dns_ip (self, ipam_fq_name=None, sub_idx=0):
       ipams = self._vnc_obj.get_network_ipam_refs()
       if not ipams:
           self.logger.error("No IPAM associated with VN")
           return None
       if not ipam_fq_name:
           ipam_fq_name = ipams[0]['to']
       for ipam in ipams:
           if ipam["to"] == ipam_fq_name:
               dns = ipam['attr'].ipam_subnets[sub_idx].dns_server_address
               break
       else:
           dns = None
           self.logger.error("DNS server for mentioned IPAM not found.")
       return dns

   def set_unknown_unicast_forwarding (self, enable=True):
       #self.params['flood_unknown_unicast'] = enable
       #self.update(self.params)
       self._vnc_obj.set_flood_unknown_unicast(enable)
       self._vnc.update_virtual_network(self._vnc_obj)
       self.update()

   def set_mac_aging_time (self, mac_aging_time):
       #self.params['mac_aging_time'] = mac_aging_time
       #self.update(self.params)
       self._vnc_obj.set_mac_aging_time(mac_aging_time)
       self._vnc.update_virtual_network(self._vnc_obj)
       self.update()

   def set_mac_move_control (self, mac_move_control):
       #self.params['mac_move_control'] = {
       #    'mac_move_limit': mac_move_control.get_mac_move_limit(),
       #    'mac_move_time_window': mac_move_control.get_mac_move_time_window(),
       #    'mac_limit_action': mac_move_control.get_mac_limit_action()
       #}
       #self.update(self.params)
       self._vnc_obj.set_mac_move_control(mac_move_control)
       self._vnc.update_virtual_network(self._vnc_obj)
       self.update()

   def set_mac_limit_control (self, mac_limit_control):
       #self.params['mac_limit_control'] = {
       #    'mac_limit': mac_limit_control.get_mac_limit(),
       #    'mac_limit_action': mac_limit_control.get_mac_limit_action(),
       #}
       #self.update(self.params)
       self._vnc_obj.set_mac_limit_control(mac_limit_control)
       self._vnc.update_virtual_network(self._vnc_obj)
       self.update()

   def set_mac_learning_enabled (self, mac_learning_enabled=True):
       #self.params['mac_learning_enabled'] = mac_learning_enabled
       #self.update(self.params)
       self._vnc_obj.set_mac_learning_enabled(mac_learning_enabled)
       self._vnc.update_virtual_network(self._vnc_obj)
       self.update()

   def set_pbb_evpn_enable (self, pbb_evpn_enable=True):
       #self.params['pbb_evpn_enable'] = pbb_evpn_enable
       #self.update(self.params)
       self._vnc_obj.set_pbb_evpn_enable(pbb_evpn_enable)
       self._vnc.update_virtual_network(self._vnc_obj)
       self.update()

   def set_pbb_etree_enable (self, pbb_etree_enable=True):
       #self.params['pbb_etree_enable'] = pbb_etree_enable
       #self.update(self.params)
       self._vnc_obj.set_pbb_etree_enable(pbb_etree_enable)
       self._vnc.update_virtual_network(self._vnc_obj)
       self.update()

   def set_forwarding_mode (self, forwarding_mode):
       #self._set_forwarding_mode(forwarding_mode)
       #self.update(self.params)
       props = self._vnc_obj.get_virtual_network_properties()
       props = props if props else VirtualNetworkType()
       props.set_forwarding_mode(forwarding_mode)
       self._vnc_obj.set_virtual_network_properties(props)
       self._vnc.update_virtual_network(self._vnc_obj)
       self.update()

   def set_ecmp_hash (self, ecmp_hash):
       #self._set_ecmp_hash(ecmp_hash)
       #self.update(self.params)
       self._vnc_obj.set_ecmp_hashing_include_fields(ecmp_hash)
       self._vnc.update_virtual_network(self._vnc_obj)
       self.update()

   def set_vxlan_id (self, vxlan_id):
       #self._set_vxlan_id(vxlan_id)
       #self.update(self.params)
       props = self._vnc_obj.get_virtual_network_properties()
       props = props if props else VirtualNetworkType()
       props.set_vlan_network_identifier(int(vxlan_id))
       self._vnc_obj.set_virtual_network_properties(props)
       self._vnc.update_virtual_network(self._vnc_obj)
       self.update()

   def get_vxlan_id (self):
       if self.connections.vnc_lib_fixture.get_vxlan_mode() == 'automatic':
           return self._vnc_obj.get_virtual_network_network_id()
       else:
           return self._vnc_obj.get_virtual_network_properties()\
                  ['vxlan_network_identifier']

   def add_route_target (self, router_asn, route_target_number):
       #self._add_route_target(router_asn, route_target_number)
       #self.update(self.params)
       val = 'target:%s:%s' % (router_asn, route_target_number)
       tgts = self._vnc_obj.get_route_target_list()
       if tgts:
           if val not in tgts.get_route_target():
               tgts.add_route_target(val)
       else:
           tgts = RouteTargetList([val])
       self._vnc_obj.set_route_target_list(tgts)
       self._vnc.update_virtual_network(self._vnc_obj)
       self.update()

   def del_route_target (self, router_asn, route_target_number):
       #dd = self.params.get('route_target_list', {})
       #lst = dd.get('route_target', [])
       #if lst:
       #    lst.remove("target:%s:%s" % (router_asn, route_target_number))
       #self.params['route_target_list'] = lst
       #self.update(self.params)
       val = 'target:%s:%s' % (router_asn, route_target_number)
       tgts = self._vnc_obj.get_route_target_list()
       if not tgts:
           return
       if val not in tgts.get_route_target():
           return
       tgts.delete_route_target(val)
       if tgts.get_route_target():
           self._vnc_obj.set_route_target_list(tgts)
       else:
           self._vnc_obj.set_route_target_list(None)
       self._vnc.update_virtual_network(self._vnc_obj)
       self.update()

   def get_an_ip (self, index=2):
       x = self._vnc_obj.get_network_ipam_refs()[0]['attr']
       pfx = x.subnets[0].subnet.ip_prefix
       pfx_len = x.subnets[0].subnet.ip_prefix_len
       cidr = str(prf) + '/' + str(pfx_len)
       return get_an_ip(cidr, index)

   def _create_subnet (self, subnet):
       params = {
           'network': self.uuid,
           'cidr': subnet,
           'ip_version': '6' if is_v6(subnet) else '4',
           'enable_dhcp': True,
       }
       self._qh.create_subnet({'subnet':params})

   def create_subnet_af (self, af, ipam_fq_name):
       if 'v4' in af or 'dual' in af:
           self._create_subnet(get_random_cidr(af='v4'))
       if 'v6' in af or 'dual' in af:
           self._create_subnet(get_random_cidr(af='v6'))

   def add_subnet (self, subnet):
       self._create_subnet(subnet)

   def update_subnet (self, subnet_id, subnet_dict):
       req = {'subnet': subnet_dict}
       self._qh.update_subnet(subnet_id, subnet_dict)
       self.vn_subnet_objs = self.quantum_h.get_subnets_of_vn(self.uuid)

   def get_subnets (self):
       ids = self._qh.show_network(self.uuid, fields='subnets')
       ids = ids['network']['subnets']
       self._subnet_objs = []
       for subnet_id in ids:
           self._subnet_objs.append(self._qh.show_subnet(subnet_id)['subnet'])
       return self._subnet_objs

   def bind_policies (self, policy_fq_names):
       if self._api == 'contrail':
           self._vnc_obj.set_network_policy_list([], True)
           self._vnc.update_virtual_network(self._vnc_obj)
           for seq, policy in enumerate(policy_fq_names):
               policy_obj = self._vnc.get_network_policy(policy)
               seq_obj = SequenceType(major=seq, minor=0)
               self._vnc_obj.add_network_policy(poilcy_obj,
                               VirtualNetworkPolicyType(sequence=seq_obj))
            self._vnc.update_virtual_network(self._vnc_obj)
       else:
            net_req = {'contrail:policys': policy_fq_names}
            self._qh.update_network(self.uuid, {'network': net_req})
       self.update()
       self._policies = policy_fq_names

   def unbind_policies (self, policy_fq_names=[]):
       if self._api == 'contrail':
           if policy_fq_names == []:
               self._vnc_obj.set_network_policy_list([],True)
               self._vnc.update_virtual_network(self._vnc_obj)
               policys_to_remain = []
           else:
               policys_to_remain = copy.copy(self._policies)
               for policy in policy_fq_names:
                   policy_obj = self._vnc.get_network_policy(policy)
                   self._vnc_obj.del_network_policy(policy_obj)
                   policys_to_remain.remove(policy)
               self._vnc.update_virtual_network(self._vnc_obj)
       else:
           if policy_fq_names == []:
               policys_to_remain = []
           else:
               policys_to_remain = copy.copy(self._policies)
               for policy in policy_fq_names:
                   policys_to_remain.remove(policy)
           net_req = {'contrail:policys': policys_to_remain}
           self._qh.update_network(self.uuid, {'network': net_req})
       self.update()
       self._policies = policy_to_remain


class NotPossibleToSubnet(Exception):

   """Raised when a given network/prefix is not possible to be subnetted to
      required numer of subnets.
   """
    pass


class MultipleVNFixture(fixtures.Fixture):

    """ Fixture to create, verify and delete multiple VNs and multiple subnets
        each.

        Deletion of the VN upon exit can be disabled by setting
        fixtureCleanup=no. If a VN with the vn_name is already present, it is
        not deleted upon exit. Use fixtureCleanup=force to force a delete.
    """

   def __init__ (self, connections, inputs, vn_count=1, subnet_count=1,
                 vn_name_net={},  project_name=None, af=None):
       """
       vn_count     : Number of VN's to be created.
       subnet_count : Subnet per each VN's
       vn_name_net  : Dictionary of VN name as key and a network with prefix to
                      be subnetted(subnet_count)as value  or list of subnets to
                      be created in that VN as value.

       Example Usage:
       1. vn_fixture = MultipleVnFixture(conn, inputs, vn_count=10,
                                         subnet_count=20)
       Creates 10 VN's with name vn1, vn2...vn10 with 20 subnets each.
       Dynamicaly identifies the subnet's and stores them as class attributes
       for future use.

       2. vn_fixture = MultipleVnFixture(conn, inputs, subnet_count=20,
                                       vn_name_net={'vn1' : '10.1.1.0/24',
                                       'vn2' : ['30.1.1.0/24', '30.1.2.0/24']})
       Creates VN's vn1 and vn2, with 20 subnets in vn1 and 2 subnets in vn2.
       """
       self.inputs = inputs
       self.connections = connections
       if not project_name:
           project_name = self.inputs.project_name
       self.stack = af or self.inputs.get_af()
       self.project_name = project_name
       self.vn_count = vn_count
       self.subnet_count = subnet_count
       self.vn_name_net = vn_name_net
       self.logger = inputs.logger
       self._vn_subnets = {}
       self._find_subnets()

    def _subnet (self, af='v4', network=None, roll_over=False):
       if not network:
           while True:
               network=get_random_cidr(af=af, mask=SUBNET_MASK[af]['min'])
               for rand_net in self.random_networks:
                   if not cidr_exclude(network, rand_net):
                      break
               else:
                   break
       net, plen = network.split('/')
       plen = int(plen)
       max_plen = SUBNET_MASK[af]['max']
       reqd_plen = max_plen - (int(self.subnet_count) - 1).bit_length()
       if plen > reqd_plen:
           if not roll_over:
               max_subnets = 2 ** (max_plen - plen)
               raise NotPossibleToSubnet("Network prefix %s can be subnetted "
                      "only to maximum of %s subnets" % (network, max_subnets))
           network = '%s/%s'%(net, reqd_plen)

       subnets = list(IPNetwork(network).subnet(plen))
       return map(lambda subnet: subnet.__str__(), subnets[:])

   def _find_subnets (self):
       if not self.vn_name_net:
           self.random_networks = []
           for i in range(self.vn_count):
               subnets = []
               if 'v4' in self.stack or 'dual' in self.stack:
                   subnets.extend(self._subnet(af='v4'))
               if 'v6' in self.stack or 'dual' in self.stack:
                   subnets.extend(self._subnet(af='v6'))
               self._vn_subnets.update({'vn%s' % (i + 1): subnets[:]})
               self.random_networks.extend(subnets)
           return
       for vn_name, net in self.vn_name_net.items():
           if type(net) is list:
               self._vn_subnets.update({vn_name: net})
           else:
               self._vn_subnets.update({vn_name: self._subnet(network=net,
                                                 af=self.stack)})

   def setUp (self):
       super(MultipleVNFixture, self).setUp()
       self._vn_fixtures = []
       for vn_name, subnets in self._vn_subnets.items():
           vn_fixture = self.useFixture(
                           VNFixture(inputs=self.inputs,
                                     connections=self.connections,
                                     project_name=self.project_name,
                                     vn_name=vn_name, subnets=subnets))
           self._vn_fixtures.append((vn_name, vn_fixture))

   def verify_on_setup (self):
       result = True
       for vn_name, vn_fixture in self._vn_fixtures:
           result &= vn_fixture.verify_on_setup()
       return result

   def get_all_subnets (self):
       return self._vn_subnets

   def get_all_fixture_obj (self):
       return map(lambda (name, fixture): (name, fixture.obj), self._vn_fixtures)

