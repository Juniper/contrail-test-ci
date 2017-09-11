
from contrail_fixtures import ContrailFixture
from tcutils.util import retry
from vnc_api.vnc_api import VirtualDns, VirtualDnsType, VirtualDnsRecord

class VdnsFixture_v2(ContrailFixture):
    
    vnc_class = VirtualDns

    def __init__ (self, connections, uuid=None, params=None, fixs=None):
       super(VdnsFixture_v2, self).__init__(
           uuid=uuid,
           connections=connections,
           params=params,
           fixs=fixs)
       self.api_s_inspect = connections.api_server_inspect
       self.cn_inspect = connections.cn_inspect
       
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
        obj = self._vnc.get_virtual_DNS(self.uuid)
        found = 'not' if not obj else ''
        self.logger.debug('%s %s found in api-server' % (self, found))
        return obj != None, obj

    def _read (self):
        ret, obj = self._read_vnc_obj()
        if ret:
            self._vnc_obj = obj
        self._obj = self._vnc_obj

    def _create (self):
        self.logger.info('Creating %s' % self)
        self.uuid = self._ctrl.create_virtual_DNS(
            **self._args)

    def _delete (self):
        self.logger.info('Deleting %s' % self)
        self._ctrl.delete_virtual_DNS(
            obj=self._obj, uuid=self.uuid)

    def _update (self):
        self.logger.info('Updating %s' % self)
        self._ctrl.update_virtual_DNS(
            obj=self._obj, uuid=self.uuid, **self.args)
    
    def verify_on_setup (self):
       self.assert_on_setup(*self._verify_in_api_server())
       self.assert_on_setup(*self._verify_in_control_nodes())

    def verify_on_cleanup (self):
       self.assert_on_cleanup(*self._verify_not_in_api_server())
       self.assert_on_cleanup(*self._verify_not_in_control_nodes())
    
    @retry(delay=3, tries=15)
    def _verify_in_control_nodes(self):
        ''' verify VDNS data in control node'''
        for cn in self.inputs.bgp_ips:
            cn_s_dns = self.cn_inspect[cn].get_cn_vdns( vdns=str(self.name))
            if cn_s_dns == None:
                msg = "VDNS Server not found in Control node"
                self.logger.debug(msg)
                return False,msg
            if self.fq_name_str not in cn_s_dns['node_name']:
                msg = 'vdns name info not matching with control name data'
                self.logger.error(msg)
                return False, msg
            act_cn_vdns_data = cn_s_dns['obj_info']['data']['virtual-DNS-data']
            if not self._obj:
                self._read()
            exp_vdns_data = self._obj.get_virtual_DNS_data()
            if act_cn_vdns_data:
                if exp_vdns_data.__dict__['domain_name'] != \
                        act_cn_vdns_data['domain-name']:
                    msg = 'vdns domain name is not matching with control node data'
                    self.logger.error(msg)
                    raise NameError(msg)
                if str(exp_vdns_data.__dict__['default_ttl_seconds']) != \
                        act_cn_vdns_data['default-ttl-seconds']:
                    msg = 'vdns ttl value is not matching with control node data'
                    self.logger.error(msg)
                    raise NameError(msg)
                if exp_vdns_data.__dict__['record_order'] != \
                        act_cn_vdns_data['record-order']:
                    msg = 'vdns record order value is not matching with control node data'
                    self.logger.error(msg)
                    raise NameError(msg)
                if exp_vdns_data.__dict__['next_virtual_DNS'] != \
                        act_cn_vdns_data['next-virtual-DNS']:
                    msg = 'vdns next virtual DNS data is not matching with control node data'
                    self.logger.error(msg)
                    raise NameError(msg)
        msg = "Vdns server entry found in Control node"
        self.logger.debug(msg)
        return True, None
    # end _verify_in_control_nodes
    
    @retry(delay=3, tries=5)
    def _verify_in_api_server(self):
        ''' verify VDNS data in API server '''
        domain , name = self.fq_name
        api_s_dns = self.api_s_inspect.get_cs_dns(
            vdns_name=str(self.name), refresh=True)
        if api_s_dns == None:
            msg = "VDNS Server info not foundin API server"
            self.logger.debug(msg)
            return False, msg
        if self.fq_name != api_s_dns['virtual-DNS']['fq_name']:
            msg = ' fq name data is not matching with api server data'
            self.logger.error(msg)
            return False, msg
        if self.uuid != api_s_dns['virtual-DNS']['uuid']:
            msg = ' UUID is is not matching with api server data'
            self.logger.error(msg)
            return False, msg
        api_vdns_data = api_s_dns['virtual-DNS']['virtual_DNS_data']
        if not self._obj:
            self._read()
        exp_vdns_data = self._obj.get_virtual_DNS_data()
        for data in api_vdns_data:
            if str(exp_vdns_data.__dict__[data]) != str(api_vdns_data.get(data)):
                msg = 'vdns ' + data + ' is not matching with api server data'
                self.logger.error(msg)
                raise NameError(msg)
        msg = "Vdns server entry found in API server"
        self.logger.debug(msg)
        return True, msg
    # end _verify_in_api_server

    @retry(delay=2, tries=5)
    def _verify_not_in_api_server(self):
        """Validate VDNS information in API-Server."""
        if self.api_s_inspect.get_cs_dns(vdns_name=str(self.name), refresh=True) is not None:
            errmsg = "VDNS information %s still found in the API Server" % self.name
            self.logger.error(errmsg)
            return False, errmsg
        else:
            msg =  "VDNS information %s removed from the API Server" % self.name
            self.logger.debug(msg)
            return True, msg
    # end _verify_not_in_api_server

    @retry(delay=2, tries=25)
    def _verify_not_in_control_nodes(self):
        for cn in self.inputs.bgp_ips:
            cn_s_dns = self.cn_inspect[cn].get_cn_vdns(
                vdns=str(self.name))
            if cn_s_dns:
                errmsg = "VDNS information %s still found in the Control node" % self.name
                self.logger.info(errmsg)
                return False, errmsg
            else:
                msg = "VDNS information %s removed in the Control node" % self.name
                self.logger.debug(msg)
                return True, msg
    # end _verify_not_in_control_nodes

