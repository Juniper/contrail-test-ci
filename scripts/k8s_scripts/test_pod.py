
from common.k8s.base import BaseK8sTest
from k8s.pod import PodFixture
from tcutils.wrappers import preposttest_wrapper

class TestPod(BaseK8sTest):

    @classmethod
    def setUpClass(cls):
        super(TestPod, cls).setUpClass()

    @classmethod
    def tearDownClass(cls):
        super(TestPod, cls).tearDownClass()

    @preposttest_wrapper
    def test_add_delete_pod(self):
        ''' 
        Test POD add delete
        '''
        pod  = self.useFixture(PodFixture(self.connections))
        assert pod.verify_on_setup()
    # end test_add_delete_pod

    @preposttest_wrapper
    def test_ping_between_two_pod(self):
        '''
        Test ping between 2 POD
        '''
        pod1  = self.useFixture(PodFixture(self.connections))
        assert pod1.verify_on_setup()
        pod2  = self.useFixture(PodFixture(self.connections))
        assert pod2.verify_on_setup()
        assert pod1.ping_to_ip(pod2.pod_ip)
    # end test_add_delete_pod
        

