# Note: This file contains template test code for reference
# TODO: copy & rename this file for use in testing

import test_v1
from tcutils.wrappers import preposttest_wrapper
from tcutils.util import get_random_name, get_random_cidr, get_random_cidrs
from common import resource_handler
from common.base import GenericTestBase

# define heat template for the resources
tmpl = {}
# define parameters for the resource template
env = {}

class Tests (test_v1.BaseTestCase_v1):

   ''' Base class is collection of portable tests which can be run on any and
       all orchestrator setup
   '''

   @classmethod
   def setUpClass (cls):
       super(Tests, cls).setUpClass()

   @classmethod
   def tearDownClass (cls):
       super(Tests, cls).tearDownClass()

   @preposttest_wrapper
   def test1 (self):
       objs = resource_handler.create(self, tmpl, env)
       resource_handler.verify_on_setup(objs)
       # update tmpl and/or env as appropriate
       # objs = resource_handler.update(self, objs, tmpl, env)
       # resource_handler.verify_on_setup(objs)
       return True

class TestwithHeat (Tests):

   ''' Runs the tests through heat api
   '''

   @classmethod
   def setUpClass(cls):
       super(TestwithHeat, cls).setUpClass()
       cls.testmode = 'heat'

class TestwithVnc (Tests):

   ''' Runs the tests through vnc api
   '''

   @classmethod
   def setUpClass (cls):
       super(TestwithVnc, cls).setUpClass()
       cls.testmode = 'vnc'

class TestwithOrch (Tests):

   ''' Runs the tests through appropriate orchestrator api
       would be openstack, vcenter, etc
   '''

   @classmethod
   def setUpClass (cls):
       super(TestwithOrch, cls).setUpClass()
       cls.testmode = 'orch'

class TestOldStyle (GenericTestBase):

   ''' Collection of tests written in older style
   '''

   @classmethod
   def setUpClass (cls):
       super(TestOldStyle, cls).setUpClass()
       cls.testmode = 'vnc'

   @classmethod
   def tearDownClass(cls):
       super(TestOldStyle, cls).tearDownClass()

   @preposttest_wrapper
   def test1 (self):
       #TODO: add code which follows the older style
       #      see policy_test.py
       return True
