#TODO: integrate with policy_test.py
import re
from contrail_fixtures import ContrailFixture
from tcutils.util import retry
from vnc_api.vnc_api import NetworkPolicy

class PolicyFixture_v2 (ContrailFixture):

   vnc_class = NetworkPolicy

   def __init__ (self, connections, uuid=None, params=None, fixs=None):
       super(PolicyFixture_v2, self).__init__(
           uuid=uuid,
           connections=connections,
           params=params,
           fixs=fixs)
       self.api_s_inspect = connections.api_server_inspect

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
       obj = self._vnc.get_network_policy(self.uuid)
       return obj != None, obj

   @retry(delay=1, tries=5)
   def _read_orch_obj (self):
       with self._api_ctx:
           obj = self._ctrl.get_network_policy(self.uuid)
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
       with self._api_ctx:
           self.uuid = self._ctrl.create_network_policy(
               **self._args)

   def _delete (self):
       self.logger.info('Deleting %s' % self)
       with self._api_ctx:
           self._ctrl.delete_network_policy(
               obj=self._obj, uuid=self.uuid)

   def _update (self):
       self.logger.info('Updating %s' % self)
       with self._api_ctx:
           self._ctrl.update_network_policy(
               obj=self._obj, uuid=self.uuid, **self.args)

   def verify_on_setup (self):
       self.assert_on_setup(*self._verify_in_api_server())
       self.assert_on_setup(*self._verify_in_control_nodes())
       #TODO: add verification code

   def verify_on_cleanup (self):
       self.assert_on_cleanup(*self._verify_not_in_api_server())
       #TODO: add verification code

   @retry(delay=5, tries=3)
   def _verify_in_api_server (self):
       domain, project, pol = self.fq_name
       api_s_policy_obj = self.api_s_inspect.get_cs_policy(
           domain=domain, project=project, policy=pol, refresh=True)
       if not api_s_policy_obj:
           return False, 'Policy obj not found'
       # TODO: Discuss with Ganesha & Vedu for verification code
       return True, None

   @retry(delay=5, tries=3)
   def _verify_not_in_api_server (self):
       domain, project, pol = self.fq_name
       api_s_policy_obj = self.api_s_inspect.get_cs_policy(
           domain=domain, project=project, policy=pol, refresh=True)
       if api_s_policy_obj:
           return False, 'Policy obj still found'
       return True, None

   @retry(delay=3, tries=5)
   def _verify_in_control_nodes (self):
       #TODO: present fixture code, skips this verification
       #      to discuss with Ganesha & Vedu
       return True, None

from common.policy import policy_test_utils

