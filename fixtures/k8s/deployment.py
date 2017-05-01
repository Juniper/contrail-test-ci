import fixtures
from vnc_api.vnc_api import NoIdError
from kubernetes.client.rest import ApiException

from common import log_orig as contrail_logging
from tcutils.util import get_random_name, retry


class DeploymentFixture(fixtures.Fixture):
    '''
    Create a deployment
    Refer https://github.com/kubernetes-incubator/client-python/blob/master/kubernetes/docs/AppsV1beta1Deployment.md
    '''

    def __init__(self,
                 connections,
                 namespace='default',
                 metadata={},
                 spec={}):
        self.logger = connections.logger or contrail_logging.getLogger(
            __name__)
        self.name = name or metadata.get('name') or get_random_name('deployment')
        self.namespace = namespace
        self.k8s_client = connections.k8s_client
        self.vnc_api_h = connections.vnc_lib
        self.metadata = metadata
        self.spec = spec
        self.v1_beta_h = self.k8s_client.v1_beta_h

        self.already_exists = None

    def setUp(self):
        super(DeploymentFixture, self).setUp()
        self.create()

    def verify_on_setup(self):
        if not self.verify_deployment_in_k8s():
            self.logger.error('Deployment %s verification in kubernetes failed'
                              % (self.name))
            return False
        self.logger.info('Deployment %s verification passed' % (self.name))
        return True
    # end verify_on_setup

    def cleanUp(self):
        super(DeploymentFixture, self).cleanUp()
        self.delete()

    def _populate_attr(self):
        self.uuid = self.obj.metadata.uid
        self.spec_obj = self.obj.spec
        self.metadata_obj = self.obj.metadata
    # end _populate_attr

    def read(self):
        try:
            self.obj = self.v1_beta_h.read_namespaced_deployment(
                self.name, self.namespace)
            self._populate_attr()
            if self.already_exists is None:
                self.already_exists = True
            return self.obj
        except ApiException as e:
            self.logger.debug('Deployment %s not present' % (self.name))
            return None
    # end read

    def create(self):
        deployment_exists = self.read()
        if deployment_exists:
            return deployment_exists
        self.already_exists = False
        self.obj = self.k8s_client.create_deployment(
            self.namespace,
            name=self.name,
            metadata=self.metadata,
            spec=self.spec)
        self.logger.info('Created Deployment %s' % (self.name))
        self._populate_attr()
    # end create

    def delete(self):
        if not self.already_exists:
            return self.k8s_client.delete_deployment(self.namespace, self.name)
    # end delete

    @retry(delay=3, tries=20)
    def verify_deployment_in_k8s(self):
        self.read()
        self.logger.info('Verifications in k8s passed for deployment %s' % (
                         self.name))
        return True
    # end verify_deployment_in_k8s
