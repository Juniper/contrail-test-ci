import copy

def build_dependency_tables (tmpl):

   ''' Dependency-Table groups resources into dependency levels.
       i.e. resources at level 'L' are dependent on resources at
       level 'L-1'.
       Dependency-Level table specifies the dependency level for
       each resource.
   '''

   def dep_lvl (k):
       try:
           return lvls[k]
       except KeyError:
           deps = tmpl['resources'][k].get('depends_on', None)
           if not deps:
               lvls[k] = 0
           else:
               lvls[k] = max([dep_lvl(d) for d in deps]) + 1
           return lvls[k]

   lvls = {}
   tbl = {}
   for res_name in tmpl['resources']:
       l = dep_lvl(res_name)
       if tbl.get(l, None):
           tbl[l].append(res_name)
       else:
           tbl[l] = [res_name]
   return tbl, lvls

def check_cyclic_dependency (tmpl):

   ''' Detect cyclic dependency and report.
       Uses "depends_on" heat directive to construct dependency.
   '''

   def _report (res):
       while in_process[0] != res:
           in_process.pop(0)
       assert False, 'Cyclic dependency %s' % in_process

   def _visit (res):
       if res in in_process:
           _report(res)
       in_process.append(res)
       for deps in tmpl['resources'][res].get('depends_on', []):
           if deps not in processed:
               _visit(deps)
       in_process.pop(-1)
       processed.append(res)

   processed = []
   in_process = []
   for res in tmpl['resources']:
       if res not in processed:
           _visit(res)

def _parse_get_param (tmpl, params, objs):
   if not params:
       return tmpl
   param_name = tmpl['get_param']
   return params['parameters'][param_name]

def _parse_get_attr (tmpl, params, objs):
   res_name = tmpl['get_attr'][0]
   attr = tmpl['get_attr'][1:]
   return objs[res_name]['fixture'].get_attr(attr)

def _parse_get_resource (tmpl, params, objs):
   res_name = tmpl['get_resource']
   return objs[res_name]['fixture'].get_resource()

def _parse_list_join (tmpl, params, objs):
   delim = tmpl['list_join'][0]
   subfn = tmpl['list_join'][1].keys()[0]
   subfn_tmpl = tmpl['list_join'][1]
   val = _heat_fn(subfn, subfn_tmpl, params, objs)
   return delim.join(val) if type(val) == type([]) else val

def _parse_str_split (tmpl, params, objs):
   delim = tmpl['str_split'][0]
   subfn = tmpl['str_split'][1].keys()[0]
   subfn_tmpl = tmpl['str_split'][1]
   val = _heat_fn(subfn, subfn_tmpl, params, objs)
   if type(val) != type(''):
       return val
   val = val.split(delim)
   if len(tmpl['str_split']) == 3:
       return val[tmpl['str_split'][2]]
   else:
       return val

_HEAT_FNS = {
   'get_attr': _parse_get_attr,
   'get_param': _parse_get_param,
   'get_resource': _parse_get_resource,
   'list_join': _parse_list_join,
   'str_split': _parse_str_split,
   #'repeat': _parse_repeat, TODO
   #'digest': _parse_digest, TODO
   #'str_replace': _parse_str_replace, TODO
   #'map_merge': _parse_map_merge, TODO
   #'map_replace': _parse_map_replace, TODO
   #'equals': _parse_equals, TODO
   #'if': _parse_if, TODO
   #'not': _parse_not, TODO
   #'and': _parse_and, TODO
   #'or': _parse_or, TODO
}

def _heat_fn (name, tmpl, params, obj):
   try:
       fn = _HEAT_FNS[name]
   except KeyError:
       assert False, 'Unimplemented heat function %s' % name
   return fn(tmpl, params, obj)

def _parse_dict (name, tmpl, params, objs):
   if tmpl.keys()[0] in _HEAT_FNS.keys():
      return _heat_fn(tmpl.keys()[0], tmpl, params, objs)

   ret = {}
   for attr, attr_tmpl in tmpl.items():
       stripped = attr.split(name + '_')[-1]
       if type(attr_tmpl) == type({}):
           args = _parse_dict(attr, attr_tmpl, params, objs)
       elif type(attr_tmpl) == type([]):
           args = _parse_list(attr, attr_tmpl, params, objs)
       else:
           args = attr_tmpl
       ret[stripped] = args
   return ret

