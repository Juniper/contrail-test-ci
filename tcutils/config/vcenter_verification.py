from tcutils.util import retry
from tcutils.config import vmware_introspect_utils
from common import log_orig as contrail_logging

class VMWareVerificationLib:
    '''Clas to hold verification helper functions for vcenter plugin introspect'''
    def __init__(self,inputs):
        self.inputs = inputs
        self.vcntr_introspect = None
        self.logger = contrail_logging.getLogger(__name__)
        self.intfs_dict = {}

    def get_introspect(self):
        try:
            for ip in self.inputs.cfgm_ips:
                if  vmware_introspect_utils.\
			get_vcenter_plugin_introspect_elements(\
			vmware_introspect_utils.VMWareInspect(ip)):
                    self.vcntr_introspect = vmware_introspect_utils.VMWareInspect(ip)
                    break
        except Exception as e:
            self.logger.exception(e)

    @retry(delay=10, tries=10)
    def verify_vm_in_vcenter(self, vrouter_ip,vm_name, *args):

       #everytime verify_vm_in_vcenter should be called with introspect refreshed
       self.get_introspect()
       vrouter_details = vmware_introspect_utils.get_vrouter_details(self.vcntr_introspect, vrouter_ip)
       for virtual_machine in vrouter_details.virtual_machines:
           if virtual_machine.name == vm_name:
               self.logger.info("Vcenter plugin verification:%s launched in vorouter %s in virtual network %s"\
                               %(vm_name,vrouter_ip,virtual_machine.virtual_network))
               return True
       self.logger.error("Vcenter plugin verification:%s NOT launched in vorouter %s "\
                               %(vm_name,vrouter_ip))
       return False

    @retry(delay=10, tries=10)
    def verify_vm_not_in_vcenter(self, vrouter_ip,vm_name, *args):
       	#everytime verify_vm_in_vcenter should be called with introspect refreshe
		self.get_introspect()
		vrouter_details = vmware_introspect_utils.get_vrouter_details(self.vcntr_introspect, vrouter_ip)
		try:
			for virtual_machine in vrouter_details.virtual_machines:
				if virtual_machine.name == vm_name:
					self.logger.error("Vcenter plugin verification:%s STILL in vorouter %s in virtual network %s"\
								%(vm_name,vrouter_ip,virtual_machine.virtual_network))
					return False
		except Exception as e:
			self.logger.info("Vcenter plugin verification:%s deleted in vorouter %s "\
                               %(vm_name,vrouter_ip))
			return True

		self.logger.info("Vcenter plugin verification:%s deleted in vorouter %s "\
                               %(vm_name,vrouter_ip))
		return True

    def get_vmi_from_vcenter_introspect(self, vrouter_ip,vm_name, *args):
       intfs = []
       if vm_name in self.intfs_dict.keys():
           return self.intfs_dict[vm_name]
       self.get_introspect()
       vrouter_details = vmware_introspect_utils.get_vrouter_details(self.vcntr_introspect, vrouter_ip)
       for virtual_machine in vrouter_details.virtual_machines:
           if virtual_machine.name == vm_name:
               intfs.append(virtual_machine)
       self.intfs_dict[vm_name] = intfs
       return intfs
                
        

if __name__ == '__main__':
    #va =  vmware_introspect_utils.VMWareInspect('10.204.216.62')
    class Inputs:
        def __init__(self):
            self.cfgm_ips = ['10.204.216.61','10.204.216.62','10.204.216.63']
    #r =  vmware_introspect_utils.get_vrouter_details(va,'10.204.216.183')
    #import pprint
    #pprint.pprint(r)
    inputs = Inputs()
    vcenter = VMWareVerificationLib(inputs)
    #vcenter.verify_vm_in_vcenter('10.204.216.181','ctest-pt_svm0-91002703')
    abc = vcenter.get_vmi_from_vcenter_introspect('10.204.216.183','ctest-pt_svm0-33618931')
    import pdb;pdb.set_trace()

