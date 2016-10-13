import os
from tcutils.util import retry
try:
   from keystoneclient.v2_0 import client as ksc
   from heatclient import client as hc

   _VERSION = '1'
   _HEAT_PORT = '8004'

   class HeatWrap ():

       def __init__ (self, **kwargs):
           ver = kwargs.get('version', _VERSION)
           self._log = kwargs['logger']
           insecure = bool(os.getenv('OS_INSECURE', True))
           self._ksc = ksc.Client(username=kwargs['username'],
                                  password=kwargs['password'],
                                  tenant_name=kwargs['project_name'],
                                  auth_url=kwargs['auth_url'],
                                  insecure=insecure)
           url = 'http://%s:%s/v%s/%s' % (kwargs['server_ip'],
                                          kwargs.get('server_port', _HEAT_PORT),
                                          ver, self._ksc.tenant_id)
           self._log.debug('Connecting to heat %s' % url)
           self._hc = hc.Client(ver, url, token=self._ksc.auth_token)

       @retry(delay=5, tries=60)
       def _wait_on_stack (self, stack, action):
           complete = action + '_COMPLETE'
           failed = action + '_FAILED'
           stack.get()
           self._log.debug('Stack:%s Status:%s' % (stack.stack_name,
                                                   stack.stack_status))
           assert stack.stack_status != failed
           return stack.stack_status == complete

       def _wait_for_completion (self, *args):
           assert self._wait_on_stack(*args), \
               'Stack update is taking a lot of time'

       def stack_create (self, name, template, env):
           self._log.info('Creating Stack:%s' % name)
           ret = self._hc.stacks.create(stack_name=name, template=template,
                                        environment=env)
           stack = self._hc.stacks.get(ret['stack']['id'])
           self._wait_for_completion(stack, 'CREATE')
           return stack

       def stack_update (self, stack, template, env, params):
           self._log.info('Updating Stack:%s' % stack.stack_name)
           stack.update(template=template, environment=env, parameters=params)
           stack = self._hc.stacks.get(stack.id)
           self._wait_for_completion(stack, 'UPDATE')
           return stack

       def stack_delete (self, stack):
           self._log.info('Deleting Stack:%s' % stack.stack_name)
           stack.delete()
           stack = self._hc.stacks.get(stack.id)
           self._wait_for_completion(stack, 'DELETE')
except ImportError:
   pass
