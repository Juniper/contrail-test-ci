#TODO: This module replaces fixtures/heat_test.py
import os
from tcutils.util import retry
try:
   from keystoneclient.v2_0 import client as ksc
   from heatclient import client as hc

   class HeatWrap:

       ''' Wrapper class for Heat Api.

           Provides methods for creation, updation and deletion of heat stacks
       '''

       def __init__ (self, username, password, project_name, auth_url,
                     server_ip, logger, server_port=8004, version=1):
           insecure = bool(os.getenv('OS_INSECURE', True))
           self.logger = logger
           self._ksc = ksc.Client(username=username, password=password,
                                  tenant_name=project_name, auth_url=auth_url,
                                  insecure=insecure)
           url = 'http://%s:%d/v%d/%s' % (server_ip, server_port, version,
                                          self._ksc.tenant_id)
           self._hc = hc.Client(version, url, token=self._ksc.auth_token)

       @retry(delay=5, tries=60)
       def _wait_on_stack (self, stack, action):
           complete = action + '_COMPLETE'
           failed = action + '_FAILED'
           stack.get()
           if stack.stack_status == failed:
               raise Exception('Heat:%s\n%s\n' % (stack.stack_status,
                                                  stack.stack_status_reason))
           return stack.stack_status == complete

       def _wait_for_completion (self, stack, action):
           if not self._wait_on_stack(stack, action):
               #TODO self.logger.debug() inspect resources state
               raise Exception('Heat Timeout')

       def stack_create (self, name, template, env):
           ret = self._hc.stacks.create(stack_name=name, template=template,
                                        environment=env)
           stack = self._hc.stacks.get(ret['stack']['id'])
           self._wait_for_completion(stack, 'CREATE')
           return stack

       def stack_update (self, stack, template, env, params):
           stack.update(template=template, environment=env, parameters=params)
           stack = self._hc.stacks.get(stack.id)
           self._wait_for_completion(stack, 'UPDATE')
           return stack

       def stack_delete (self, stack):
           stack.delete()
           stack = self._hc.stacks.get(stack.id)
           self._wait_for_completion(stack, 'DELETE')

except ImportError:
   pass
