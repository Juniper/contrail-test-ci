from fabric.api import local

import test
from tcutils.util import get_random_name, retry
from k8s.pod import PodFixture
from k8s.service import ServiceFixture
from k8s.ingress import IngressFixture
from k8s.namespace import NamespaceFixture
from k8s.network_policy import NetworkPolicyFixture
from common.connections import ContrailConnections
from common import create_public_vn
from common.base import _GenericTestBaseMethods


K8S_SERVICE_IPAM = ['default-domain', 'default', 'service-ipam']
K8S_PUBLIC_VN_NAME = '__public__'
K8S_PUBLIC_FIP_POOL_NAME = '__fip_pool_public__'

class BaseK8sTest(test.BaseTestCase, _GenericTestBaseMethods):

    @classmethod
    def setUpClass(cls):
        super(BaseK8sTest, cls).setUpClass()
        cls.connections = ContrailConnections(cls.inputs,
                              project_name=cls.inputs.admin_tenant,
                              username=cls.inputs.admin_username,
                              password=cls.inputs.admin_password,
                              logger=cls.logger)
        cls.vnc_lib_fixture = cls.connections.vnc_lib_fixture
        cls.vnc_lib = cls.connections.vnc_lib
        cls.agent_inspect = cls.connections.agent_inspect
        cls.cn_inspect = cls.connections.cn_inspect
        cls.analytics_obj = cls.connections.analytics_obj
        cls.api_s_inspect = cls.connections.api_server_inspect
        cls.logger = cls.connections.logger
        cls.k8s_client = cls.connections.k8s_client