def _parse_list (name, tmpl, params, objs):
   ret = []
   for entry in tmpl:
       refs = None
       if type(entry) == type({}):
           item = _parse_dict(name, entry, params, objs)
       elif type(entry) == type([]):
           item = _parse_list(name, entry, params, objs)
       else:
           item = entry
       if item != None:
          ret.append(item)
   return ret

def _parse_resource (tmpl, params, objs):
   args = {}
   for prop, prop_tmpl in tmpl.items():
       refs = None
       if type(prop_tmpl) == type({}):
           val = _parse_dict(prop, prop_tmpl, params, objs)
       elif type(prop_tmpl) == type([]):
           val = _parse_list(prop, prop_tmpl, params, objs)
       else:
           val = prop_tmpl
       args[prop] = val
   return args

def parse_resource (tmpl, params, objs):
   return _parse_resource(tmpl['properties'], params, objs)

def _get_dependency_from_dict (desc):
   ret = []
   for k,v in desc.items():
       if k == 'get_resource':
           ret.append(v)
       elif k == 'get_attr':
           ret.append(v[0])
       elif type(v) == type({}):
           ret.extend(_get_dependency_from_dict(v))
       elif type(v) == type([]):
           ret.extend(_get_dependency_from_list(v))
   return ret

def _get_dependency_from_list (desc):
   ret = []
   for item in desc:
       if type(item) == type({}):
           ret.extend(_get_dependency_from_dict(item))
       elif type(item) == type([]):
           ret.extend(_get_dependency_from_list(item))
   return ret

def report_fwd_refs (lvls, tmpl):

   ''' Report forward references.
       Heat uses "get_resource" and "get_attr" directives to establish
       references between resources.
       A forward reference is a reference to a resource, which is at
       a higher dependecy level i.e, resource comes later in the
       creation order.
   '''

   fwd_refs = {}
   for res,res_tmpl in tmpl['resources'].items():
       refs = set(_get_dependency_from_dict(res_tmpl['properties']))
       fwd_refs[res] = []
       for r in refs:
           if lvls[r] >= lvls[res]:
               fwd_refs[res].append(r)
   for res in tmpl['resources']:
       if fwd_refs[res] == []:
           del fwd_refs[res]
   return fwd_refs

def _clear_refs_in_policy (tmpl, refs):
   keys = tmpl.keys()
   for k in keys:
       if k != 'name':
           del tmpl[k]
   return tmpl

_TMPL_FN = {
   'OS::ContrailV2::NetworkPolicy': _clear_refs_in_policy,
}

def remove_fwd_refs (tmpl, refs):

   ''' Remove forward references.
       TODO: Challenge: make this routine resource agnostic
   '''

   tmpl_update = copy.deepcopy(tmpl)
   modified = False
   for res, deps in refs.items():
       res_type = tmpl['resources'][res]['type']
       if deps:
           try:
               fn = _TMPL_FN[res_type]
           except KeyError:
               assert False, 'Unhandled resource type %s' % res_type
           fn(tmpl['resources'][res]['properties'], deps)
           modified = True
   return (tmpl, tmpl_update) if modified else (tmpl, None)

def _fix_refs_in_dict (tmpl, objs):
   if tmpl.keys()[0] in _HEAT_FNS.keys():
       return _heat_fn(tmpl.keys()[0], tmpl, None, objs)

   for attr, attr_tmpl in tmpl.items():
       if type(attr_tmpl) == type({}):
           tmpl[attr] = _fix_refs_in_dict(attr_tmpl, objs)
       elif type(attr_tmpl) == type([]):
           tmpl[attr] = _fix_refs_in_list(attr_tmpl, objs)
   return tmpl

def _fix_refs_in_list (tmpl, objs):
   lst = []
   for entry in tmpl:
       if type(entry) == type({}):
           item = _fix_refs_in_dict(entry, objs)
       elif type(entry) == type([]):
           item = _fix_refs_in_list(entry, objs)
       lst.append(item)
   return lst

def fix_fwd_refs (topo, tmpl, refs):

   ''' Resolve forward references.
       This function is called between first-pass (resource creation), and
       second-pass (resource updation).
   '''

   for res in refs:
       props = tmpl['resources'][res]['properties']
       for prop, prop_tmpl in props.items():
           if type(prop_tmpl) == type({}):
               props[prop] = _fix_refs_in_dict(prop_tmpl, topo)
           elif type(prop_tmpl) == type([]):
               props[prop] = _fix_refs_in_list(prop_tmpl, topo)
