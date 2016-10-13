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

   def __init__ (self, rid=None, connections=None):
       self._id = rid
       self._connections = connections
       self._inputs = None
       self._logger = None
       self._vnc_obj = None
       self._verify_on_setup = os.getenv('VERIFY_ON_SETUP') or False
       self._verify_on_cleanup = os.getenv('VERIFY_ON_CLEANUP') or False
       if connections:
           self._ctrl = self._connections.get_orch_ctrl()
           self._vnc = self._ctrl.get_api('vnc')
           self._inputs = connections.inputs
           self._logger = connections.logger

   @property
   def uuid (self):
       return self._vnc_obj.uuid

   @property
   def name (self):
       return self._vnc_obj.name

   @property
   def fq_name (self):
       return self._vnc_obj.get_fq_name()

   @property
   def fq_name_str (self):
       return self._vnc_obj.get_fq_name_str()

   def setUp (self):
       super(ContrailFixture, self).setUp()
       if self._id:
           self._read(self._id)
       else:
           self._create()
       if self._verify_on_setup:
           self.verify_on_setup()

   def cleanUp (self):
       super(ContrailFixture, self).cleanUp()
       if not self._id:
           self._delete()
       if self._verify_on_cleanup:
           self.verify_on_cleanup()

   def update (self, params=None):
       if not params:
           self._read(self.uuid)
       else:
           self._update (params)
       if self._verify_on_setup:
           self.verify_on_setup()

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