from tcutils.util import get_random_name
from vnc_api.vnc_api import VirtualDnsType
                            
class VdnsFixture (VdnsFixture_v2):

   ''' Fixture for backward compatiblity '''
   
   #TODO:
   def __init__ (self, connections, 
                  **kwargs):
       domain = connections.domain_name
       name = kwargs.get('vdns_name')
       self._api = kwargs.get('option', 'contrail')
       self.inputs = connections.inputs
       
       if name:
           uid = self._check_if_present(connections, name, [domain])
           if uid:
               super(VdnsFixture, self).__init__(connections=connections,
                                               uuid=uid)
               return
       else:
           name = get_random_name("vdns")
       self._construct_contrail_params(name, domain, kwargs)
       super(VdnsFixture, self).__init__(connections=connections,
                                       params=self._params)

   def _check_if_present (self, conn, vdns_name, domain):
       uid = domain + [vdns_name]
       obj = conn.get_orch_ctrl().get_api('vnc').get_virtual_DNS(uid)
       if not obj:
           return None
       return uid

   def setUp (self):
       super(VdnsFixture, self).setUp()

   def cleanUp (self):
       super(VdnsFixture, self).cleanUp()

   def _construct_contrail_params (self, name, domain, kwargs):
        self._params = {
            'type': 'OS::ContrailV2::VirtualDNS',
            'name' : name,
            'domain': domain
        }
        dns_data = kwargs.get('dns_data', None)
        if dns_data: 
            domain_name = dns_data.domain_name or 'juniper.net'
            default_ttl_seconds = dns_data.default_ttl_seconds or 100
            dynamic_records_from_client = dns_data.dynamic_records_from_client or True
            record_order = dns_data.record_order or 'random'
            next_virtual_DNS = dns_data.next_virtual_DNS or None
            floating_ip_record = dns_data.floating_ip_record or None
            external_visible = dns_data.external_visible or False
            reverse_resolution = dns_data.reverse_resolution or True
       
        self._params['virtual_DNS_data'] = {}
        self._params['virtual_DNS_data']['domain_name'] = domain_name
        self._params['virtual_DNS_data']['record_order'] = record_order
        self._params['virtual_DNS_data']['default_ttl_seconds'] = default_ttl_seconds
        self._params['virtual_DNS_data']['dynamic_records_from_client'] = \
                                                dynamic_records_from_client
        self._params['virtual_DNS_data']['external_visible'] = \
                                                external_visible
        self._params['virtual_DNS_data']['reverse_resolution'] = \
                                                reverse_resolution
        self._params['virtual_DNS_data']['floating_ip_record'] = \
                                                floating_ip_record
        self._params['virtual_DNS_data']['next_virtual_DNS'] = \
                                                next_virtual_DNS
