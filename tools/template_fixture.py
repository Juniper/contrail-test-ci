#!/bin/python

import string
import argparse

orch_read_fn = string.Template(
'''
   @retry(delay=1, tries=5)
   def _read_orch_obj (self):
       obj = self._ctrl.get_$__object_type__(self.uuid)
       found = 'not' if not obj else ''
       self.logger.debug('%s %s found in orchestrator' % (self, found))
       return obj != None, obj
''')

orch_read_call = (
'''       ret, obj = self._read_orch_obj()
       if ret:
           self._obj = obj''')

orch_read_nocall = (
'''       self._obj = self._vnc_obj''')

orch_verify_fns = string.Template(
'''
   def _verify_in_orch (self):
       if not self._read_orch_obj()[0]:
           return False, '%s not found in orchestrator' % self
       return True, None

   @retry(delay=5, tries=6)
   def _verify_not_in_orch (self):
       if self._ctrl.get_$__object_type__(self.uuid):
           msg = '%s not removed from orchestrator' % self
           self.logger.debug(msg)
           return False, msg
       self.logger.debug('%s removed from orchestrator' % self)
       return True, None
''')

verify_in_orch_call = (
'''       self.assert_on_setup(*self._verify_in_orch())''')

verify_not_in_orch_call = (
'''       self.assert_on_cleanup(*self._verify_not_in_orch())''')

base = string.Template(
'''from contrail_fixtures import ContrailFixture
from tcutils.util import retry
from vnc_api.vnc_api import $__vnc_class__

class $__fixture__ (ContrailFixture):

   vnc_class = $__vnc_class__

   def __init__ (self, connections, uuid=None, params=None, fixs=None):
       super($__fixture__, self).__init__(
           uuid=uuid,
           connections=connections,
           params=params,
           fixs=fixs)
       # Note: Add type specific initialization

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
       obj = self._vnc.get_$__object_type__(self.uuid)
       found = 'not' if not obj else ''
       self.logger.debug('%s %s found in api-server' % (self, found))
       return obj != None, obj
$__orch_read_fn__
   def _read (self):
       ret, obj = self._read_vnc_obj()
       if ret:
           self._vnc_obj = obj
$__orch_read_call__

   def _create (self):
       self.logger.info('Creating %s' % self)
       self.uuid = self._ctrl.create_$__object_type__(
           **self._args)

   def _delete (self):
       self.logger.info('Deleting %s' % self)
       self._ctrl.delete_$__object_type__(
           obj=self._obj, uuid=self.uuid)

   def _update (self):
       self.logger.info('Updating %s' % self)
       self._ctrl.update_$__object_type__(
           obj=self._obj, uuid=self.uuid, **self.args)

   def verify_on_setup (self):
       self.assert_on_setup(*self._verify_in_api_server())
$__verify_in_orch__
       #TODO: check if more verification is needed

   def verify_on_cleanup (self):
       self.assert_on_cleanup(*self._verify_not_in_api_server())
$__verify_not_in_orch__
       #TODO: check if more verification is needed

   def _verify_in_api_server (self):
       if not self._read_vnc_obj()[0]:
           return False, '%s not found in api-server' % self
       return True, None

   @retry(delay=5, tries=6)
   def _verify_not_in_api_server (self):
       if self._vnc.get_$__object_type__(self.uuid):
           msg = '%s not removed from api-server' % self
           self.logger.debug(msg)
           return False, msg
       self.logger.debug('%s removed from api-server' % self)
       return True, None
$__orch_verify_fns__''')

ap = argparse.ArgumentParser(description='Generate fixture boilerplate code')
ap.add_argument('--vnc-class', type=str, required=True,
   help='vnc resource class [see vnc_api/gen/resource_common.py]')
ap.add_argument('--object-type', type=str, required=True,
   help='object_type for resource class [see vnc_api/gen/resource_common.py]')
ap.add_argument('--orch-api', action='store_true', default=False,
   help='True if Orchestrator has API for this resource')
ap.add_argument('--fixture', type=str, required=True,
   help='Name of fixture class')
ap.add_argument('--file', type=str,  required=True, help='output file')
args =  ap.parse_args()

params = {
   '__vnc_class__': args.vnc_class,
   '__fixture__': args.fixture,
   '__object_type__': args.object_type,
}

if args.orch_api:
   orch = {
       '__orch_read_fn__': orch_read_fn.substitute(params),
       '__orch_read_call__': orch_read_call,
       '__verify_in_orch__': verify_in_orch_call,
       '__verify_not_in_orch__': verify_not_in_orch_call,
       '__orch_verify_fns__': orch_verify_fns.substitute(params)
   }
else:
   orch = {
       '__orch_read_fn__': '',
       '__orch_read_call__': orch_read_nocall,
       '__verify_in_orch__': '',
       '__verify_not_in_orch__': '',
       '__orch_verify_fns__': '',
   }
params.update(orch)

code = base.substitute(params)
fh = open(args.file, 'w')
fh.write(code)
fh.close()
print 'Code written to %s' % args.file
