import os
try:
   try:
       from quantumclient.quantum import client as qc
   except:
       from neutronclient.neutron import client as qc
   from novaclient import client as nc

   class OpenstackWrap:

       def __init__ (self, **kwargs):
           self._log = kwargs['logger']
           prj = kwargs['project_id'].replace('-', '')
           insecure = bool(os.getenv('OS_INSECURE', True))
           self._qh = qc.Client('2.0',
                                username=kwargs['username'],
                                password=kwargs['password'],
                                project_id=prj,
                                auth_url=kwargs['auth_url'],
                                region_name=kwargs['region_name'],
                                insecure=insecure)
           self._nh = nc.Client('2',
                                username=kwargs['username'],
                                api_key=kwargs['password'],
                                project_id=kwargs['project_name'],
                                auth_url=kwargs['auth_url'],
                                endpoint_type=kwargs['endpoint_type'],
                                region_name=kwargs['region_name'],
                                insecure=insecure)

       def get_flavor (self, name):
           return self._nh.flavors.find(name=name)

       def get_image (self, name):
           for image in self._nh.images.list():
               if image.name == name:
                   return image

       def create_virtual_machine (self, **kwargs):
           opts = {
               'name': kwargs['name'],
               'image': self.get_image(kwargs['image']),
               'flavor': self.get_flavor(kwargs['flavor']),
               'nics': None
           }
           lst = []
           for nic in kwargs['networks']:
               if nic.keys()[0] == 'port':
                   lst.append({'port-id': nic.values()[0]})
               else:
                   lst.append({'net-id': nic.values()[0]})
           opts['nics'] = lst
           obj = self._nh.servers.create(**opts)
           return obj.id

       def get_virtual_machine (self, rid):
           ret = self._nh.servers.list(search_opts={'uuid':rid})
           if ret:
               return ret[0]
           return None

       def delete_virtual_machine (self, vm):
           return self._nh.servers.delete(vm.id)

#TODO add methods for other resources
except:
   pass