class VdnsRecordFixture_v2(ContrailFixture):

    vnc_class = VirtualDnsRecord
    
    def __init__(self, connections, uuid=None, params=None, fixs=None):
        super(VdnsRecordFixture_v2, self).__init__(
           uuid=uuid,
           connections=connections,
           params=params,
           fixs=fixs)
        self.api_s_inspect = connections.api_server_inspect
        self.cn_inspect = connections.cn_inspect

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
        obj = self._vnc.get_virtual_DNS_record(self.uuid)
        found = 'not' if not obj else ''
        self.logger.debug('%s %s found in api-server' % (self, found))
        return obj != None, obj

    def _read (self):
        ret, obj = self._read_vnc_obj()
        if ret:
            self._vnc_obj = obj
        self._obj = self._vnc_obj

    def _create (self):
        self.logger.info('Creating %s' % self)
        self.uuid = self._ctrl.create_virtual_DNS_record(
            **self._args)

    def _delete (self):
        self.logger.info('Deleting %s' % self)
        self._ctrl.delete_virtual_DNS_record(
            obj=self._obj, uuid=self.uuid)

    def _update (self):
        self.logger.info('Updating %s' % self)
        self._ctrl.update_virtual_DNS_record(
            obj=self._obj, uuid=self.uuid, **self.args)
    
    def verify_on_setup (self):
        self.assert_on_setup(*self._verify_in_api_server())
        self.assert_on_setup(*self._verify_in_control_nodes())

    def verify_on_cleanup (self):
        self.assert_on_cleanup(*self._verify_not_in_api_server())
        self.assert_on_cleanup(*self._verify_not_in_control_nodes())

    @retry(delay=5, tries=5)
    def _verify_in_control_nodes(self):
        ''' verify VDNS record data in API in Control node'''
        result = True
        for cn in self.inputs.bgp_ips:
            try:
                cn_s_dns = self.cn_inspect[cn].get_cn_vdns_rec(
                    vdns=self._args['virtual_DNS'].split(":")[-1],
                    rec_name=self.name)
            except TypeError:
                msg = "No record found inside the specified VDNS server"
                return False, msg
            if cn_s_dns == None:
                msg = "No record entry found in API server"
                return False, msg
            if self.fq_name_str not in cn_s_dns['node_name']:
                msg = 'vdns name info not matching with control name data'
                self.logger.error(msg)
                return False, msg
            act_cn_vdns_rec_data = cn_s_dns['obj_info'][
                    'data']['virtual-DNS-record-data']
            if not self._obj:
                self._read()
            exp_vdns_rec_data = self._obj.get_virtual_DNS_record_data()
            if act_cn_vdns_rec_data:
                if exp_vdns_rec_data.__dict__['record_name'] != act_cn_vdns_rec_data['record-name']:
                    msg = 'vdns record name is not matching with control node data'
                    self.logger.error(msg)
                    raise NameError(msg)
                if str(exp_vdns_rec_data.__dict__['record_ttl_seconds']) != act_cn_vdns_rec_data['record-ttl-seconds']:
                    msg = 'vdns record ttl value is not matching with control node data'
                    self.logger.error(msg)
                    raise NameError(msg)
                if exp_vdns_rec_data.__dict__['record_type'] != act_cn_vdns_rec_data['record-type']:
                    msg = 'vdns record type value is not matching with control node data'
                    self.logger.error(msg)
                    raise NameError(msg)
                if exp_vdns_rec_data.__dict__['record_data'] != act_cn_vdns_rec_data['record-data']:
                    msg = 'vdns record data is not matching with control node data'
                    self.logger.error(msg)
                    raise NameError(msg)
        msg = "VDNS record info is matching with control node data"
        self.logger.debug(msg)
        return True, None
    # end of  _verify_in_control_nodes

    @retry(delay=5, tries=5)
    def _verify_in_api_server(self):
        ''' verify VDNS record data in API server '''
        result = True
        try: 
            api_s_dns_rec = self.api_s_inspect.get_cs_dns_rec( rec_name=self.name, 
                vdns_name=self._args['virtual_DNS'].split(":")[-1], refresh=True)
        except TypeError:
            msg = "No record found inside the specified VDNS server"
            return False, msg
        if api_s_dns_rec == None:
            msg = "No record entry found in API server"
            return False, msg
        if self.fq_name != api_s_dns_rec['virtual-DNS-record']['fq_name']:
            msg = ' fq name data is not matching with DNS record data'
            self.logger.error(msg)
            return False, msg
        if self.uuid != api_s_dns_rec['virtual-DNS-record']['uuid']:
            msg = ' UUID is is not matching with DNS record data'
            self.logger.error(msg)
            return False, msg
        api_vdns_rec_data = api_s_dns_rec[
                'virtual-DNS-record']['virtual_DNS_record_data']
        if not self._obj:
            self._read()
        exp_vdns_rec_data = self._obj.get_virtual_DNS_record_data()
        for data in api_vdns_rec_data:
            if str(exp_vdns_rec_data.__dict__[data]) != str(api_vdns_rec_data.get(data)):
                msg = 'vdns ' + data + ' is not matching with api server DNS record data'
                self.logger.error(msg)
                raise NameError(msg)
        msg = "VDNS record info is matching with API Server data"
        self.logger.debug(msg)
        return True, None
    # end of _verify_in_api_server

    @retry(delay=2, tries=5)
    def _verify_not_in_api_server(self):
        '''Validate VDNS record data not  in API-Server.'''
        if self.api_s_inspect.get_cs_dns_rec(rec_name=self.name, 
                                            vdns_name=self._args['virtual_DNS'].split(":")[-1],
                                            refresh=True) is not None:
            errmsg = "VDNS record information %s still found in the API Server" % self.name
            self.logger.error(errmsg)
            return False, errmsg
        else:
            msg = "VDNS record information %s removed from the API Server" % self.vdns_record_name
            self.logger.debug(msg)
            return True, msg

    @retry(delay=2, tries=5)
    def _verify_not_in_control_server(self):
        for cn in self.inputs.bgp_ips:
            cn_s_dns = self.cn_inspect[cn].get_cn_vdns_rec(
                            vdns=self._args['virtual_DNS'].split(":")[-1],
                            rec_name=self.name)
            if cn_s_dns:
                errmsg = "VDNS record information %s still found in the Control node" \
                        % self.vdns_record_name
                self.logger.error(errmsg)
                return False, errmsg
            else:
                msg = "VDNS record information %s removed in the Control node" \
                        % self.vdns_record_name
                self.logger.debug(msg)
                return True, msg


