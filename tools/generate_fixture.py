#!/bin/python

import string
import argparse

fixture_code = string.Template(
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
   def _read (self):
       self._vnc_obj = self._vnc.get_$__object_type__(self.uuid)
       # Note:
       # option-1: if resource object can be read/created/deleted through
       #           non-contrail api, then read resource object through
       #           orchestrator control
       # option-2: retain the vnc object
       # Example, service-instance can be read/created/deleted only
       #          through contrail-api. Thus option-2 is applicable.
       #          floatin-ip can be read/created/deleted through openstack
       #          apis. Thus option-1 is applicable 
       # 1. self._obj = self._ctrl.get_$__object_type__(self.uuid)
       # 2. self._obj = self._vnc_obj
       # !!! Remove this comment section !!!
       return self._vnc_obj and self._obj

   def _create (self):
       self.logger.debug('Creating %s' % self)
       self.uuid = self._ctrl.create_$__object_type__(
           **self._args)

   def _delete (self):
       self.logger.debug('Deleting %s' % self)
       self._ctrl.delete_$__object_type__(
           obj=self._obj, uuid=self.uuid)

   def _update (self):
       self.logger.debug('Updating %s' % self)
       self._ctrl.update_$__object_type__(
           obj=self._obj, uuid=self.uuid, **self.args)

   def verify_on_setup (self):
       assert self.vnc_obj, '%s not found' % self
       #TODO: check if more verification is needed

   def verify_on_cleanup (self):
       ret, err = self._verify_not_in_api_server()
       assert ret, err
       #TODO: check if more verification is needed

   @retry(delay=5, tries=6)
   def _verify_not_in_api_server (self):
       if self._vnc.get_$__object_type__(self.uuid):
           return False, '%s not removed' % self
       return True, None
''')

ap = argparse.ArgumentParser(description='Generate fixture boilerplate code')
ap.add_argument('--vnc-class', type=str, required=True,
   help='vnc resource class [see vnc_api/gen/resource_common.py]')
ap.add_argument('--object-type', type=str, required=True,
   help='object_type for resource class [see vnc_api/gen/resource_common.py]')
ap.add_argument('--fixture', type=str, required=True, help='fixture name')
ap.add_argument('--file', type=str,  required=True, help='output file')
args =  ap.parse_args()

params = {
   '__vnc_class__': args.vnc_class,
   '__fixture__': args.fixture,
   '__object_type__': args.object_type,
}

code = fixture_code.substitute(params)
fh = open(args.file, 'w')
fh.write(code)
fh.close()
print 'Code written to %s' % args.file
