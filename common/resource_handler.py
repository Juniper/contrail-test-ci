import copy
from tcutils.util import get_random_name
from api_wraps.heat import parser
import vn_fix
import policy_fix
import vm_fix, vmi_fix, instip_fix
import svctmpl_fix, svcinst_fix, pt_fix

# Map: heat resource type -> fixture
_HEAT_2_FIXTURE = {
   'OS::ContrailV2::VirtualNetwork': vn_fix.VNFixture,
   'OS::ContrailV2::NetworkPolicy': policy_fix.PolicyFixture,
   'OS::ContrailV2::ServiceTemplate': svctmpl_fix.SvcTemplateFixture,
   'OS::ContrailV2::ServiceInstance': svcinst_fix.SvcInstanceFixture,
   'OS::ContrailV2::PortTuple': pt_fix.PortTupleFixture,
   'OS::ContrailV2::InstanceIp': instip_fix.InstanceIpFixture,
   'OS::ContrailV2::VirtualMachineInterface': vmi_fix.PortFixture,
   'OS::Nova::Server': vm_fix.VMFixture,
}

# Map: heat resource type -> fixture's transform method
#
# Transform function would be required in cases where non-contrailv2
# based forms have to supported. For example, if the resource definition
# used Openstack heat resource types, this function would convert the
# same to conform to contrailv2 resource definition.
#
# Method accepts argument extracted from heat template & env, and
# returns structure that can be passed to fixture's __init__ method
# param: str, specifies heat resource
# param: dict, specifies arguments extracted from template & env
#
_TRANSFORMS = {
   'OS::ContrailV2::VirtualNetwork': vn_fix.transform_args,
   'OS::ContrailV2::NetworkPolicy': policy_fix.transform_args,
   'OS::ContrailV2::VirtualMachineInterface': vmi_fix.transform_args,
   'OS::ContrailV2::InstanceIp': instip_fix.transform_args,
   'OS::ContrailV2::ServiceTemplate': svctmpl_fix.transform_args,
   'OS::ContrailV2::ServiceInstance': svcinst_fix.transform_args,
   'OS::ContrailV2::PortTuple': pt_fix.transform_args,
}

def _transform_args (res, args, objs):
   try:
       fn = _TRANSFORMS[res]
   except KeyError:
       fn = None
   return fn(res, copy.deepcopy(args), objs) if fn else args

def _create_via_heat (test, tmpl, params):

   ''' Create resources via heat and for each resource create appropriate
       fixture
       - for each resource in "resources" section an appropriate
         entry must be present in the "outputs" section of the template
       - code *CANNOT* handle cyclic dependency
       - to account for cyclic reference,
         i) build dependency table,
         ii) check & remove forward references
             forward references are those where resource holds reference to
             another resource that is to be created later
         iii) create resource and then update the reference
   '''

   parser.check_cyclic_dependency(tmpl)
   test.logger.debug("Creating resources via Heat")
   wrap = test.connections.get_orch_ctrl().get_api('heat')
   assert wrap, "Unable to obtain Heat api-wrap"

   tmpl_first = copy.deepcopy(tmpl)
   _, tbl = parser.build_dependency_tables(tmpl_first)
   refs = parser.report_fwd_refs(tbl, tmpl_first)
   tmpl_first, tmpl_to_update = parser.remove_fwd_refs(tmpl_first, refs)
   st = wrap.stack_create(get_random_name(), tmpl_first, params)
   objs = {'heat_wrap': wrap, 'stack': st}
   test.addCleanup(_delete_via_heat, objs)
   for out in st.outputs:
       key = out['output_key']
       res_id = out['output_value']
       try:
           res_name = tmpl_first['outputs'][key]['value']['get_attr'][0]
       except KeyError:
           res_name = tmpl_first['outputs'][key]['value']['get_resource']
       res_type = _HEAT_2_FIXTURE[tmpl_first['resources'][res_name]['type']]
       objs[res_name] = {'fixture' : test.useFixture(res_type(test.connections,
                                                              rid=res_id))}
   if tmpl_to_update:
       parser.fix_fwd_refs(objs, tmpl_to_update, refs)
       wrap.stack_update(st, tmpl_to_update, params, {})
       for res_name in refs:
           objs[res_name]['fixture'].update()
   return objs

def _delete_via_heat (objs):
   wrap = objs['heat_wrap']
   wrap.stack_delete(objs['stack'])

def _update_via_heat (test, objs, tmpl, params):

   ''' Update heat stack and refresh each resource's fixture
       procedure should be same as 'create' method
   '''

   parser.check_cyclic_dependency(tmpl)
   test.logger.debug("Updating resources via Heat")
   wrap = objs['heat_wrap']
   st = objs['stack']
   tmpl_first = copy.deepcopy(tmpl)
   _, tbl = parser.build_dependency_tables(tmpl_first)
   refs = parser.report_fwd_refs(tbl, tmpl_first)
   tmpl_first, tmpl_to_update = parser.remove_fwd_refs(tmpl_first, refs)
   st = wrap.stack_update(st, tmpl_first, params, {})
   for out in st.outputs:
       key = out['output_key']
       res_id = out['output_value']
       try:
           res_name = tmpl_first['outputs'][key]['value']['get_attr'][0]
       except KeyError:
           res_name = tmpl_first['outputs'][key]['value']['get_resource']
       res_type = _HEAT_2_FIXTURE[tmpl_first['resources'][res_name]['type']]
       if objs.get(res_name, None):
           objs[res_name]['fixture'].update()
       else:
           objs[res_name] = {
               'fixture' : test.useFixture(res_type(test.connections,
                                                    rid=res_id))
           }
   if tmpl_to_update:
       parser.fix_fwd_refs(objs, tmpl_to_update, refs)
       wrap.stack_update(st, tmpl_to_update, params, {})
       for res_name in refs:
           objs[res_name]['fixture'].update()
   return objs

