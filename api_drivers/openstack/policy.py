
class OsPolicyMixin:

    ''' Mixin class implements CRUD methods for Policy
    '''

    def create_network_policy (self, **kwargs):
        args = {'name': kwargs['name']}
        args['entries'] = kwargs.get('network_policy_entries', {})
        pol = self._qh.create_policy({'policy': args})
        return pol['policy']['id']

    def update_network_policy (self, obj=None, uuid=None, **kwargs):
        args = {}
        args['entries'] = kwargs.get('network_policy_entries', {})
        uuid = uuid or obj['policy']['id']
        self._qh.update_policy(uuid, {'policy':args})

    def get_network_policy (self, uuid):
        return self._qh.show_policy(uuid)

    def delete_network_policy (self, obj=None, uuid=None):
        uuid = uuid or obj['policy']['id']
        return self._qh.delete_policy(uuid)
