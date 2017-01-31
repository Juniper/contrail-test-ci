import fixtures
from kubernetes.client.rest import ApiException

from common import log_orig as contrail_logging
from tcutils.util import get_random_name, retry

class NamespaceFixture(fixtures.Fixture):
    '''
    '''
    def __init__(self, connections, name=None):
        self.logger = connections.logger or contrail_logging.getLogger(__name__)
        self.name = name or get_random_name('namespace')
        self.k8s_client = connections.k8s_client

        self.already_exists = False

    def setUp(self):
        super(NamespaceFixture, self).setUp()    
        self.create()

    def verify_on_setup()
        if not self.verify_namespace_is_active():
            self.logger.error('Namespace %s verification failed', %(
                               self.name))
            return False
        if not self.verify_namespace_in_contrail_api():
            self.logger.error('Namespace %s not seen in Contrail API' %(
                               self.name))
            return False
        self.logger.info('Namespace %s verification passed' % (self.name))
        return True
    # end verify_on_setup 


    @retry(delay=1, tries=10)
    def verify_namespace_is_active(self):
        if self.status != 'Active':
            self.logger.warn('Namespace %s is not Active yet, It is %s' %(
                             self.name, self.status))
            return False
        return True
    # end verify_namespace_is_active

    @retry(delay=1, tries=10)
    def verify_namespace_in_contrail_api(self):
        try:
            self.vnc_api_h.read_project(id=self.uuid)
        except NoIdError:
            self.logger.warn('Namespace %s UUID %s not in contrail-api-server' %(
                             self.name, self.uuid))
            return False
        self.logger.info('Namespace %s is seen in contrail-api' % (self.name))
        return True
    # end verify_namespace_in_contrail_api

    def cleanUp(self):
        super(NamespaceFixture, self).cleanUp()
        self.delete()

    def _populate_attr(self):
        self.uuid = self.obj.metadata.uid
        self.status = self.obj.status.phase

    def read(self):
        try:
            self.obj = self.k8s_client.read_namespace(self.name)
            self._populate_attr()
            self.already_exists = True
        except ApiException as e:
            self.logger.debug('Namespace %s not present' % (self.name))
            return None 
    # end read

    def create(self):
        ns_exists = self.read()
        if ns_exists:
            return ns_exists
        self.obj = self.k8s_client.create_namespace(self.name)
        self._populate_attr() 
    # end create

    def delete(self):
        if not self.already_exists:
            return self.k8s_client.delete_namespace(self.name)
    # end delete

