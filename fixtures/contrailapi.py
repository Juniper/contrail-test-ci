import logging

from tcutils.util import *
from vnc_api.vnc_api import *

class ContrailVncApi():

    def __init__(self, vnc, logger=None):
        self._vnc = vnc
        self._log = logger or logging.getLogger(__name__)

    def get_policy(self, fq_name, **kwargs):
        return self._vnc.network_policy_read(fq_name=fq_name)

    def get_floating_ip(self, fip_id, **kwargs):
        fip_obj = self._vnc.floating_ip_read(id=fip_id)
        return fip_obj.get_floating_ip_address()

    def create_floating_ip(self, pool_obj, project_obj, **kwargs):
        fip_obj = FloatingIp(get_random_name('fip'), pool_obj)
        fip_obj.set_project(project_obj)
        self._vnc.floating_ip_create(fip_obj)
        fip_obj = self._vnc.floating_ip_read(fq_name=fip_obj.fq_name)
        return (fip_obj.get_floating_ip_address(), fip_obj.uuid)

    def delete_floating_ip(self, fip_id, **kwargs):
        self._vnc.floating_ip_delete(id=fip_id)

    def assoc_floating_ip(self, fip_id, vm_id, **kwargs):
        fip_obj = self._vnc.floating_ip_read(id=fip_id)
        vm_obj = self._vnc.virtual_machine_read(id=vm_id)
        vmi = vm_obj.get_virtual_machine_interface_back_refs()[0]['uuid']
        vmintf = self._vnc.virtual_machine_interface_read(id=vmi)
        fip_obj.add_virtual_machine_interface(vmintf)
        self._log.debug('Associating FIP:%s with VMI:%s' % (fip_id, vm_id))
        self._vnc.floating_ip_update(fip_obj)
        return fip_obj

    def disassoc_floating_ip(self, fip_id, **kwargs):
        self._log.debug('Disassociating FIP %s' % fip_id)
        fip_obj = self._vnc.floating_ip_read(id=fip_id)
        fip_obj.virtual_machine_interface_refs=None
        self._vnc.floating_ip_update(fip_obj)
        return fip_obj

    def add_security_group(self, vm_id, sg_id, **kwargs):
        sg = self.get_security_group(sg_id)
        vnc_vm = self._vnc.virtual_machine_read(id=vm_id)
        vmis = [vmi['uuid'] for vmi in vnc_vm.get_virtual_machine_interface_back_refs()]
        vmis = [self._vnc.virtual_machine_interface_read(id=vmi) for vmi in vmis]
        for vmi in vmis:
            sg_lst = vmi.get_security_group_refs()
            if not sg_lst:
                sg_lst = []
            sg_lst.append({'uuid': sg.uuid, 'to':sg.fq_name})
            vmi.set_security_group_list(sg_lst)
            self._vnc.virtual_machine_interface_update(vmi)

    def remove_security_group(self, vm_id, sg_id, **kwargs):
        sg = self.get_security_group(sg_id)
        vnc_vm = self._vnc.virtual_machine_read(id=vm_id)
        vmis = [vmi['uuid'] for vmi in vnc_vm.get_virtual_machine_interface_back_refs()]
        vmis = [self._vnc.virtual_machine_interface_read(id=vmi) for vmi in vmis]
        for vmi in vmis:
            sg_lst = vmi.get_security_group_refs()
            if not sg_lst:
                return
            for i, sg_ref in enumerate(sg_lst):
                if sg_ref['uuid'] == sg.uuid:
                     break
            else:
                return
            sg_lst.pop(i)
            vmi.set_security_group_list(sg_lst)
            self._vnc.virtual_machine_interface_update(vmi)

    def create_security_group(self, sg_name, parent_fqname, sg_entries, **kwargs):
        sg = SecurityGroup(sg_name, parent_type='project',
                           fq_name=parent_fqname+[sg_name])
        sg.security_group_entries = PolicyEntriesType(sg_entries)
        self._vnc.security_group_create(sg)
        sg = self._vnc.security_group_read(fq_name=sg.get_fq_name())
        return sg.uuid

    def delete_security_group(self, sg_id, **kwargs):
        self._vnc.security_group_delete(id=sg_id)

    def get_security_group(self, sg_id, **kwargs):
        try:
            return self._vnc.security_group_read(id=sg_id)
        except:
            try:
                return self._vnc.security_group_read(fq_name=sg_id)
            except:
                return None

    def get_security_group_rules(self, sg_id, **kwargs):
        sg_info = self._vnc.security_group_read(id=sg_id)
        return sg_info.get_security_group_entries().exportDict()['PolicyEntriesType']['policy_rule']

    def delete_security_group_rules(self, sg_id, **kwargs):
        sg = self._vnc.security_group_read(id=sg_id)
        sg.set_security_group_entries(None)
        self._vnc.security_group_update(sg)

    def set_security_group_rules(self, sg_id, sg_entries, **kwargs):
        sg = self._vnc.security_group_read(id=sg_id)
        sg.set_security_group_entries(PolicyEntriesType(sg_entries))
        return self._vnc.security_group_update(sg)

    def get_vn_list(self, **kwargs):
       return self._vnc.virtual_networks_list(kwargs['parent_id'])['virtual-networks'] 

    def disable_policy_on_vmi(self, vmi_id, disable=True):
        '''
        Disables the policy on the VMI vmi_id
        '''

        log_str = 'DISABLED' if disable else 'ENABLED'

        vmi_obj = self._vnc.virtual_machine_interface_read(id=vmi_id)
        vmi_obj.set_virtual_machine_interface_disable_policy(disable)
        self._vnc.virtual_machine_interface_update(vmi_obj)
        self._log.info("Policy %s on VMI %s" % (log_str, vmi_id))

        return True
    # end disable_policy_on_vmi

    def add_fat_flow_to_vmi(self, vmi_id, fat_flow_config):
        '''vmi_id: vmi id where Fat flow config is to be added
           fat_flow_config: dictionary of format {'proto':<string>,'port':<int>}
        '''
        proto_type = ProtocolType(protocol=fat_flow_config['proto'],
                        port=fat_flow_config['port'])

        vmi_obj = self._vnc.virtual_machine_interface_read(id=vmi_id)
        fat_config = vmi_obj.get_virtual_machine_interface_fat_flow_protocols()
        if fat_config:
            fat_config.fat_flow_protocol.append(proto_type)
        else:
            fat_config = FatFlowProtocols(fat_flow_protocol=[proto_type])
        vmi_obj.set_virtual_machine_interface_fat_flow_protocols(
                                                fat_config)
        self._vnc.virtual_machine_interface_update(vmi_obj)
        self._log.info("Fat flow added on VMI %s: %s" % (
                            vmi_id, fat_flow_config))

        return True
    #end add_fat_flow_to_vmi

    def remove_fat_flow_on_vmi(self, vmi_id, fat_flow_config):
        '''
        Removes the first matching Fat flow configuration
        vmi_id: vmi id
        fat_flow_config: dictionary of format {'proto':<string>,'port':<int>}
        '''
        vmi_obj = self._vnc.virtual_machine_interface_read(id=vmi_id)
        fat_config_get = vmi_obj.get_virtual_machine_interface_fat_flow_protocols()
        if fat_config_get:
            for config in fat_config_get.fat_flow_protocol:
                if config.protocol == fat_flow_config['proto'] and \
                    config.port == fat_flow_config['port']:
                    fat_config_get.fat_flow_protocol.remove(config)
                    vmi_obj.set_virtual_machine_interface_fat_flow_protocols(
                                                            fat_config_get)
                    self._vnc.virtual_machine_interface_update(vmi_obj)
                    self._log.info("Fat flow config removed from VMI %s: %s" % (
                                        vmi_id, vars(config)))
                    break

        return True
    #end remove_fat_flow_on_vmi

    def add_proto_based_flow_aging_time(self, proto, port=0, timeout=180):
        '''
        Adds protocol based flow aging timeout value.
        proto: <string>, port: <int>, timeout: <int-in-seconds>
        '''

        fq_name = [ 'default-global-system-config',
                    'default-global-vrouter-config']
        gv_obj = self._vnc.global_vrouter_config_read(fq_name=fq_name)
        flow_aging = gv_obj.get_flow_aging_timeout_list()

        flow_aging_add = FlowAgingTimeout(protocol=proto, port=port, timeout_in_seconds=timeout)
        if flow_aging:
            flow_aging.flow_aging_timeout.append(flow_aging_add)
        else:
            flow_aging = FlowAgingTimeoutList([flow_aging_add])
        gv_obj.set_flow_aging_timeout_list(flow_aging)
        self._vnc.global_vrouter_config_update(gv_obj)

        self._log.info('Added global flow aging configuration: %s' % (vars(flow_aging_add)))

        return True
    #end add_proto_based_flow_aging_time

    def delete_proto_based_flow_aging_time(self, proto, port=0, timeout=180):
        '''
        Remove protocol based flow aging timeout value.
        proto: <string>, port: <int>, timeout: <int-in-seconds>
        '''

        fq_name = [ 'default-global-system-config',
                    'default-global-vrouter-config']
        gv_obj = self._vnc.global_vrouter_config_read(fq_name=fq_name)
        flow_aging = gv_obj.get_flow_aging_timeout_list()

        if not flow_aging:
            return
        for aging in flow_aging.flow_aging_timeout:
            values = vars(aging)
            if values['timeout_in_seconds'] == timeout and \
                values['protocol'] == proto and values['port'] == port:
                flow_aging.flow_aging_timeout.remove(aging)

                gv_obj.set_flow_aging_timeout_list(flow_aging)
                self._vnc.global_vrouter_config_update(gv_obj)

                self._log.info('Deleted the flow aging configuration: %s' % (vars(aging)))

                return True
    #end delete_proto_based_flow_aging_time
