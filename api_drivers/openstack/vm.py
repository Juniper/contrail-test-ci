import copy

try:
    from novaclient import exceptions as novaException

    class OsVmMixin:

        ''' Mixin class implements CRUD methods for virtual machine
        '''

        def create_virtual_machine (self, **kwargs):
            assert args['type'] == 'openstack', "Unsupport argument type"
            args = copy.deepcopy(kwargs)
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
                return ret[0]
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
