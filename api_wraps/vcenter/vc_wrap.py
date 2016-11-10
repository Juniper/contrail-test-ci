# TODO: This module replaces
# fixtures/vcenter.py
# common/vcenter_libs.py
import time
from netaddr import IPNetwork
from tcutils.util import retry

try:
   from pyVmomi import vim, vmodl
   from pyVim import  connect

   _vimtype_dict = {
       'dc' : vim.Datacenter,
       'cluster' : vim.ClusterComputeResource,
       'vm' : vim.VirtualMachine,
       'host' : vim.HostSystem,
       'host.NasSpec' : vim.host.NasVolume.Specification,
       'network' : vim.Network,
       'ds' : vim.Datastore,
       'dvs.PortGroup' : vim.dvs.DistributedVirtualPortgroup,
       'dvs.VSwitch' : vim.dvs.VmwareDistributedVirtualSwitch,
       'dvs.PVLan' : vim.dvs.VmwareDistributedVirtualSwitch.PvlanSpec,
       'dvs.VLan' : vim.dvs.VmwareDistributedVirtualSwitch.VlanIdSpec,
       'dvs.PortConfig' : vim.dvs.VmwareDistributedVirtualSwitch.VmwarePortConfigPolicy,
       'dvs.ConfigSpec' : vim.dvs.DistributedVirtualPortgroup.ConfigSpec,
       'dvs.PortConn' : vim.dvs.PortConnection,
       'dvs.PortGroupSecurity' : vim.dvs.VmwareDistributedVirtualSwitch.SecurityPolicy,
       'dvs.PortGroupPolicy' : vim.host.NetworkPolicy,
       'dvs.Blob' : vim.dvs.KeyedOpaqueBlob,
       'ip.Config' : vim.vApp.IpPool.IpPoolConfigInfo,
       'ip.Association' : vim.vApp.IpPool.Association,
       'ip.Pool' : vim.vApp.IpPool,
       'dev.E1000' : vim.vm.device.VirtualE1000,
       'dev.VDSpec' : vim.vm.device.VirtualDeviceSpec,
       'dev.VD' : vim.vm.device.VirtualDevice,
       'dev.ConnectInfo' : vim.vm.device.VirtualDevice.ConnectInfo,
       'dev.DVPBackingInfo' : vim.vm.device.VirtualEthernetCard.DistributedVirtualPortBackingInfo,
       'dev.Ops.add' : vim.vm.device.VirtualDeviceSpec.Operation.add,
       'dev.Ops.remove' : vim.vm.device.VirtualDeviceSpec.Operation.remove,
       'dev.Ops.edit' : vim.vm.device.VirtualDeviceSpec.Operation.edit,
       'vm.Config' : vim.vm.ConfigSpec,
       'vm.Reloc' : vim.vm.RelocateSpec,
       'vm.Clone' : vim.vm.CloneSpec,
       'vm.PassAuth' : vim.vm.guest.NamePasswordAuthentication,
       'vm.Prog' : vim.vm.guest.ProcessManager.ProgramSpec,
   }

   def _vim_obj (typestr, **kwargs):
       return _vimtype_dict[typestr](**kwargs)

   @retry(delay=5, tries=60)
   def _wait_for_task (task):
       if (task.info.state == vim.TaskInfo.State.running or
           task.info.state == vim.TaskInfo.State.queued):
           return False
       if task.info.state != vim.TaskInfo.State.success:
           if task.info.state == vim.TaskInfo.State.error:
               raise Exception(task.info.error.localizedMessage)
           raise Exception("Something went wrong in wait_for_task")
       return True

   def _wait_for_task_timeout (task):
       if not _wait_for_task(task):
           raise RuntimeError("Timeout: task took too long")

   def _match_obj (obj, param):
       attr = param.keys()[0]
       attrs = [attr]
       if '.' in attr:
           attrs = attr.split('.')
           for i in range(len(attrs) - 1):
               if not hasattr(obj, attrs[i]):
                   break
               obj = getattr(obj, attrs[i])
       attr = attrs[-1]
       return hasattr(obj, attr) and getattr(obj, attr) == param.values()[0]

   class VcenterWrap:

       def __init__ (self, host, port, username, password, logger):
           self.logger = logger
           self._si = connect.SmartConnect(host=host, port=port,
                                           user=username, pwd=password)
           if not self._si:
               raise Exception("Unable to connect to vcenter: %s:%d %s/%s" % \
                          (self._host, self._port, self._user, self._passwd))
           self._content = self._si.RetrieveContent()
           if not self._content:
               raise Exception("Unable to retrieve content from vcenter")

       def _find_obj (self, root, vimtype, param):
           if vimtype == 'ip.Pool':
               items = self._content.ipPoolManager.QueryIpPools(self._dc)
           else:
               items = self._content.viewManager.CreateContainerView(root,
                               [_vimtype_dict[vimtype]], True).view
           for obj in items:
               if _match_obj(obj, param):
                   return obj
           return None

       def _get_obj_list (self, root, vimtype):
           view = self._content.viewManager.CreateContainerView(root,
                               [_vimtype_dict[vimtype]], True)
           return [obj for obj in view.view]

       def get_datacenter (self, name):
           return self._find_obj(self._content.rootFolder, 'dc',
                                 {'name' : name})

       def get_dvses (self, dc):
           return self._get_obj_list(dc, 'dvs.VSwitch')

       def get_zones (self, dc):
           return self._get_obj_list(dc, 'cluster')

       def get_hosts (self, cluster):
           return self._get_obj_list(cluster, 'host')

       def get_datastore (self, dc, name):
           return self._find_obj(dc, 'ds', {'name':name})

       def create_nfs_store (self, dc, rhost, rpath, lpath,
                             access='readWrite', hosts=None):
           if not hosts:
               hosts = [host for cluster in dc.hostFolder.childEntity \
                        for host in cluster.host]
           spec = _vim_obj('host.NasSpec', remoteHost=rhost, remotePath=rpath,
                           localPath=lpath, accessMode=access)
           ret = []
           for host in hosts:
               ds = host.configManager.datastoreSystem.CreateNasDatastore(spec)
               ret.append((host, ds))

       def delete_nfs_store (self, pairs):
           for host, ds in pairs:
               host.configManager.datastoreSystem.RemoveDatastore(ds)

       def get_private_vlan_pairs (self, dvs, vlan_type='isolated'):
           return [(vlan.primaryVlanId, vlan.secondaryVlanId) for vlan in \
                   dvs.config.pvlanConfig if vlan.pvlanType == vlan_type]

       def enter_maintenance_mode (self, host):
           if host.runtime.inMaintenanceMode:
               self.logger.debug("Host %s already in maintenance mode" % name)
               return
           for vm in host.vm:
               if vm.summary.config.template:
                   continue
               self.logger.debug("Powering off %s" % vm.name)
               _wait_for_task_timeout(vm.PowerOff())
           self.logger.debug("EnterMaintenence mode on host %s" % name)
           _wait_for_task_timeout(host.EnterMaintenanceMode(timeout=10))

       def exit_maintenance_mode (self, host):
           if not host.runtime.inMaintenanceMode:
               self.logger.debug("Host %s not in maintenance mode" % name)
               return
           self.logger.debug("ExitMaintenence mode on host %s" % name)
           _wait_for_task_timeout(host.ExitMaintenanceMode(timeout=10))
           for vm in host.vm:
               if vm.summary.config.template:
                   continue
               self.logger.debug("Powering on %s" % vm.name)
               _wait_for_task_timeout(vm.PowerOn())

       #TODO def register_virtual_machine_template

       #TODO def get_virtual_machine (self, dc, rid):

       #TODO def create_virtual_machine (self, dc, **kwargs):

       def delete_virtual_machine (self, vm_obj):
           if vm_obj.runtime.powerState != 'poweredOff':
               try:
                   _wait_for_task_timeout(vm_obj.PowerOff())
               except RuntimeError: # Ignore if VM shutdown took too long
                   pass
               _wait_for_task_timeout(vm_obj.Destroy())

       def migrate_virtual_machine (self, vm_obj, host):
           if host == vm_obj.runtime.host:
               self.logger.debug("Src %s & Dst %s is same" % (host, vm_obj.host))
               return
           _wait_for_task_timeout(vm.RelocateVM_Task(_vim_obj('vm.Reloc',
                                   host=tgt, datastore=tgt.datastore[0])))

       #TODO def get_virtual_network (self, dc, rid):

       #TODO def create_virtual_network (self, dc, **kwargs):

       #TODO def delete_virtual_network (self, vn_obj):

       def run_cmd_in_virtual_machine (self, dc, vm_id, vm_user, vm_password,
                                       path_to_cmd, cmd_args=None):
           vm = self._find_obj(dc, 'vm', {'summary.config.instanceUuid':vm_id})
           creds = _vim_obj('vm.PassAuth', username=vm_user,
                            password=vm_password)
           ps = _vim_obj('vm.Prog', programPath=path_to_cmd, arguments=cmd_args)
           pm = self._content.guestOperationsManager.processManager
           res = pm.StartProgramInGuest(vm, creds, ps)
           return res

       def reboot_virtual_machine (self, vm_obj, r):
           assert r != 'SOFT', 'Soft reboot is not supported, use \
                                VMFixture.run_cmd_on_vm'
           _wait_for_task_timeout(vm_obj.ResetVM_Task())

except ImportError:
   pass
