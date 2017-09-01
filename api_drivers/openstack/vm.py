import copy
from tcutils.util import retry
from common import vcenter_libs
from tcutils.timeout import timeout, TimeoutError

try:
   from novaclient import exceptions as novaException

   class OsVmMixin:

       ''' Mixin class implements CRUD methods for virtual machine
       '''

       def create_virtual_machine (self, **kwargs):
           assert kwargs['type'] == 'openstack', "Unsupport argument type"
           #args = copy.deepcopy(kwargs)
           args = kwargs
           del args['type']
           lst = []
           for nic in args['networks']:
               if nic.keys()[0] == 'port':
                   lst.append({'port-id': nic.values()[0]})
               else:
                   lst.append({'net-id': nic.values()[0]})
           args['nics'] = lst
           del args['networks']
           obj = self._nh.servers.create(**args)
           return obj.id

       def get_virtual_machine (self, uuid):
           ret = self._nh.servers.list(search_opts={'uuid':uuid})
           if ret:
               vm_details = VmDetails(ret[0], self._nh)
               return vm_details
           return None

       def delete_virtual_machine (self, obj=None, uuid=None):
           uuid = uuid or obj.id
           self._nh.servers.delete(uuid)

       def update_virtual_machine (self, obj=None, uuid=None, **kwargs):
           assert args['type'] == 'openstack', "Unsupport argument type"
           args = copy.deepcopy(kwargs)
           del args['type']
           pass #TODO

except ImportError:
   class OsVmMixin:
       pass

class VmDetails():
    '''
    Class to get VM details from nova
    '''
    def __init__(self, vm_obj, api_obj):
        '''vm_obj: nova VM obj, api_obj: nova obj'''
        self.obj = vm_obj
        self.name = vm_obj.name
        self.api_obj = api_obj
        self.get_vn_name(vm_obj)

    def get_vm_obj(self, vm_obj, wait_time=30):
        ''' It has been noticed that sometimes get() takes upto 20-30mins
            in error scenarios
            This method sets a timeout for the same
        '''
        with timeout(seconds=wait_time):
            try:
                vm_obj.get()
            except TimeoutError, e:
                #self.logger.error('Timed out while getting VM %s detail' % (
                #    vm_obj.name))
                return False
    # end get_vm_obj

    @retry(delay=1, tries=10)
    def get_vn_name(self, vm_obj):
        self.get_vm_obj(vm_obj)
        self.vn_names = vm_obj.networks.keys()

        if self.vn_names:
            return self.vn_names
        else:
            return False

    @retry(tries=1, delay=60)
    def _get_vm_ip(self, vm_obj, vn_name=None):
        ''' Returns a list of IPs for the VM in VN.

        '''
        vm_ip_dict = self.get_vm_ip_dict(vm_obj)
        if not vn_name:
            address = list()
            for ips in vm_ip_dict.itervalues():
                address.extend(ips)
            return (True, address)
        if vn_name in vm_ip_dict.keys() and vm_ip_dict[vn_name]:
            return (True, vm_ip_dict[vn_name])
        #self.logger.error('VM does not seem to have got an IP in VN %s' % (vn_name))
        return (False, [])
    # end get_vm_ip

    def get_vm_ip(self, vm_obj, vn_name=None):
        return self._get_vm_ip(vm_obj, vn_name)[1]

    def get_vm_ip_dict(self, vm_obj):
        ''' Returns a dict of all IPs with key being VN name '''
        self.get_vm_obj(vm_obj)
        ip_dict={}
        for key,value in vm_obj.addresses.iteritems():
            ip_dict[key] = list()
            for dct in value:
                ip_dict[key].append(dct['addr'])
        return ip_dict

    def wait_till_vm_is_active(self, vm_obj):
        return self.wait_till_vm_status(vm_obj, 'ACTIVE')
    # end wait_till_vm_is_active

    @retry(tries=30, delay=5)
    def wait_till_vm_status(self, vm_obj, status='ACTIVE'):
        try:
            self.get_vm_obj(vm_obj)
            if vm_obj.status == status or vm_obj.status == 'ERROR':
                #self.logger.debug('VM %s is in %s state now' %
                #                 (vm_obj, vm_obj.status))
                return (True,vm_obj.status)
            else:
                #self.logger.debug('VM %s is still in %s state, Expected: %s' %
                #                  (vm_obj, vm_obj.status, status))
                return False
        except novaException.NotFound:
            #self.logger.debug('VM console log not formed yet')
            return False
        except novaException.ClientException:
            #self.logger.error('Fatal Nova Exception while getting VM detail')
            return False
    # end wait_till_vm_status

    @property
    def hypervisors(self):
        if not getattr(self, '_hypervisors', None):
            try:
                self._hypervisors = self.api_obj.hypervisors.list()
            except novaException.Forbidden:
                self._hypervisors = None
                #<TBD>
                #self._hypervisors = self.admin_obj.obj.hypervisors.list()
        return self._hypervisors

    def get_host_of_vm(self, vm_obj):
        #<TBD>
        ''' if 'OS-EXT-SRV-ATTR:hypervisor_hostname' not in vm_obj.__dict__:
            vm_obj = self.admin_obj.get_vm_by_id(vm_obj.id) '''
        for hypervisor in self.hypervisors:
            if vm_obj.__dict__['OS-EXT-SRV-ATTR:hypervisor_hostname'] is not None:
                if vm_obj.__dict__['OS-EXT-SRV-ATTR:hypervisor_hostname']\
                    == hypervisor.hypervisor_hostname:
                    if hypervisor.hypervisor_type == 'QEMU' or \
                        hypervisor.hypervisor_type == 'docker':
                        host_name = vm_obj.__dict__['OS-EXT-SRV-ATTR:host']
                        return host_name
                    if 'VMware' in hypervisor.hypervisor_type:
                        host_name = vcenter_libs.get_contrail_vm_by_vm_uuid(self.inputs,vm_obj.id)
                        return host_name
            else:
                return
                #<TBD>
                ''' if vm_obj.__dict__['OS-EXT-STS:vm_state'] == "error":
                    self.logger.error('VM %s has failed to come up' %vm_obj.name)
                    self.logger.error('Fault seen in nova show <vm-uuid> is:  %s' %vm_obj.__dict__['fault'])
                else:
                    self.logger.error('VM %s has failed to come up' %vm_obj.name)
                self.logger.error('Nova failed to get host of the VM') '''
    # end get_host_of_vm
