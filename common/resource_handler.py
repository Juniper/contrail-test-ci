import os
import copy
from tcutils.util import get_random_name
from api_wraps.heat import parser
import vn_fix
import policy_fix
import vm_fix, vmi_fix
from instance_ip_fixture import InstanceIpFixture
from svc_template_fixture import SvcTemplateFixture
from svc_instance_fixture import SvcInstanceFixture
from port_tuple_fixture import PortTupleFixture

# Map: heat resource type -> fixture
_HEAT_2_FIXTURE = {
   'OS::ContrailV2::VirtualNetwork': vn_fix.VNFixture,
   'OS::ContrailV2::NetworkPolicy': policy_fix.PolicyFixture,
   'OS::ContrailV2::ServiceTemplate': SvcTemplateFixture,
   'OS::ContrailV2::ServiceInstance': SvcInstanceFixture,
   'OS::ContrailV2::PortTuple': PortTupleFixture,
   'OS::ContrailV2::InstanceIp': InstanceIpFixture,
   'OS::ContrailV2::VirtualMachineInterface': vmi_fix.PortFixture,
   'OS::Nova::Server': vm_fix.VMFixture,
}

def verify_on_setup (objs):
   for res in objs['fixtures']:
       objs['fixtures'][res].verify_on_setup()

def verify_on_cleanup (objs):
   for res in objs['fixtures']:
       objs['fixtures'][res].verify_on_cleanup()

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
   objs = {'heat_wrap': wrap, 'stack': st,
           'fixture_cleanup': test.connections.inputs.fixture_cleanup,
           'fixtures': {}, 'id-map': {}, 'fqn-map': {}}
   test.addCleanup(_delete_via_heat, objs)
   for out in st.outputs:
       key = out['output_key']
       res_id = out['output_value']
       try:
           res_name = tmpl_first['outputs'][key]['value']['get_attr'][0]
       except KeyError:
           res_name = tmpl_first['outputs'][key]['value']['get_resource']
       res_type = _HEAT_2_FIXTURE[tmpl_first['resources'][res_name]['type']]
       test.logger.debug('Reading %s - %s' % (res_name,
             tmpl_first['resources'][res_name]['properties'].get('name', None)))
       obj = test.useFixture(res_type(test.connections, uuid=res_id, fixs=objs))
       objs['fixtures'][res_name] = obj
       objs['id-map'][obj.uuid] = obj
       objs['fqn-map'][obj.fq_name_str] = obj
   if tmpl_to_update:
       parser.fix_fwd_refs(objs, tmpl_to_update, refs)
       wrap.stack_update(st, tmpl_to_update, params, {})
       for res_name in refs:
           test.logger.debug('Updating %s' % res_name)
           objs['fixtures'][res_name].update()
   return objs

def _delete_via_heat (objs):
   if objs['fixture_cleanup'] == 'no':
       return
   wrap = objs['heat_wrap']
   wrap.stack_delete(objs['stack'])
   if os.getenv('VERIFY_ON_CLEANUP'):
       verify_on_cleanup(objs)

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
       if objs['fixtures'].get(res_name, None):
           test.logger.debug('Updating %s' % res_name)
           objs['fixtures'][res_name].update()
       else:
           test.logger.debug('Reading %s - %s' % (res_name,
               tmpl_first['resources'][res_name]['properties'].get('name',
                                                                   None)))
           obj = test.useFixture(res_type(test.connections, uuid=res_id,
                                          fixs=objs))
           objs['fixtures'][res_name] = obj
           objs['id-map'][obj.uuid] = obj
           objs['fqn-map'][obj.fq_name_str] = obj
   if tmpl_to_update:
       parser.fix_fwd_refs(objs, tmpl_to_update, refs)
       wrap.stack_update(st, tmpl_to_update, params, {})
       for res_name in refs:
           test.logger.debug('Updating %s' % res_name)
           objs['fixtures'][res_name].update()
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
   objs = {'fixtures': {}, 'args': {}, 'id-map': {}, 'fqn-map': {}}
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
           obj = test.useFixture(res_type(test.connections, params=args,
                                          fixs=objs))
           objs['fixtures'][res_name] = obj
           objs['args'][res_name] = args
           objs['id-map'][obj.uuid] = obj
           objs['fqn-map'][obj.fq_name_str] = obj
   if tmpl_to_update:
       parser.fix_fwd_refs(objs, tmpl_to_update, refs)
       for res_name in refs:
           res_tmpl = tmpl_to_update['resources'][res_name]
           args = parser.parse_resource(res_tmpl, params, objs)
           diff_args = _get_delta(objs['args'][res_name], args)
           objs['fixtures'][res_name].update(args)
           objs['args'][res_name].update(diff_args)
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
           if res_name not in objs['fixtures']:
               res_tmpl = tmpl_first['resources'][res_name]
               res_type = _HEAT_2_FIXTURE[res_tmpl['type']]
               args = parser.parse_resource(res_tmpl, params, objs)
               obj = test.useFixture(res_type(test.connections, params=args,
                                              fixs=objs))
               objs['fixtures'][res_name] = obj
               objs['args'][res_name] = args
               objs['id-map'][obj.uuid] = obj
               objs['fqn-map'][obj.fq_name_str] = obj
           else:
               check_for_update.append(res_name)

   if tmpl_to_update:
       parser.fix_fwd_refs(objs, tmpl_to_update, refs)

   check_for_update = list(set(check_for_update + refs.keys()))
   for res_name in check_for_update:
       res_tmpl = tmpl_to_update['resources'][res_name]
       args = parser.parse_resource(res_tmpl, params, objs)
       diff_args = _get_delta(objs['args'][res_name], args)
       if diff_args:
           args['type'] = res_tmpl['type']
           objs['fixtures'][res_name].update(args)
           objs['args'][res_name].update(diff_args)

   #for res_name in objs['fixtures']:
   #    if res_name not in tmpl['resources']:
   #        objs['fixtures'][res_name].cleanUp()
   #        del objs['fixtures'][res_name]
   return objs

def create (test, tmpl, params):
   if test.testmode == 'heat':
       objs =  _create_via_heat(test, tmpl, params)
   else:
       test.connections.get_orch_ctrl().select_api = test.testmode
       objs = _create_via_fixture(test, tmpl, params)
   test.objs = objs
   return test.objs

def update (test, objs, tmpl, params):
   if test.testmode == 'heat':
       objs = _update_via_heat(test, objs, tmpl, params)
   else:
       test.connections.get_orch_ctrl().select_api = test.testmode
       objs = _update_via_fixture(test, objs, tmpl, params)
   test.objs = objs
   return test.objs

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
