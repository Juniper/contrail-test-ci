
from contrail_fixtures import ContrailFixture
from tcutils.util import retry
from vnc_api.vnc_api import VirtualDns, VirtualDnsType, VirtualDnsRecord

from vnc_api.gen.resource_test import VirtualDnsRecordTestFixtureGen

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
            try:
                cn_s_dns = self.cn_inspect[cn].get_cn_vdns( vdns=str(self.name))
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
                        return False, msg
                    if str(exp_vdns_data.__dict__['default_ttl_seconds']) != \
                            act_cn_vdns_data['default-ttl-seconds']:
                        msg = 'vdns ttl value is not matching with control node data'
                        self.logger.error(msg)
                        return False, msg
                    if exp_vdns_data.__dict__['record_order'] != \
                            act_cn_vdns_data['record-order']:
                        msg = 'vdns record order value is not matching with control node data'
                        self.logger.error(msg)
                        return False, msg
                    if exp_vdns_data.__dict__['next_virtual_DNS'] != \
                            act_cn_vdns_data['next-virtual-DNS']:
                        msg = 'vdns next virtual DNS data is not matching with control node data'
                        self.logger.error(msg)
                        return False, msg
            except Exception as e:
                # Return false if we get an key error and for retry
                msg = "Exception happened"
                return False, msg
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
        try:
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
                    return False, msg
        except Exception as e:
            # Return false if we get an key error and for retry
            msg = "Exception happened"
            return False
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
   
   @property
   def vdns_fq_name (self):
       return self.fq_name_str

   @property
   def vdns_name (self):
       return self.name

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
           'domain': domain,
       }
       dns_domain_name = kwargs.get('dns_domain_name', 'juniper.net')
       ttl = kwargs.get('ttl',100)
       record_order = kwargs.get('record_order', 'random')
       dynamic_records_from_client = kwargs.get('dynamic_records_from_client', True)
       
       self._params['virtual_dns_data'] = {}
       self._params['virtual_dns_data']['domain_name'] = dns_domain_name
       self._params['virtual_dns_data']['record_order'] = record_order
       self._params['virtual_dns_data']['default_ttl_seconds'] = ttl
       self._params['virtual_dns_data']['dynamic_records_from_client'] = \
                    dynamic_records_from_client


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
                        return False, msg
                    if str(exp_vdns_rec_data.__dict__['record_ttl_seconds']) != act_cn_vdns_rec_data['record-ttl-seconds']:
                        msg = 'vdns record ttl value is not matching with control node data'
                        self.logger.error(msg)
                        return False, msg
                    if exp_vdns_rec_data.__dict__['record_type'] != act_cn_vdns_rec_data['record-type']:
                        msg = 'vdns record type value is not matching with control node data'
                        self.logger.error(msg)
                        return False, msg
                    if exp_vdns_rec_data.__dict__['record_data'] != act_cn_vdns_rec_data['record-data']:
                        msg = 'vdns record data is not matching with control node data'
                        self.logger.error(msg)
                        return False, msg
            except Exception as e:
                msg = "Exception happened"
                return False, msg
        msg = "VDNS record info is not matching with control node data"
        self.logger.debug(msg)
        return True, None
    # end of  _verify_in_control_nodes

    @retry(delay=5, tries=5)
    def _verify_in_api_server(self):
        ''' verify VDNS record data in API server '''
        result = True
        api_s_dns_rec = self.api_s_inspect.get_cs_dns_rec( rec_name=self.name, 
            vdns_name=self._args['virtual_DNS'].split(":")[-1], refresh=True)
        try:
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
                    return False, msg
        except Exception as e:
            msg = "Exception happened"
            return False, msg
        msg = "VDNS record info is not matching with API Server data"
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
   
    @property
    def vdns_record_fq_name (self):
       return self.fq_name_str

    @property
    def vdns_record_name (self):
       return self.name

   #TODO:
    def __init__ (self, connections, name, vdns_fqname, 
                 **kwargs):
        vdns_name = kwargs.get('vdns_name')
        domain = vdns_fqname
        name = kwargs.get('vdns_record_name')
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
        self._construct_contrail_params(name, domain, kwargs)
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

    def _construct_contrail_params (self, name, domain, kwargs):
        self._params = {
            'type': 'OS::ContrailV2::VirtualDnsRecord',
            'name' : name,
            'domain': domain,
        }
        record_name = kwargs.get('dns_record_name', 'TestRecord')
        record_type = kwargs.get('dns_record_type','A')
        record_class = kwargs.get('dns_record_class', 'IN')
        record_data = kwargs.get('dns_record_data', '127.0.0.1')
        record_ttl_seconds = kwargs.get('dns_record_ttl_seconds', 86400)
       
        self._params['virtual_DNS_record_data'] = {}
        self._params['virtual_DNS_record_data']['record_name'] = record_name
        self._params['virtual_DNS_record_data']['record_type'] = record_type
        self._params['virtual_DNS_record_data']['record_class'] = record_class
        self._params['virtual_DNS_record_data']['record_data'] = record_data
        self._params['virtual_DNS_record_data']['record_ttl_seconds'] = \
                    record_ttl_seconds
