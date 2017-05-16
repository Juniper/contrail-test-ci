#!/bin/python

import string
import argparse

orch_read_fn = string.Template(
'''
   @retry(delay=1, tries=5)
   def _read_orch_obj (self):
       with self._api_ctx:
           obj = self._ctrl.get_$__object_type__(self.uuid)
       return obj != None, obj
''')

orch_read_call = (
'''       ret, obj = self._read_orch_obj()
       if ret:
           self._obj = obj''')

orch_read_nocall = (
'''       self._obj = self._vnc_obj''')

base = string.Template(
'''from contrail_fixtures import ContrailFixture
from tcutils.util import retry
from vnc_api.vnc_api import $__vnc_class__

class $__fixturev2__ (ContrailFixture):

   vnc_class = $__vnc_class__

   def __init__ (self, connections, uuid=None, params=None, fixs=None):
       super($__fixturev2__, self).__init__(
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
       return obj != None, obj
$__orch_read_fn__
   def _read (self):
       ret, obj = self._read_vnc_obj()
       if ret:
           self._vnc_obj = obj
$__orch_read_call__

   def _create (self):
       self.logger.info('Creating %s' % self)
       with self._api_ctx:
           self.uuid = self._ctrl.create_$__object_type__(
               **self._args)

   def _delete (self):
       self.logger.info('Deleting %s' % self)
       with self._api_ctx:
           self._ctrl.delete_$__object_type__(
               obj=self._obj, uuid=self.uuid)

   def _update (self):
       self.logger.info('Updating %s' % self)
       with self._api_ctx:
           self._ctrl.update_$__object_type__(
               obj=self._obj, uuid=self.uuid, **self.args)

   def verify_on_setup (self):
       #TODO: add verification code
       pass

   def verify_on_cleanup (self):
       #TODO: add verification code
       pass

from tcutils.util import get_random_name

class $__fixture__ ($__fixturev2__):

   """ Fixture for backward compatiblity """

   def __init__ (self, connections, **kwargs):
       #TODO: add init
       domain = connections.domain_name
       prj = kwargs.get('project_name') or connections.project_name
       prj_fqn = domain + ':' + prj
       name = None #TODO: kwargs.get()

       if name:
           uid = self._check_if_present(connections, name, [domain, prj])
           if uid:
               super($__fixture__, self).__init__(connections=connections,
                                           uuid=uid)
               return
       else:
           name = get_random_name(prj)

       self._params = {}
       super($__fixture__, self).__init__(
               connections=connections, params=self._params)

   def _check_if_present (self, conn, name, prj_fqn):
       uid = prj_fqn + [name]
       obj = conn.get_orch_ctrl().get_api('vnc').get_$__object_type__(uid)
       if not obj:
           return None
       return uid

   def setUp (self):
       super($__fixture__, self).setUp()
       self.vnc_api = self._vnc._vnc # direct handle to vnc library
       #TODO: placeholder for additional code, if not required
       #      delete this method

   def cleanUp (self):
       super($__fixture__, self).cleanUp()
       #TODO: placeholder for additional code, if not required
       #      delete this method
''')

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
   '__fixturev2__': args.fixture + '_v2',
   '__object_type__': args.object_type,
}

if args.orch_api:
   orch = {
       '__orch_read_fn__': orch_read_fn.substitute(params),
       '__orch_read_call__': orch_read_call,
   }
else:
   orch = {
       '__orch_read_fn__': '',
       '__orch_read_call__': orch_read_nocall,
   }
params.update(orch)

code = base.substitute(params)
fh = open(args.file, 'w')
fh.write(code)
fh.close()
print 'Code written to %s' % args.file
