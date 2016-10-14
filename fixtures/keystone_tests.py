import os
from common.openstack_libs import ks_client as keystone_client
from common.openstack_libs import ks_v3_client as keystone_v3_client
from common.openstack_libs import ks_exceptions
from common.openstack_libs import keystoneclient
from common import log_orig as contrail_logging
from tcutils.util import retry, get_dashed_uuid

class KeystoneCommands():

    '''Handle all tenant managements'''

    def __init__(self, username=None, password=None, tenant=None,
                 auth_url=None, token=None, endpoint=None,
                 insecure=True, region_name=None,
                 logger=None, domain=None):

        self.logger = logger or contrail_logging.getLogger(__name__)
        if token:
            self.keystone = keystoneclient.Client(
                token=token, endpoint=endpoint)
        else:
            if (auth_url is not None) and ('v3' in auth_url):
                self.keystone = keystone_v3_client.Client(
                    username=username, password=password, domain_name=domain, auth_url=auth_url,
                    insecure=insecure, region_name=region_name or 'RegionOne')
            else:
                self.keystone = keystone_client.Client(
                    username=username, password=password, tenant_name=tenant, auth_url=auth_url,
                    insecure=insecure, region_name=region_name or 'RegionOne')

    def get_handle(self):
        return self.keystone

    def get_role_dct(self, role_name):
        all_roles = self.roles_list()
        for x in all_roles:
            if (x.name == role_name):
                return x
        return None

    def get_user_dct(self, user_name):
        all_users = self.user_list()
        for x in all_users:
            if (x.name == user_name):
                return x
        return None

    def get_tenant_dct(self, tenant_name):
        all_tenants = self.tenant_list()
        for x in all_tenants:
            if (x.name == tenant_name):
                return x
        return None

    def find_domain(self, domain_name):
        return self.keystone.domains.find(name=domain_name)

    def get_domain(self, domain_obj):
        return self.keystone.domains.get(domain_obj)

    def list_domains(self):
        return self.keystone.domains.list()

    def update_domain(self, domain_obj, domain_name=None,
                      description=None, enabled=None):
        return self.keystone.domains.update(domain=dobj, name=domain_name,
                                            description=description,
                                            enabled=enabled)

    def create_domain(self, domain_name):
        return get_dashed_uuid(self.keystone.domains.create(domain_name).id)

    def delete_domain(self, domain_name, domain_obj=None):
        if not domain_obj:
            domain_obj=self.find_domain(domain_name)
        self.update_domain(domain_obj=domain_obj, enabled=False)
        return self.keystone.domains.delete(domain_obj)

    def create_project(self, project_name, domain_name=None):
        if self.keystone.auth_ref.domain_scoped:
            if domain_name == self.keystone.domain_name:
                return get_dashed_uuid(self.keystone.projects.create(name=project_name).id)
            else:
                domain=self.keystone.domains.create(domain_name)
                return get_dashed_uuid(self.keystone.projects.create(name=project_name, domain=domain).id)
        else:
            return get_dashed_uuid(self.keystone.tenants.create(project_name).id)

    def delete_project(self, name, obj=None):
       if self.keystone.auth_ref.domain_scoped:
           if not obj:
               obj = self.keystone.projects.find(name=name)
           self.keystone.projects.delete(obj)
       else:
           if not obj:
               obj = self.keystone.tenants.find(name=name)
           self.keystone.tenants.delete(obj)

    def create_tenant_list(self, tenants=[]):
        for tenant in tenants:
            return_vlaue = self.create_project(project_name=tenant)

    def delete_tenant_list(self, tenants=[]):
        for tenant in tenants:
             self.delete_project(tenant)

    def update_tenant(self, tenant_id, tenant_name=None, description=None,
                      enabled=None):

        self.keystone.tenants.update(
            tenant_id, tenant_name=tenant_name, description=description, enabled=enabled)

    def add_user_to_tenant(self, tenant, user, role, domain=None):
        ''' inputs have to be string '''
        user = self.get_user_dct(user)
        role = self.get_role_dct(role)
        tenant = self.get_tenant_dct(tenant)
        if self.keystone.auth_ref.domain_scoped:
            domain_id=self.find_domain(domain)
            mem_role=self.get_role_dct('_member_')
            self.keystone.roles.grant(role, user=user, group=None, domain=domain_id)
            self.keystone.roles.grant(role, user=user, group=None, project=tenant)
            self.keystone.roles.grant(mem_role, user=user, group=None, domain=domain_id)
            self.keystone.roles.grant(mem_role, user=user, group=None, project=tenant)

        else:
            self._add_user_to_tenant(tenant, user, role)

    def _add_user_to_tenant(self, tenant, user, role):
        ''' inputs could be id or obj '''
        try:
            self.keystone.tenants.add_user(tenant, user, role)
        except ks_exceptions.Conflict as e:
            if 'already has role' in str(e):
                self.logger.debug(str(e))
            else:
                self.logger.info(str(e))

    def remove_user_from_tenant(self, tenant, user, role):

        user = self.get_user_dct(user)
        role = self.get_role_dct(role)
        tenant = self.get_tenant_dct(tenant)
        self.keystone.tenants.remove_user(tenant, user, role)

    def tenant_list(self, limit=None, marker=None):

        if self.keystone.auth_ref.domain_scoped:
            return self.keystone.projects.list()
        else:
            return self.keystone.tenants.list()

    def create_roles(self, role):

        self.keystone.roles.create(role)

    def delete_roles(self, role):

        role = self.get_role_dct(role)
        self.keystone.roles.delete(role)

    def add_user_role(self, user_name, role_name, tenant_name=None):

        user = self.get_user_dct(user_name)
        role = self.get_role_dct(role_name)
        if tenant_name:
            tenant = self.get_tenant_dct(tenant_name)

        self.keystone.roles.add_user_role(user, role, tenant)

    def get_role_for_user(self, user, tenant_name=None):

        user = self.get_user_dct(user)
        if tenant_name:
            tenant = self.get_tenant_dct(tenant_name)
        return self.keystone.roles.roles_for_user(user, tenant)

    def remove_user_role(self, user, role, tenant=None):

        user = self.get_user_dct(user)
        role = self.get_role_dct(role)
        if tenant:
            tenant = self.get_tenant_dct(tenant)

        self.keystone.roles.remove_user_role(user, role, tenant)

    def roles_list(self):

        return self.keystone.roles.list()

    def create_user(self, user, password, email='', tenant_name=None, enabled=True,
                    project_name=None, domain_name=None):

        if self.keystone.auth_ref.domain_scoped:
            project_id=self.get_tenant_dct(project_name).id
            domain_id=self.find_domain(domain_name).id
            self.keystone.users.create(user, domain_id, project_id, password, email, enabled=enabled)
        else:
            tenant_id = self.get_tenant_dct(tenant_name).id
            self.keystone.users.create(user, password, email, tenant_id, enabled)

    @retry(delay=3, tries=5)
    def delete_user(self, user):

        user = self.get_user_dct(user)
        try:
            self.keystone.users.delete(user)
            return True
        except ks_exceptions.ClientException, e:
            # TODO Remove this workaround 
            if 'Unable to add token to revocation list' in str(e):
                self.logger.warn('Exception %s while deleting user' % (
                                 str(e)))
                return False
    # end delete_user

    def update_user_tenant(self, user, tenant):

        user = self.get_user_dct(user)
        tenant = self.get_tenant_dct(tenant)
        self.keystone.users.update_tenant(user, tenant)

    def user_list(self, tenant_id=None, limit=None, marker=None):

        return self.keystone.users.list()

    def services_list(self, tenant_id=None, limit=None, marker=None):
        return self.keystone.services.list()

    def get_id(self):
        if self.keystone.auth_ref.domain_scoped:
            if self.keystone.auth_domain_id == 'default':
                return get_dashed_uuid(self.keystone.projects.find(name='admin').id)
            else:
                return None
        else:
            return get_dashed_uuid(self.keystone.auth_tenant_id)

    def get_project_id(self, name):
       try:
           if 'v3' in self.keystone.auth_url:
               obj =  self.keystone.projects.find(name=name)
           else:
               obj =  self.keystone.tenants.find(name=name)
           return get_dashed_uuid(obj.id)
       except ks_exceptions.NotFound:
           return None

    def get_endpoint(self, service):
       ''' Given the service-name return the endpoint ip '''
       return self.keystone.service_catalog.get_urls(service_type=service)
