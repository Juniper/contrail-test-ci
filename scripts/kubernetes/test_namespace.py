
import test
from fixtures.k8s.namespace import Namespace
from tcutils.wrappers import preposttest_wrapper

class TestNamespace(test.BaseTestCase):

    @classmethod
    def setUpClass(cls):
        super(TestNamespace, cls).setUpClass()

    @classmethod
    def tearDownClass(cls):
        super(TestNamespace, cls).tearDownClass()

    @preposttest_wrapper
    def test_namespace_1(self):
        ''' Create and delete a namespace 
        '''
        namespace = self.useFixture(Namespace(self.connections))
        assert namespace.verify_on_setup()

    # end test_namespace_1
        