#        cls.public_vn = create_public_vn.PublicVn(connections=cls.connections,
#                                 public_vn=K8S_PUBLIC_VN_NAME,
#                                 public_tenant=cls.inputs.admin_tenant,
#                                 logger=cls.logger,
#                                 fip_pool_name=K8S_PUBLIC_FIP_POOL_NAME,
#                                 api_option='contrail',
#                                 ipam_fq_name=K8S_SERVICE_IPAM)

    #end setUpClass

    @classmethod
    def tearDownClass(cls):
        super(BaseK8sTest, cls).tearDownClass()
    # end tearDownClass

    def setup_http_service(self,
                            name=None,
                            namespace='default',
                            app=None,
                            metadata=None,
                            spec=None,
                            frontend_port=80,
                            backend_port=80):
        '''
        A simple helper method to create a service

        Noticed that nginx continues to listen on port 80 even if target port
        is different. So, recommended not to change backend_port for now
        '''
        metadata = metadata or {}
        spec = spec or {}
        name = name or get_random_name('nginx-svc')
        metadata.update({'name' :  name})
        selector_dict = {}
        spec.update({
                         'ports' : [
                             {
                                 'protocol' : 'TCP',
                                 'port': int(frontend_port),
                                 'targetPort': int(backend_port)
                             }
                         ]
                       })
        if app:
            selector_dict = { 'selector': { 'app': app } }
            spec.update(selector_dict)

        return self.useFixture(ServiceFixture(
            connections=self.connections,
            name=name,
            namespace=namespace,
            metadata=metadata,
            spec=spec))
    # end setup_http_service

    def setup_simple_nginx_ingress(self,
                                   service_name,
                                   name=None,
                                   namespace='default',
                                   service_port=80):
        default_backend = {'service_name': service_name,
                           'service_port' : service_port}
        return self.setup_ingress(name=name,
                                  namespace=namespace,
                                  default_backend=default_backend)
    # end setup_simple_nginx_ingress


    def setup_ingress(self,
                      name=None,
                      namespace='default',
                      metadata={},
                      default_backend={},
                      rules=[],
                      spec={}):
        '''
        A very basic helper method to create an ingress

        '''
        name = name or get_random_name('nginx-ingress')
        metadata.update({'name' :  name})
        if default_backend:
            spec.update({'backend' : default_backend})
        if rules:
            spec.update({'rules' : rules})

        return self.useFixture(IngressFixture(
            connections=self.connections,
            name=name,
            namespace=namespace,
            metadata=metadata,
            spec=spec))
    # end setup_ingress

    def setup_namespace(self,
                         name=None):
        return self.useFixture(NamespaceFixture(
                                   connections=self.connections,
                                   name=name))
    # end create_namespace

    def setup_pod(self,
                  name=None,
                  namespace='default',
                  metadata=None,
                  spec=None,
                  labels=None):
        name = name or get_random_name('pod')
        metadata = metadata or {}
        spec = spec or {}
        labels = labels or {}
        metadata['name'] = metadata.get('name') or name
        if labels:
            metadata['labels'] = metadata.get('labels', {})
            metadata['labels'].update(labels)
        return self.useFixture(PodFixture(
                                   connections=self.connections,
                                   name=name,
                                   namespace=namespace,
                                   metadata=metadata,
                                   spec=spec))
    # end setup_pod

    def setup_nginx_pod(self,
                        name=None,
                        namespace='default',
                        metadata=None,
                        container_port=80,
                        labels=None,
                        spec=None):
        '''
        Noticed that nginx continues to listen on port 80 even if target port
        (container_port) is different
        '''
        metadata = metadata or {}
        spec = spec or {}
        labels = labels or {}
        name = name or get_random_name('nginx-pod')
        if labels:
            metadata['labels'] = metadata.get('labels', {})
            metadata['labels'].update(labels)
        spec = spec or {
                    'containers' : [
                        { 'image' : 'nginx',
                            'ports' : [
                                       {'container_port' : int(container_port)}
                                      ],
                        }
                    ]
              }
        return self.setup_pod(name=name,
                              namespace=namespace,
                              metadata=metadata,
                              spec=spec)
    # end setup_nginx_pod

    def setup_busybox_pod(self,
                        name=None,
                        namespace='default',
                        metadata=None,
                        spec=None,
                        labels=None):
        metadata = metadata or {}
        spec = spec or {}
        labels = labels or {}
        name = name or get_random_name('busybox-pod')
        spec = spec or {
                    'containers' : [
                        { 'image' : 'busybox',
                          'command' : ['sleep', '1000000'],
                          'image_pull_policy' : 'IfNotPresent',
                        }
                    ],
                    'restart_policy' : 'Always',
                }
        return self.setup_pod(name=name,
                              namespace=namespace,
                              metadata=metadata,
                              spec=spec,
                              labels=labels)
    # end setup_busybox_pod

    @retry(delay=1, tries=5)
    def validate_wget(self, pod, link, expectation=True, **kwargs):
        ret_val = self.do_wget(pod, link, **kwargs)
        return ret_val == expectation
    # end validate_wget

    def do_wget(self, pod, link, output_file='/dev/null', host='',
                timeout=5):
        host_str = ''
        if host:
            host_str = '--header "Host:%s" ' %(host)
        cmd = 'wget %s %s -O %s -T %s' % (link, host_str, output_file,
                                          timeout)
        output = pod.run_cmd(cmd, shell='/bin/sh -l -c')
        if '100%' in output:
            self.logger.info('[Pod %s] Cmd %s passed. Output :%s' %(pod.name,
                cmd, output))
            return True
        else:
            self.logger.info('[Pod %s] Cmd %s failed. Output :%s' %(pod.name,
                cmd, output))
            return False
    # end do_wget


    @retry(delay=1, tries=5)
    def validate_nginx_lb(self,
                          lb_pods,
                          service_ip,
                          test_pod=None,
                          path='',
                          host=None,
                          port=80):
        '''
        From test_pod , run wget on http://<service_ip>:<port> and check
        if the all the lb_pods respond to atleast one of the requests over
        3*len(lb_pods) attempts
        '''
        for pod in lb_pods:
            pod.run_cmd('echo %s > /usr/share/nginx/html/index.html' %(
                pod.name))
        attempts = len(lb_pods)*5
        hit = {}
        for x in lb_pods:
            hit[x.name] = 0

        if host:
            host_str = '--header "Host:%s" ' %(host)
        cmd = 'wget http://%s:%s/%s %s -O -' % (service_ip, port, path,
            host_str)
        for i in range(0, attempts):
            if test_pod:
                output = test_pod.run_cmd(cmd, shell='/bin/sh -l -c')
            else:
                output = local(cmd, capture=True)
            for pod in lb_pods:
                if pod.name in output:
                    hit[pod.name] += 1
            if 0 not in hit.values():
                self.logger.info('Responses seen from all pods, lb seems fine.'
                                 'Hits : %s' %(hit))
                return True
        if 0 in hit.values():
            msg = ('No http hit seen for one or more pods.'
                    'Pls check. Hits: %s' %(hit))
            self.logger.warn(msg)
            return False
        self.logger.info('Nginx lb hits seem to be ok: %s' %(hit))
        return True
    # end validate_nginx_lb

    def setup_simple_policy(self,
                            pod_selector=None,
                            name=None,
                            namespace='default',
                            metadata=None,
                            spec=None,
                            ingress_pods=None,
                            ingress_namespaces=None,
                            ports=None):
        '''
        A simple helper method to create a network policy with a single
        ingress entry
        Ex :
        ingress_pod : { 'role': 'frontend'}
        ingress_namespace : { 'project': 'mynamespace'}
        ports = ['tcp/80']

        '''
        metadata = metadata or {}
        spec = spec or {}
        ingress_pods = ingress_pods
        ingress_namespaces = ingress_namespaces
        ports = ports
        ingress_pod_selector = None
        ns_selector = None
        port_list = []
        name = name or get_random_name('np-')
        metadata.update({'name' :  name})
        selector_dict = {}
        pod_selector_dict = {}

        if pod_selector is not None:
            pod_selector_dict = { 'match_labels' : pod_selector }

        if ingress_pods is not None:
            ingress_pod_dict = {'match_labels': {}}
            for k,v in ingress_pods.iteritems():
                ingress_pod_dict['match_labels'].update({k:v})
            ingress_pod_selector = {'pod_selector': ingress_pod_dict}

        if ingress_namespaces is not None:
            ingress_ns_dict = {'match_labels': {}}
            for k,v in ingress_namespaces.iteritems():
                ingress_ns_dict['match_labels'].update({k:v})
            ns_selector = {'namespace_selector': ingress_ns_dict}

        if ports is not None:
            for port_str in ports:
                protocol, port = port_str.split('/')
                port_list.append({'protocol': protocol, 'port': port})

        spec.update({
            'ingress': [
                { 'from': [ ingress_pod_selector or ns_selector ],
                }
            ],
            'pod_selector': pod_selector_dict,
        })
        if ports is not None:
            spec['ingress'][0]['ports'] = port_list

        return self.useFixture(NetworkPolicyFixture(
            connections=self.connections,
            name=name,
            namespace=namespace,
            metadata=metadata,
            spec=spec))
    # end setup_simple_policy

    def update_simple_policy(self,
                            np_fixture,
                            pod_selector=None,
                            namespace='default',
                            metadata=None,
                            spec=None,
                            ingress_pods=None,
                            ingress_namespaces=None,
                            ports=None):
        '''
        TODO
        update of a policy does not work as of now
        https://github.com/kubernetes/kubernetes/issues/35911
        '''
        pass

    def setup_isolation(self, namespace_fixture):
        namespace_fixture.enable_isolation()
        self.addCleanup(namespace_fixture.disable_isolation)
    # end self.setup_isolation