from vnc_api.vnc_api import VirtualDnsRecordType

class VdnsRecordFixture(VdnsRecordFixture_v2):

    ''' Fixture for backward compatiblity '''
   
   #TODO:
    def __init__ (self, connections, 
                  vdns_fq_name,
                  virtual_DNS_record_data,
                 **kwargs):
        dns_record_data = virtual_DNS_record_data
        name = kwargs.get('virtual_DNS_record_name', None)
        domain = vdns_fq_name
        self._api = kwargs.get('option', 'contrail')
        self.inputs = connections.inputs
        if name:
            uid = self._check_if_present(connections, name, [domain])
            if uid:
                super(VdnsRecordFixture, self).__init__(connections=connections,
                                               uuid=uid)
                return
        else:
            name = get_random_name("vdnsRecord")
        self._construct_contrail_params(name, domain, dns_record_data, kwargs)
        super(VdnsRecordFixture, self).__init__(connections=connections,
                                       params=self._params)

    def _check_if_present (self, conn, vdns_record_name, domain):
        uid = domain + [vdns_record_name]
        obj = conn.get_orch_ctrl().get_api('vnc').get_virtual_DNS(uid)
        if not obj:
            return None
        return uid

    def setUp (self):
        super(VdnsRecordFixture, self).setUp()

    def cleanUp (self):
        super(VdnsRecordFixture, self).cleanUp()

    def _construct_contrail_params (self, name, domain, dns_record_data, kwargs):
        self._params = {
            'type': 'OS::ContrailV2::VirtualDnsRecord',
            'name' : name,
            'virtual_DNS': domain
        }
        
        
        record_name = dns_record_data.record_name 
        record_type = dns_record_data.record_type 
        record_class = dns_record_data.record_class 
        record_data = dns_record_data.record_data 
        record_ttl_seconds = dns_record_data.record_ttl_seconds 

        self._params['virtual_DNS_record_data'] = {}
        self._params['virtual_DNS_record_data']['record_name'] = record_name
        self._params['virtual_DNS_record_data']['record_type'] = record_type
        self._params['virtual_DNS_record_data']['record_class'] = record_class
        self._params['virtual_DNS_record_data']['record_data'] = record_data
        self._params['virtual_DNS_record_data']['record_ttl_seconds'] = \
                    record_ttl_seconds