def _create_via_fixture (test, tmpl, params):

   ''' Create resource via fixture
       - Heat template *MUST* explicilty call out dependency with the
         directive "depends_on"
       - Build a dependency table, which specifies the order in which the
         fixtures/resource must be initiated
       - Remove any forward references
       - Parse the heat template and derive arguments
       - Create resources using fixtures, in order given by dependency
         table
       - Update references with fixtures' update method
   '''

   parser.check_cyclic_dependency(tmpl)
   test.logger.debug("Creating resources via fixtures")
   objs = {'id-map': {}}
   tmpl_first = copy.deepcopy(tmpl)
   dep_tbl, res_tbl = parser.build_dependency_tables(tmpl)
   lvls = dep_tbl.keys()
   lvls.sort()
   refs = parser.report_fwd_refs(res_tbl, tmpl_first)
   tmpl_first, tmpl_to_update = parser.remove_fwd_refs(tmpl_first, refs)
   for i in lvls:
       for res_name in dep_tbl[i]:
           res_tmpl = tmpl_first['resources'][res_name]
           res_type = _HEAT_2_FIXTURE[res_tmpl['type']]
           args = parser.parse_resource(res_tmpl, params, objs)
           targs = _transform_args(res_tmpl['type'], args, objs)
           obj = test.useFixture(res_type(test.connections, params=targs))
           objs[res_name] = {'fixture' : obj, 'args' : args}
           objs['id-map'][obj.uuid] = obj
   if tmpl_to_update:
       parser.fix_fwd_refs(objs, tmpl_to_update, refs)
       for res_name in refs:
           res_tmpl = tmpl_to_update['resources'][res_name]
           args = parser.parse_resource(res_tmpl, params, objs)
           diff_args = _get_delta(objs[res_name]['args'], args)
           targs = _transform_args(res_tmpl['type'], diff_args, objs)
           objs[res_name]['fixture'].update(targs)
           objs[res_name]['args'].update(diff_args)
   return objs

def _update_via_fixture (test, objs, tmpl, params):

   ''' Update resource via fixture
       - Add new resources if any
       - Check for Update in existing resources
       - Delete resources no longer in template
   '''

   parser.check_cyclic_dependency(tmpl)
   test.logger.debug("Updating resources via fixtures")
   check_for_update = []
   tmpl_first = copy.deepcopy(tmpl)
   dep_tbl, res_tbl = parser.build_dependency_tables(tmpl)
   lvls = dep_tbl.keys()
   lvls.sort()
   refs = parser.report_fwd_refs(res_tbl, tmpl_first)
   tmpl_first, tmpl_to_update = parser.remove_fwd_refs(tmpl_first, refs)
   for i in lvls:
       for res_name in dep_tbl[i]:
           if res_name not in objs:
               res_tmpl = tmp_firstl['resources'][res_name]
               res_type = _HEAT_2_FIXTURE[res_tmpl['type']]
               args = parser.parse_resource(res_tmpl, params, objs)
               targs = _transform_args(res_tmpl['type'], args, objs)
               obj = test.useFixture(res_type(test.connections, params=targs))
               objs[res_name] = {'fixture' : obj, 'args' : args}
               objs['id-map'][obj.uuid] = obj
           else:
               check_for_update.append(res_name)

   if tmpl_to_update:
       parser.fix_fwd_refs(objs, tmpl_to_update, refs)

   check_for_update = list(set(check_for_update + refs.keys()))
   for res_name in check_for_update:
       res_tmpl = tmpl_to_update['resources'][res_name]
       args = parser.parse_resource(res_tmpl, params, objs)
       diff_args = _get_delta(objs[res_name]['args'], args)
       if diff_args:
           targs = _transform_args(res_tmpl['type'], diff_args, objs)
           objs[res_name]['fixture'].update(targs)
           objs[res_name]['args'].update(diff_args)

   for res_name in objs:
       if res_name not in tmpl['resources'] and res_name != 'id-map':
           objs[res_name]['fixture'].cleanUp()
           del objs[res_name]

   return objs

def create (test, tmpl, params):
   if test.testmode == 'heat':
       return _create_via_heat(test, tmpl, params)
   else:
       test.connections.get_orch_ctrl().select_api = test.testmode
       return _create_via_fixture(test, tmpl, params)

def update (test, objs, tmpl, params):
   if test.testmode == 'heat':
       return _update_via_heat(test, objs, tmpl, params)
   else:
       test.connections.get_orch_ctrl().select_api = test.testmode
       return _update_via_fixture(test, objs, tmpl, params)

def _diff_help (old, new):
   if len(old) != len(new):
       return new
   if type(new) == type([]):
       old_cp = copy.copy(old)
       new_cp = copy.copy(new)
       old_cp.sort()
       new_cp.sort()
       items = range(len(new))
   else:
       items = new.keys()
       old_cp = old
       new_cp = new
   for i in items:
       if type(new[i]) == type({}) or type(new[i]) == type([]):
           if _diff_help(old[i], new[i]):
               return new
       elif new[i] != old[i]:
           return new
   return None

def _get_delta (old, new):
   delta = {}
   for k in old:
       if k not in new:
           if type(old[k]) == type([]):
               delta[k] = []
           else:
               delta[k] = None
   for k in new:
       if k not in old:
           delta[k] = new[k]
       else:
           if type(new[k]) == type({}):
               diff = _diff_help(old[k], new[k])
           elif type(new[k]) == type([]):
               diff = _diff_help(old[k], new[k])
           else:
               diff = new[k] if new[k] != old[k] else None
           if diff:
               delta[k] = diff
   return delta
