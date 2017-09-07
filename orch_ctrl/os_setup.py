import os
import re
from fabric.context_managers import settings
from fabric.operations import sudo, put
from common import FlavorMgr, ImageMgr, RoundRobin
from api_drivers.openstack.driver import supported_types as os_arg_types
from api_drivers.vnc.driver import supported_types as vnc_arg_types

#TODO: logging

class OpenstackControl (object):
    ''' Single openstack-contrail cluster setup
    '''
    def __init__ (self, username, password,
                  project_name, project_id, domain_name, 
                  auth_ip, auth_url, authn_url,
                  api_server_ip, api_server_port, openstack_ip,
                  endpoint, region, scope,
                  cert, key, cacert, insecure, use_ssl,
                  lb_class, logger, inputs):
        self.inputs = inputs
        self._apis = {}
        self._select_api = ['vnc']
        self._select_lb = None
        self._user = username
        self._pass = password
        self._prjname = project_name
        self._dmnname = domain_name
        self._prjid = project_id
        self._auth_ip = auth_ip
        self._auth_url = auth_url
        self._authn_url = authn_url
        self._api_ip = api_server_ip
        self._api_port = api_server_port
        self._os_ip = openstack_ip
        self._endpoint = endpoint
        self._region = region
        self._scope = scope
        self._cert = cert
        self._key = key
        self._cacert = cacert
        self._insecure = insecure
        self._use_ssl = use_ssl
        self.logger = logger
        self._supported = {
            'orch': os_arg_types,
            'heat': [],
            'vnc': vnc_arg_types,
            'openstack': os_arg_types,
        }
        self._hijack = { # overides user selected api route
            'get_virtual_machine': 'openstack',
            'delete_virtual_machine': 'openstack',
        }
        self._flavor_mgr = FlavorMgr(self._install_flavor, logger)
        self._img_mgr = ImageMgr(self._install_image, logger)
        self._namespaces = ['qemu', 'docker']
        self._osapi = self.get_api('openstack')
        self._read_zones_and_nodes()
        self.select_api = 'orch' # api route selector
        self.select_lb = None if os.getenv('NO_LB', 0) else lb_class

    def _read_zones_and_nodes (self):
        zones = self._osapi.get_zones()
        self.zones = {}
        self.hosts = {}
        self.hypervisors = self._osapi.get_hypervisor()
        for z in zones:
            self.zones[z.zoneName] = {'hosts': list(z.hosts.keys())}
        for hypervisor in self.hypervisors:                                     
            self.hosts[hypervisor.hypervisor_hostname.split('.')[0]] = hypervisor
        
    def __getattr__ (self, fn):

        ''' Procedure to route api calls
            Attempt user selected api-route, if method not found
            fallback to vnc.
        '''

        if fn == '__repr__':
            return self
        if fn in self._hijack:
            return getattr(self.get_api(self._hijack[fn]), fn)
        api = self.get_api(self.select_api)
        try:
            return getattr(api, fn)
        except AttributeError:
            return getattr(self.get_api('vnc'), fn)

    @property
    def select_api (self):
        return self._select_api[0]

    @select_api.setter
    def select_api (self, api):
        assert api in self._supported, 'Unsupported api %s' % api
        self._select_api[0] = api

    def push_api (self, api):
        assert api in self._supported, 'Unsupported api %s' % api
        self._select_api.insert(0, api)

    def pop_api (self):
        self._select_api.pop(0)

    def get_supported_apis (self):
        return self._supported

    @property
    def select_lb (self):
        return self._select_lb

    @select_lb.setter
    def select_lb (self, cls):
        if cls is not None:
            cls.set_zones_and_hosts(self.zones, self.hosts)
        self._select_lb = cls

    def get_zones (self):
        return list(self.zones.keys())

    def get_hosts (self, zone=None):
        if zone:
            return list(self.zones[zone].keys())
        else:
            return list(self.hosts)

    def get_api (self, api):
        assert api in self._supported, 'Unsupported api %s' % api
        try:
            return self._apis[api]
        except KeyError:
            fn = getattr(self, '_get_' + api + '_api')
            self._apis[api] = fn()
            return self._apis[api]

    def _get_heat_api (self):
        from api_drivers.heat.driver import HeatDriver
        return HeatDriver(ks_h=self.get_api('openstack').keystone_handle,
                          cert=self._cert,
                          key=self._key,
                          cacert=self._cacert,
                          insecure=self._insecure,
                          logger=self.logger)

    def _get_vnc_api (self):
        from api_drivers.vnc.driver import VncDriver
        return VncDriver(username=self._user,
                         password=self._pass,
                         project_name=self._prjname,
                         project_id=self._prjid,
                         domain_name=self._dmnname,
                         server_ip=self._api_ip,
                         server_port=self._api_port,
                         auth_server_ip=self._auth_ip,
                         auth_url=self._authn_url,
                         use_ssl=self._use_ssl)

    def _get_openstack_api (self):
        from api_drivers.openstack.driver import OpenstackDriver
        return OpenstackDriver(username=self._user,
                               password=self._pass,
                               project_id=self._prjid,
                               project_name=self._prjname,
                               domain_name=self._dmnname,
                               auth_url=self._auth_url,
                               endpoint_type=self._endpoint,
                               region_name=self._region,
                               scope=self._scope,
                               cert=self._cert,
                               key=self._key,
                               cacert=self._cacert,
                               insecure=self._insecure,
                               logger=self.logger)

    def _get_orch_api (self):
        return self.get_api('openstack')

    def _pick_image (self, image):
        for ns in self._namespaces:
            try:
                img = self._img_mgr.get_image(ns, image)
                #TODO: add debug
                return img
            except NameError:
                pass
        raise Exception('Image %s not in %s' % (image, self._namespaces))

    def _pick_host_and_image (self, availability_zone, image):
        if not self.select_lb:
            return None, self._pick_image(image)

        zone = None
        host = None
        if availability_zone:
            zone = availability_zone.split(':')
            assert len(zone) <= 2, \
                'availability_zone must be specified as "zone:host" or "zone"'
            zone, host = zone if len(zone) == 2 else zone, None
            if not host:
                zone, host = self.select_lb.next(zone)
            ns = self.hosts[host].hypervisor_type.lower()
            image_obj = self._img_mgr.get_image(ns, image)
            #TODO add debug
            return zone + ':' + host, image_obj

        attempts = len(self.select_lb)
        while attempts:
            zone, host = self.select_lb.next()
            ns = self.hosts[host].hypervisor_type.lower()
            try:
                image_obj = self._img_mgr.get_image(ns, image)
                #TODO add debug
                return zone + ':' + host, image_obj
            except NameError:
                attempts -= 1

        raise Exception('Unable to find a host for %s in %s' % (image,
                        availability_zone))

    def create_virtual_machine (self, **kwargs):
        kwargs['flavor'] = self._flavor_mgr.get_flavor(kwargs['flavor'])
        zone, image = self._pick_host_and_image(
                        kwargs.get('availability_zone', None),
                        kwargs['image'])
        if zone:
            kwargs['availability_zone'] = zone
        kwargs['image'] = image
        return self.get_api('openstack').create_virtual_machine(**kwargs)

    def _execute_cmd_with_proxy (self, cmd):
        if self.inputs.http_proxy:
            with shell_env(http_proxy=self.inputs.http_proxy):
                sudo(cmd)
        else:
            sudo(cmd)

    def _install_flavor (self, name, **kwargs):
        ctx = self._osapi.get_flavor(name)
        if ctx:
            return ctx
        self.logger.debug('Adding flavor %s' % name)
        ctx = self._osapi.create_flavor(name=name, **kwargs)
        if self.inputs.dpdk_data:
            ctx.set_keys({'hw:mem_page_size': 'any'})
        return ctx

    def _install_image (self, ns, img_info, img_url):
        #TODO: check if docker requires special handling
        ctx = self._osapi.get_image(img_info['name'])
        if ctx:
            return ctx
        self.logger.debug('Installing image %s' % img_info['name'])
        username = self.inputs.host_data[self._os_ip]['username']
        password = self.inputs.host_data[self._os_ip]['password']
        with settings(host_string='%s@%s' % (username, self._os_ip),
                      password=password, warn_only=True,
                      abort_on_prompts=False):
            img_url = self._download_image(img_url)
            self._glance_image(img_url, img_info)
        return self._osapi.get_image(img_info['name'])

    def _download_image(self, image_url):

        ''' Get the image from build path - it download the image in case 
            of http[s]. In case of file:// url, copy it to the node.

            Args:
            image_url: Image url - it may be file:// or http:// url

            Returns: Local image filesystem absolute path
        '''

        if re.match(r'^file://', image_url):
            abs_path = re.sub('file://','',image_url)
            if not re.match(r'^/', abs_path):
                abs_path = '/' + abs_path
            if os.path.exists(abs_path):
                filename=os.path.basename(abs_path)
                put(abs_path, '/tmp/%s' % filename)
                return '/tmp/%s' % filename
        elif re.match(r'^(http|https)://', image_url):
            filename=os.path.basename(image_url)
            self._execute_cmd_with_proxy("wget %s -O /tmp/%s" % (image_url,
                                         filename))
            return '/tmp/%s' % filename

    def _glance_image (self, image_abs_path, image_info):
        if '.gz' in image_abs_path:
            self._execute_cmd_with_proxy('gunzip -f %s' % image_abs_path)
            image_path_real=image_abs_path.split('.gz')[0]
        else:
            image_path_real=image_abs_path

        if self.inputs.get_build_sku()[0] < 'l':
            public_arg = "--is-public True"
        else:
            public_arg = "--visibility public"

        insecure = '--insecure' if self._insecure else ''
        cmd = '(glance %s --os-username %s --os-password %s \
                --os-tenant-name %s --os-auth-url %s \
                --os-region-name %s image-create --name "%s" \
                %s %s --file %s)' % (insecure,
                                     self._user,
                                     self._pass,
                                     self._prjname,
                                     self._auth_url,
                                     self._region,
                                     image_info['name'],
                                     public_arg,
                                     image_info['glance'],
                                     image_path_real)
        self._execute_cmd_with_proxy(cmd)
        return True