class PolicyFixture (PolicyFixture_v2):

   """ Fixture for backward compatiblity """

   def __init__ (self, connections, **kwargs):
       domain = connections.domain_name
       prj = kwargs.get('project_name') or connections.project_name
       prj_fqn = domain + ':' + prj
       name = kwargs['policy_name']

       uid = self._check_if_present(connections, name, [domain, prj])
       if uid:
           super(PolicyFixture, self).__init__(connections=connections,
                                           uuid=uid)
           return

       rules = policy_test_utils.update_rules_with_icmpv6(
               connections.inputs.get_af(), kwargs['rules_list'])
       policy_rule = []
       for rule in rules:
           rule_dict = {}
           rule_dict['direction'] = rule.get('direction', '<>')
           rule_dict['protocol'] = rule.get('protocol', 'any')
           rule_dict['application'] = rule.get('application')
           rule_dict['action_list'] = {
               'simple_action': rule.get('simple_action', 'pass')
           }
           self._handle_ports('src_ports', rule, rule_dict)
           self._handle_ports('dst_ports', rule, rule_dict)
           self._handle_address('src', rule, rule_dict, prj_fqn)
           self._handle_address('dst', rule, rule_dict, prj_fqn)
           policy_rule.append(rule_dict)
       self._params = {
           'name': name,
           'network_policy_entries': { 'policy_rule': policy_rule },
       }
       if kwargs.get('api'):
           self._params['type'] = 'OS::ContrailV2::NetworkPolicy'
       else:
           self._params['type'] = 'OS::Neutron::Policy'
       super(PolicyFixture, self).__init__(
               connections=connections, params=self._params)

   def _handle_ports (self, key, rule, rule_dict):
       ports = rule.get(key, 'any')
       if ports == 'any':
           ports = (-1, -1)
       rule_dict[key] = [{
           'start_port': ports[0],
           'end_port': ports[1]
       }]

   def _handle_address (self, key, rule, rule_dict, prj_fqn):
       prj_fqn = prj_fqn.split(':')
       if key == 'src':
           key_pfx = 'source'
           set_key = 'src_addresses'
       else:
           key_pfx = 'dest'
           set_key = 'dst_addresses'
       nw = key_pfx + '_network'
       network = None
       if rule.get(nw) is not None:
           m = re.match(r"(\S+):(\S+):(\S+)", rule[nw])
           if m or rule[nw] == 'any':
               network = rule[nw]
           else:
               network = ':'.join(prj_fqn + [rule[nw]])
       pol = key_pfx + '_policy'
       policy = None
       if rule.get(pol) is not None:
           m = re.match(r"(\S+):(\S+):(\S+)", rule[pol])
           if m:
               policy = rule[pol]
           else:
               policy = ':'.join(prj_fqn + [rule[pol]])
       sub = key_pfx + '_subnet'
       prf, prf_len = None, None
       if rule.get(sub) is not None:
           prf, prf_len = rule[sub].split('/')

       addr = {}
       if prf:
           addr['subnet'] = {'ip_prefix': prf, 'ip_prefix_len': prf_len}
       if network:
           addr['virtual_network'] = network
       if policy:
           addr['network_policy'] = policy
       rule_dict[set_key] = [addr]

   def _check_if_present (self, conn, name, prj_fqn):
       uid = prj_fqn + [name]
       obj = conn.get_orch_ctrl().get_api('vnc').get_network_policy(uid)
       if not obj:
           return None
       return uid

   def setUp (self):
       super(PolicyFixture, self).setUp()
       self.vnc_api = self._vnc._vnc # direct handle to vnc library
       #TODO: placeholder for additional code, if not required
       #      delete this method

   def cleanUp (self):
       super(PolicyFixture, self).cleanUp()
       #TODO: placeholder for additional code, if not required
       #      delete this method

   #TODO: ---------xxxxxxx-----------xxxxxx-------
   #      Following methods have been retained as is, need to determine 
   #      efficancy and then port these to new fixture class
   def verify_policy_in_vna (self, scn, policy_attch_to_vn=None):
       '''
       Policies attached to VN will be pushed to VNA [in Compute node] once
       a VM is spawned in a VN.
       Input:  Test scenario object is passed as input 
               [defined in policy_test_input].
       Return: returns a dictionary with keys as result & msg.
           For success, return is empty.
           For failure, result is set to False & msg has the error info.
       Steps: for each vn present in compute [vn has vm in compute]
           -whats the expected policy list for the vn
           -derive expected system rules for vn in vna
           -get actual system rules for vn in vna
           -compare
       '''
       self.logger.debug("Starting verify_policy_in_vna")
       result = True
       # expected data: translate user rules to system format for verification
       # Step 1: Translate user rules to ACEs
       user_rules_tx = {}
       if policy_attch_to_vn is None:
           policy_attch_to_vn = scn.vn_policy
       for policy in scn.policy_list:
           flag_policy_inheritance = 0
           policy_rules = scn.rules[policy]
           for rule in scn.rules[policy]:
               if (('dest_policy' in rule) or ('source_policy' in rule)):
                   flag_policy_inheritance = 1
           if flag_policy_inheritance == 1:
                policy_rules = self.tx_policy_to_vn(scn.rules[policy],
                                   policy_attch_to_vn)
           for test_vn in scn.policy_vn[policy]:
               user_rules_tx[policy] = self.tx_user_def_rule_to_aces(test_vn,
                       policy_rules)

       # Step 2: Aggregate rules by network
       rules_by_vn = {}
       for vn in scn.vnet_list:
           tmp_vn_rules = []
           rules_by_vn[vn] = []
           self.logger.debug("vn is %s, scn.vn_policy is %s" % (vn,
               scn.vn_policy[vn]))
           for policy in scn.vn_policy[vn]:
               rules_by_vn[vn] += user_rules_tx[policy]

           # remove duplicate rules after adding policies
           rules_by_vn[vn] = policy_test_utils.trim_realign_rules(
                   rules_by_vn[vn])

       # Step 3: Translate user-rules-> ACEs to system format and update ACE
       # IDs
       for vn in scn.vnet_list:
           if rules_by_vn[vn] != []:
               rules_by_vn[vn] = self.tx_user_def_aces_to_system(
                   vn, rules_by_vn[vn])
               rules_by_vn[vn] = policy_test_utils.update_rule_ace_id(
                   rules_by_vn[vn])

           self.logger.debug("VN: %s, expected ACE's is " % (vn))
           for r in rules_by_vn[vn]:
               self.logger.debug("%s" % (json.dumps(r, sort_keys=True)))
       # end building VN ACE's from user rules

       # Get actual from vna in compute nodes [referred as cn]
       vn_of_cn = scn.vn_of_cn  # {'cn1': ['vn1', 'vn2'], 'cn2': 'vn2'}
       cn_vna_rules_by_vn = {}  # {'vn1':[{...}, {..}], 'vn2': [{..}]}
       err_msg = {}  # To capture error {compute: {vn: error_msg}}
       for compNode in self.inputs.compute_ips:
           self.logger.debug("Compute node: %s, Check for expected data" % (
               compNode))
           inspect_h = self.agent_inspect[compNode]
           vnCn = (vn for vn in vn_of_cn[compNode] if vn_of_cn[compNode])
           for vn in vnCn:
               self.logger.debug("Checking for VN %s in Compute %s" % (
                   vn, compNode))
               vn_fq_name = inspect_h.get_vna_vn('default-domain', 
                       self.project_name, vn)['name']
               vna_acl = inspect_h.get_vna_acl_by_vn(vn_fq_name)
               if vna_acl:
                   # system_rules
                   cn_vna_rules_by_vn[vn] = vna_acl['entries']
               else:
                   cn_vna_rules_by_vn[vn] = []
               # compare with test input & assert on failure
               ret = policy_test_utils.compare_rules_list(rules_by_vn[vn],
                       cn_vna_rules_by_vn[vn], logger=self.logger)
               if ret:
                   result = ret['state']
                   msg = ret['msg']
                   err_msg[compNode] = {vn: msg}
                   self.logger.error("Compute node: %s, VN: %s, test result "\
                           "not expected, msg: %s" % (compNode, vn, msg))
                   self.logger.debug("Expected rules: ")
                   for r in rules_by_vn[vn]:
                       self.logger.debug(r)
                   self.logger.debug("Actual rules from system: ")
                   for r in cn_vna_rules_by_vn[vn]:
                       self.logger.debug(r)
               else:
                   self.logger.info("Compute node: %s, VN: %s, result of "\
                        "expected rules check passed" % (compNode, vn))
           self.logger.debug("Compute node: %s, Check for unexpected data" % (
                compNode))
           vn_not_of_cn = []
           skip_vn_not_of_cn = 0
           vn_not_of_cn = list(set(scn.vnet_list) - set(vn_of_cn[compNode]))
           if vn_not_of_cn == []:
               skip_vn_not_of_cn = 1
           for vn in vn_not_of_cn:
               if skip_vn_not_of_cn == 1:
                   break
               # VN & its rules should not be present in this Compute
               vn_exists = inspect_h.get_vna_vn('default-domain',
                       self.project_name, vn)
               if vn_exists:
                   vn_fq_name = vn_exists['name']
                   vna_acl = inspect_h.get_vna_acl_by_vn(vn_fq_name)
                   # system_rules
                   cn_vna_rules_by_vn[vn] = vna_acl['entries']
                   result = False
                   msg = "Compute node: " + str(compNode) + ", VN: " + \
                         str(vn) + " seeing unexpected rules in VNA" + \
                         str(cn_vna_rules_by_vn[vn])
                   err_msg[compNode] = {vn: msg}
               else:
                   self.logger.info("Compute node: %s, VN: %s, validated "\
                           "that no extra rules are present" % (compNode, vn))
       return {'result': result, 'msg': err_msg}

   def tx_policy_to_vn (self, rules, vn_policy_dict):
       """
       Return rules that have source and destination vn names in place of
       source and destination policy.
       """
       tx_rule_list = []
       src_pol = 'Null'
       dest_pol = 'Null'
       for rule in rules:
           if ((not 'source_policy' in rule) and (not 'dest_policy' in rule)):
               tx_rule_list.append(rule)
               continue
           if 'source_policy' in rule:
               src_pol = rule['source_policy']
           if 'dest_policy' in rule:
               dest_pol = rule['dest_policy']
           src_pol_vns = []
           dest_pol_vns= []
           for each_vn in vn_policy_dict:
               if src_pol in vn_policy_dict[each_vn]:
                   src_pol_vns.append(each_vn)
               if dest_pol in vn_policy_dict[each_vn]:
                   dest_pol_vns.append(each_vn)
           if (src_pol_vns and dest_pol_vns):
               for eachvn in src_pol_vns:
                   new_rule = copy.deepcopy(rule)
                   del new_rule['source_policy']
                   new_rule['source_network'] = eachvn
                   for eachvn2 in dest_pol_vns:
                       new_rule2 = copy.deepcopy(new_rule)
                       del new_rule2['dest_policy']
                       new_rule2['dest_network'] = eachvn2
                       tx_rule_list.append(new_rule)

           if (src_pol_vns and (not dest_pol_vns)):
               for eachvn in src_pol_vns:
                   new_rule = copy.deepcopy(rule)
                   del new_rule['source_policy']
                   new_rule['source_network'] = eachvn
                   tx_rule_list.append(new_rule)

           if (dest_pol_vns and (not src_pol_vns)):
               for eachvn in dest_pol_vns:
                   new_rule = copy.deepcopy(rule)
                   del new_rule['dest_policy']
                   new_rule['dest_network'] = eachvn
                   tx_rule_list.append(new_rule)
       return tx_rule_list

   def tx_user_def_rule_to_aces (self, test_vn, rules):
       """
       Return user defined rules to expected ACL entries, each rule as 
       dictionary, a
       list of dicts returned.
       1. translate keys rules-> ace
       2. translate 'any' value for port to range
       3. translate 'any' value for protocol to range
       4. expand bi-directional rules
       5. update 'action_l' as simple_action will not be used going forward
       """

       # step 1: key translation, update port/protocol values to system format
       translator = {
           'direction': 'direction', 'simple_action': 'simple_action',
           'protocol': 'proto_l', 'source_network': 'src', 'src_ports':
           'src_port_l', 'dest_network': 'dst', 'dst_ports': 'dst_port_l'}
       user_rules_tx = []
       configd_rules = len(user_rules_tx)
       for rule in rules:
           user_rule_tx = dict((translator[k], v) for (k, v) in rule.items())
           user_rules_tx.append(user_rule_tx)
       for rule in user_rules_tx:
           # port value mapping
           for port in ['src_port_l', 'dst_port_l']:
               if rule[port] == 'any':
                   rule[port] = {'max': '65535', 'min': '0'}
               else:  # only handling single or continuous range for port
                   if len(rule[port]) == 2:
                       rule[port] = {'max': str(rule[port][1]),
                                     'min': str(rule[port][0])}
                   else:
                       self.logger.error(
                           "user input port_list not handled by verification")
           # protocol value mapping
           if rule['proto_l'] == 'any':
               rule['proto_l'] = {'max': '255', 'min': '0'}
           else:
               rule['proto_l'] = {'max': str(rule['proto_l']),
                                  'min': str(rule['proto_l'])}

       # step 2: expanding rules if bidir rule
       final_rule_l = []
       for rule in user_rules_tx:
           if rule['direction'] == '<>':
               rule['direction'] = '>'
               pos = user_rules_tx.index(rule)
               new_rule = copy.deepcopy(rule)
               # update newly copied rule: swap address/ports & insert
               new_rule['src'], new_rule['dst'] = new_rule[
                   'dst'], new_rule['src']
               new_rule['src_port_l'], new_rule['dst_port_l'] = new_rule[
                   'dst_port_l'], new_rule['src_port_l'],
               user_rules_tx.insert(pos + 1, new_rule)

       # step 3: update action
       for rule in user_rules_tx:
           rule['action_l'] = [rule['simple_action']]
       return user_rules_tx

   def tx_user_def_aces_to_system (self, test_vn, user_rules_tx):
       '''convert ACEs derived from user rules to system format:
       1. For every user rule, add deny rule; skip adding duplicates
       2. For non-empty policy, add permit-all at the end
       3. add ace_id, rule_type
       4. Update VN to FQDN format
       5. remove direction and simple_action fields @end..
       '''
       if user_rules_tx == []:
           return user_rules_tx
       any_proto_port_rule = {
           'direction': '>', 'proto_l': {'max': '255', 'min': '0'},
           'src_port_l': {'max': '65535', 'min': '0'},
           'dst_port_l': {'max': '65535', 'min': '0'}}

       # step 0: check & build allow_all for local VN if rules are defined in
       # policy
       test_vn_allow_all_rule = copy.copy(any_proto_port_rule)
       test_vn_allow_all_rule['simple_action'] = 'pass'
       test_vn_allow_all_rule['action_l'] = ['pass']
       test_vn_allow_all_rule['src'], test_vn_allow_all_rule[
           'dst'] = test_vn, test_vn

       # check the rule for any protocol with same network exist and for deny
       # rule
       test_vn_deny_all_rule = copy.copy(any_proto_port_rule)
       test_vn_deny_all_rule['simple_action'] = 'deny'
       test_vn_deny_all_rule['action_l'] = ['deny']
       test_vn_deny_all_rule['src'], test_vn_deny_all_rule[
           'dst'] = test_vn, test_vn

       # step 1: check & add permit-all rule for same  VN  but not for 'any'
       # network
       last_rule = copy.copy(any_proto_port_rule)
       last_rule['simple_action'], last_rule['action_l'] = 'pass', ['pass']
       last_rule['src'], last_rule['dst'] = 'any', 'any'

       # check any rule exist in policy :
       final_user_rule = self.get_any_rule_if_exist(last_rule, user_rules_tx)

       # step 2: check & add deny_all for every user-created rule
       system_added_rules = []
       for rule in user_rules_tx:
           pos = len(user_rules_tx)
           new_rule = copy.deepcopy(rule)
           new_rule['proto_l'] = {'max': '255', 'min':
                                  '0'}
           new_rule['direction'] = '>'
           new_rule['src_port_l'], new_rule['dst_port_l'] = {
               'max': '65535', 'min': '0'}, {'max': '65535', 'min': '0'}
           new_rule['simple_action'] = 'deny'
           new_rule['action_l'] = ['deny']
           system_added_rules.append(new_rule)

       # step to check any one of the rule is any protocol and source and dst
       # ntw is test vn then check for the duplicate rules
       final_any_rules = self.get_any_rule_if_src_dst_same_ntw_exist(
           test_vn_allow_all_rule, test_vn_deny_all_rule, user_rules_tx)
       if final_any_rules:
           user_rules_tx = final_any_rules

       # Skip adding rules if they already exist...
       self.logger.debug( json.dumps(system_added_rules, sort_keys=True))
       if not policy_test_utils.check_rule_in_rules(test_vn_allow_all_rule,
               user_rules_tx):
           user_rules_tx.append(test_vn_allow_all_rule)
       for rule in system_added_rules:
           if not policy_test_utils.check_rule_in_rules(rule, user_rules_tx):
               user_rules_tx.append(rule)

       # step 3: check & add permit-all rule for same  VN  but not for 'any'
       # network
       last_rule = copy.copy(any_proto_port_rule)
       last_rule['simple_action'], last_rule['action_l'] = 'pass', ['pass']
       last_rule['src'], last_rule['dst'] = 'any', 'any'

       # if the first rule is not 'any rule ' then append the last rule
       # defined above.
       for rule in user_rules_tx:
           any_rule_flag = True
           if ((rule['src'] == 'any') and (rule['dst'] == 'any')):
               any_rule_flag = False
       if any_rule_flag:
           user_rules_tx.append(last_rule)

       # triming the duplicate rules
       user_rules_tx = policy_test_utils.remove_dup_rules(user_rules_tx)
       # triming the protocol with any option for rest of the fileds
       tcp_any_rule = {
           'proto_l': {'max': 'tcp', 'min': 'tcp'},
           'src': 'any', 'dst': 'any',
           'src_port_l': {'max': '65535', 'min': '0'},
           'dst_port_l': {'max': '65535', 'min': '0'}}
       udp_any_rule = {
           'proto_l': {'max': 'udp', 'min': 'udp'},
           'src': 'any', 'dst': 'any',
           'src_port_l': {'max': '65535', 'min': '0'},
           'dst_port_l': {'max': '65535', 'min': '0'}}
       icmp_any_rule = {
           'proto_l': {'max': 'icmp', 'min': 'icmp'},
           'src': 'any', 'dst': 'any',
           'src_port_l': {'max': '65535', 'min': '0'},
           'dst_port_l': {'max': '65535', 'min': '0'}}
       icmp_match, index_icmp = self.check_5tuple_in_rules(
           icmp_any_rule, user_rules_tx)
       tcp_match, index_tcp = self.check_5tuple_in_rules(
           tcp_any_rule, user_rules_tx)
       udp_match, index_udp = self.check_5tuple_in_rules(
           udp_any_rule, user_rules_tx)
       if icmp_match:
           for rule in user_rules_tx[index_icmp + 1:len(user_rules_tx)]:
               if rule['proto_l'] == {'max': 'icmp', 'min': 'icmp'}:
                   user_rules_tx.remove(rule)
       if tcp_match:
           for rule in user_rules_tx[index_tcp + 1:len(user_rules_tx)]:
               if rule['proto_l'] == {'max': 'tcp', 'min': 'tcp'}:
                   user_rules_tx.remove(rule)
       if udp_match:
           for rule in user_rules_tx[index_udp + 1:len(user_rules_tx)]:
               if rule['proto_l'] == {'max': 'udp', 'min': 'udp'}:
                   user_rules_tx.remove(rule)
       # if any rule is exist the it will execute
       if final_user_rule:
           user_rules_tx = final_user_rule
       # step 4: add ace_id, type, src to all rules
       for rule in user_rules_tx:
           rule['ace_id'] = str(user_rules_tx.index(rule) + 1)
           # currently checking policy aces only
           rule['rule_type'] = 'Terminal'
           if rule['src'] != 'any':
               m = re.match(r"(\S+):(\S+):(\S+)", rule['src'])
               if not m:
                   rule['src'] = ':'.join(
                       self.project_fq_name) + ':' + rule['src']
           if rule['dst'] != 'any':
               m = re.match(r"(\S+):(\S+):(\S+)", rule['dst'])
               if not m:
                   rule['dst'] = ':'.join(
                       self.project_fq_name) + ':' + rule['dst']
           try:
               del rule['direction']
           except:
               continue
           try:
               del rule['simple_action']
           except:
               continue
       return user_rules_tx

   def get_any_rule_if_exist (self, all_rule, user_rules_tx):
       final_rules = []
       if policy_test_utils.check_rule_in_rules(all_rule, user_rules_tx):
           for rule in user_rules_tx:
               if rule == all_rule:
                   final_rules.append(rule)
                   break
               else:
                   final_rules.append(rule)
       return final_rules

   def get_any_rule_if_src_dst_same_ntw_exist (self, test_vn_allow_all_rule,
           test_vn_deny_all_rule, user_rules_tx):
       final_any_rules = []
       if (policy_test_utils.check_rule_in_rules(test_vn_allow_all_rule,
           user_rules_tx) or policy_test_utils.check_rule_in_rules(
               test_vn_deny_all_rule, user_rules_tx)):
           for rule in user_rules_tx:
               if ((rule == test_vn_allow_all_rule) or 
                       (rule == test_vn_deny_all_rule)):
                   final_any_rules.append(rule)
                   break
               else:
                   final_any_rules.append(rule)
       return final_any_rules

   def check_5tuple_in_rules (self, rule, rules):
       '''check if 5-tuple of given rule exists in given rule-set..
       Return True if rule exists; else False'''

       match_keys = ['proto_l', 'src', 'dst', 'src_port_l', 'dst_port_l']
       for r in rules:
           match = True
           for k in match_keys:
               if r[k] != rule[k]:
                   match = False
                   break
           if match == True:
               break
       return (match, rules.index(r))
