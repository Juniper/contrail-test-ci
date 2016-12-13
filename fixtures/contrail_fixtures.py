import copy
import os
import fixtures

def _process_refs_to (val, objs):
   if ':' in val:
       return val.split(':')
   else:
       return objs['id-map'][val].fq_name

def process_refs (args, refs, objs):

   ''' Helper routine to handle refs, converts
       - [fqdn...] to [{"to":fqdn}...]
       - [fqdn...] + [ref-data...] to [{"to":fqdn, "attr":ref-data}...]
   '''

   new_args = copy.deepcopy(args)
   for ref in refs:
       try:
           lst = []
           del new_args[ref[0]]
           if len(ref) == 2:
               del new_args[ref[1]]
               for to, attr in zip(args[ref[0]], args[ref[1]]):
                   lst.append({'to': _process_refs_to(to, objs), 'attr': attr})
           else:
               for to in args[ref[0]]:
                   lst.append({'to': _process_refs_to(to, objs)})
           new_args[ref[0]] = lst
       except KeyError:
           pass
   return new_args

class ContrailFixture (fixtures.Fixture):

   ''' Base class for all fixtures. '''

   def __init__ (self, connections, uuid=None, params=None, fixs=None):
       self.fixs = fixs
       self.connections = connections
       self.inputs = connections.inputs
       self.logger = connections.logger
       self._ctrl = connections.get_orch_ctrl()
       self.type_name = self.vnc_class.resource_type
       self._setup_ref_fields()
       self._vnc = self._ctrl.get_api('vnc')
       if type(uuid) == type([]):
           self.uuid = self._vnc.fqn_to_id(self.type_name, uuid)
       else:
           self.uuid = uuid
       self._args_type = None
       self._vnc_obj = None
       self._obj = None
       self._owned = False if uuid else True
       self._args = self._handle_args(params)
       self._verify_on_cleanup = os.getenv('VERIFY_ON_CLEANUP') or False

   def _setup_ref_fields (self):
       self.ref_fields = []
       for ref in self.vnc_class.ref_fields:
           if self.vnc_class.ref_field_types[ref][1] != 'None':
               self.ref_fields.append((ref, ref + '_data'))
           else:
               self.ref_fields.append((ref,))

   def _handle_args (self, params):
       if not params:
           return None
       res_type = params['type']
       if 'OS::ContrailV2' in res_type and getattr(self, 'ref_fields', None):
           args = process_refs(params, self.ref_fields, self.fixs)
       else:
           args = params
       self._args_type = args['type']
       del args['type']
       return args

   def _update_args (self, params):
       self._args.update(params) #TODO: delete all entries set to None/[]/{}

   #@property
   #def uuid (self):
   #    return self._uuid or self._vnc_obj.uuid

   @property
   def vnc_obj (self):
       if not self._vnc_obj:
           self._read()
       return self._vnc_obj

   @property
   def args (self):
       return self._args or self._parse_args_from_vnc_obj()

   @property
   def name (self):
       return self.vnc_obj.name

   @property
   def fq_name (self):
       if not self._vnc_obj:
           return self._vnc.id_to_fqn(self.uuid)
       return self.vnc_obj.get_fq_name()

   @property
   def fq_name_str (self):
       if not self._vnc_obj:
           return ':'.join(self._vnc.id_to_fqn(self.uuid))
       return self.vnc_obj.get_fq_name_str()

   def setUp (self):
       super(ContrailFixture, self).setUp()
       if not self._owned:
           self._read()
       else:
           self._create()

   def cleanUp (self):
       super(ContrailFixture, self).cleanUp()
       if self._owned:
           self._delete()
       if self._verify_on_cleanup:
           self.verify_on_cleanup()

   def update (self, params=None):
       if not params:
           self._read()
       else:
           self._update_args(self._handle_args(params))
           self._update()

#TODO: check with contrail_fix_ext reqd?
def contrail_fix_ext(*dargs, **dkwargs):
    '''
        Must have methods = (verify_on_setup)
        or set verify=False explicitly

        verify function will be run only once unless force=True is set on call
        Example:

            @contrail_fix_ext ()
            class Foo (object):
                def __init__ (self):
                    pass
            ## <--- Fail

            @contrail_fix_ext (verify=False)
            class Foo (object):
                def __init__ (self):
                    pass
            ## <--- Setup will pass
    '''
    def inner(cls):
        cls._decorator_states = {
            'setup_done': False,
            'setup_verified': False,
            'obj_verified': False,
            'args': dargs,
            'kwargs': dkwargs,
        }
        cls_setup = cls.setUp

        def setup(self, *args, **kwargs):
            if not self._decorator_states['setup_done']:
                ret = cls_setup(self)
                self._decorator_states['setup_done'] = True
            if getattr(self._decorator_states['kwargs'],
                       'verify_on_setup', True):
                if not (self._decorator_states[
                        'setup_verified'] and not getattr(kwargs, 'force',
                                                          False)):
                    self.verify_on_setup()
                    self._decorator_states['setup_verified'] = True
            return ret
        if cls._decorator_states['kwargs'].get('verify_on_setup', True):
            for method in ('verify_on_setup', ):
                if not (method in dir(cls) and callable(getattr(
                        cls, method))):
                    raise NotImplementedError, 'class must implement %s' % method

        cls.setUp = setup
        return cls
    return inner

# def check_state():
#    print "in check_state "
#    def wrapper(function):
#        print "in wrapper function "
#        def s_wrapped(a,*args,**kwargs):
#            print "in wrapped function " + str(a) + str(args) + str(kwargs)
#            if not self.inputs.verify_state():
#                self.inputs.logger.warn( "Pre-Test validation failed.. Skipping test %s" %(function.__name__))
#            else :
#                return function(self,*args,**kwargs)
#        return s_wrapped
#    return wrapper
#
# def logger():
#    print "in main logger"
#    def log_wrapper(function):
#        print "In log wrapper function"
#        def l_wrapper(self, *args,**kwargs):
#            print "In log wrapped function"
#            self.inputs.logger.info('=' * 80)
#            self.inputs.logger.info('STARTING TEST : ' + function.__name__ )
# self.inputs.logger.info('END TEST : '+ function.__name__ )
# self.inputs.logger.info('-' * 80)
#            return function(self, *args, **kwargs)
#        return l_wrapper
#    return log_wrapper

# ContrailFixtureExtension end
