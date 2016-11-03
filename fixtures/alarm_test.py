import fixtures
from project_test import *
from tcutils.util import *
from vnc_api.vnc_api import *
from time import sleep
from contrail_fixtures import *
import inspect
from tcutils.config import vnc_api_results


class AlarmFixture(fixtures.Fixture):

    ''' Fixture to create and verify and delete alarms.
        Create AlarmFixture object
    '''
    def __init__(self, inputs, connections, alarm_name=None,uve_keys=[], alarm_severity=None, 
                alarm_rules=None,operand1=None, operand2=None, description=None,variables=None,
                id_perms=None, perms2=None, display_name=None,parent_obj_type='project', 
                clean_up=True, project_name=None, project_fixture=None):
        self.connections = connections
        self.inputs = inputs or connections.inputs
        self.logger = self.connections.logger
        self.vnc_lib_h = self.connections.get_vnc_lib_h()
        self.api_s_inspect = self.connections.api_server_inspect
        self.analytics_obj = self.connections.analytics_obj
        self.alarm_name = alarm_name
        self.alarm_id = None
        self.alarm_fq_name = [self.inputs.domain_name, self.alarm_name]
        self.uve_keys = uve_keys
        self.alarm_severity = alarm_severity
        self.alarm_rules = alarm_rules
        self.operand1 = operand1
        self.operand2 = operand2
        self.description= description
        self.variables = variables
        self.id_perms = id_perms
        self.perms2 = perms2
        self.display_name = display_name
        self.parent_obj_type = parent_obj_type
        self.domain_name = self.connections.domain_name
        self.project_name = project_name or self.connections.project_name
        self.project_fixture = project_fixture
        if self.project_fixture:
            self.project_name = self.project_fixture.project_name  
        self.project_id = self.connections.get_project_id()
        self.parent_obj = None
        self.clean_up = clean_up
        self.obj = None
    # end __init__
    
    def read(self):
        if self.alarm_id:
            self.alarm_obj = self.vnc_lib_h.alarm_read(id = self.alarm_id)
            self.alarm_fq_name = self.alarm_obj.get_fq_name()
            self.alarm_name = self.alarm_obj.name
    # end read
            
    def setUp(self):
        super(AlarmFixture, self).setUp()
    #end setup
                
    def create(self, alarm_rules):
        self.alarm_rules = alarm_rules
        self.alarm_id = self.alarm_id or self.get_alarm_id()
        if self.alarm_id:
            self.read()
            self.logger.debug("alarm already present not creating" %
                              (self.alarm_name, self.alarm_id))
        else:
            self.logger.debug(" creating alarm : %s", self.alarm_name)
            self.already_present = False
            if self.parent_obj_type == 'global':
                self.parent_obj = self.get_global_config_obj()
            if self.parent_obj_type == 'project':
                if not self.project_fixture:
                    self.project_fixture = self.useFixture(
                        ProjectFixture(vnc_lib_h=self.vnc_lib_h,
                                       project_name=self.project_name,
                                       connections=self.connections))
                self.parent_obj = self.project_fixture.getObj()
            if not self.parent_obj:
                raise AmbiguousParentError("[[u'default-global-system-config'], [u'default-domain', u'default-project']]")
            if not self.alarm_rules:
                self.alarm_rules = self.create_alarm_rules()
            uve_keys_type = UveKeysType(self.uve_keys)
            self.alarm_obj = Alarm(name=self.alarm_name, parent_obj=self.parent_obj,
                                   alarm_rules=self.alarm_rules, alarm_severity=self.alarm_severity,
                                   uve_keys = uve_keys_type)
            #need to set rules and other parameters before passing alarm_obj
            self.alarm_id = self.vnc_lib_h.alarm_create(self.alarm_obj)
    #end create

    def create_expression(self, params_dict):
         return AlarmExpression(params_dict=params_dict)
    #end create_expression
    
    def create_and_list(self,and_list):
        return AlarmAndList(and_list=and_list)
    #end create_and_list
    
    def create_or_list(self,or_list):
        return AlarmOrList(or_list=or_list)
    #end create_or_list
    
    def configure_alarm_rules(self,params_dict_list, multi_or_conditions=False):
        '''configure single or multiple rules'''
        self.alarm_exp_list = []
        self.alarm_and_list = []
        self.alarm_or_list = []
        try:
            for params_dict in params_dict_list:
                alarm_exp = self.create_expression(params_dict)
                self.alarm_exp_list.append(alarm_exp)
            if multi_or_conditions:
                for alarm_exp in self.alarm_exp_list:
                    alarm_and = self.create_and_list([alarm_exp])
                    self.alarm_and_list.append(alarm_and)
            else:
                self.alarm_and_list.append(self.create_and_list(self.alarm_exp_list))
            self.alarm_or_list = self.create_or_list(self.alarm_and_list)
            return self.alarm_or_list
        except:
            self.logger.info('error configuring alarm')
    #end configure_alarm_rules
    
    def getObj(self):
        return self.alarm_obj
    #end getObj
    
    def set_display_name(self, display_name):
        self.display_name = display_name
        self.alarm_obj.set_display_name(display_name)
        self.vnc_lib_h.alarm_update(self.alarm_obj)
    #end set_display_name
    
    def get_display_name(self):
        return self.alarm_obj.get_display_name()
    #end get_display_name
    
    def get_alarm_id(self):
        if not self.alarm_id:
            try:
                alarm_obj = self.vnc_lib_h.alarm_read(
                    fq_name=self.alarm_fq_name)
                self.alarm_id = alarm_obj.uuid
            except NoIdError:
                return None
        return self.alarm_id
    #end get_alarm_id
    
    def get_global_config_obj(self):
        gsc_id = self.vnc_lib_h.get_default_global_system_config_id()
        gsc_obj = self.vnc_lib_h.global_system_config_read(id=gsc_id)
        return gsc_obj

    #end get_global_config_obj
    
    def set_alarm_rules(self,exp_list,multi_or_conditions=False):
        rules=self.configure_alarm_rules(exp_list,multi_or_conditions=multi_or_conditions)
        try:
            if rules:
                self.alarm_obj.set_alarm_rules(rules)
                self.vnc_lib_h.alarm_update(self.alarm_obj)
                return True
        except:
            return False
    #end set_alarm_rules
    
    def set_alarm_enable(self,enable):
        pass
    
    def set_alarm_disable(self):
        pass
    
    def get_alarm_severity(self):
        return self.alarm_severity
    #end get_alarm_severity
    
    def set_alarm_severity(self,severity):
        self.alarm_severity = severity
        self.alarm_obj.set_alarm_severity(severity)
        self.vnc_lib_h.alarm_update(self.alarm_obj)
    # set_alarm_severity
       
    def set_uve_keys(self,uve_key):
        self.uve_keys = uve_key
        uve_key_type = UveKeysType(uve_key)
        self.alarm_obj.set_uve_keys(uve_key_type)
        self.vnc_lib_h.alarm_update(self.alarm_obj)
    # set_uve_keys
       
    def get_uve_keys(self):
        return self.uve_keys
    #end get_uve_keys
    
    def verify_alarm_in_api_server(self):
        if self.parent_obj_type == 'project':
            self.cs_alarm = self.api_s_inspect.get_cs_alarm(
                project=self.project_name, alarm=self.alarm_name, refresh=True)
        else:
           self.cs_alarm = self.api_s_inspect.get_global_alarm(alarm_name=self.alarm_name) 
        if not self.cs_alarm:
            self.logger.info('Alarm %s not present in api server' %self.alarm_name)
            return False
        self.logger.info('Alarm %s present in the api-server' %self.alarm_name)
        return True
    #end verify_alarm_in_api_server
      
    def verify_alarm_config(self):
        alarm_config = self.cs_alarm
        name = alarm_config['alarm']['display_name']
        if not name:
            self.logger.debug('Alarm name is missing in the config')
            return False
        uve_keys = alarm_config['alarm']['uve_keys']['uve_key']
        if not (uve_keys == self.uve_keys):
            self.logger.info('uve_keys not present or doesn\'t match %s %s' %(uve_keys , self.uve_keys))
        rules = alarm_config['alarm']['alarm_rules']
        if not rules:
            self.logger.debug('rules are not present in config')
            return False
        return True
    #end verify_alarm_config       
    
    @retry(delay=3, tries=10)            
    def verify_alarm_not_in_api_server(self):
        cs_alarm = self.api_s_inspect.get_cs_alarm(
            project=self.project_name, alarm=self.alarm_name, refresh=True)
        if cs_alarm:
            errmsg = 'Alarm %s not removed from api-server' % self.alarm_name
            self.logger.warn(errmsg)
            return False
        self.logger.info('Alarm %s removed from api-server' % self.alarm_name)
        return True
    #end verify_alarm_not_in_api_server 
    
    def verify_alarm_setup(self):
        '''Verify alarm in configuration '''
        result = True
        result = self.verify_alarm_in_api_server()
        if not result:
            self.logger.error('Alarm %s verification in api-server failed'%self.alarm_name)
            return result
        result = self.verify_alarm_config()
        if not result:
            self.logger.error('Alarm not configured properly')
            return result
        return True
    #end verify_alarm_setup
    
    def cleanUp(self):
        super(AlarmFixture, self).cleanUp()
        do_cleanup = True
        if self.inputs.fixture_cleanup == 'no':
            do_cleanup = False
        if self.already_present:
            do_cleanup = False
        if self.inputs.fixture_cleanup == 'force':
            do_cleanup = True
        if self.clean_up == False:
            do_cleanup = False
        if do_cleanup:
            self._delete_alarm()
            self.logger.info('Deleted alarm %s' %self.alarm_name)
            assert self.verify_alarm_not_in_api_server()
        else:
            self.logger.debug('Skippping deletion of alarm %s' %self.alarm_name)
    #end cleanup
    
    def _delete_alarm(self, verify=False):
        try:
            self.vnc_lib_h.alarm_delete(id = self.alarm_id)
        except RefsExistError:
            return
    #end _delete_alarm
           
if __name__ == "__main__":
    vh=VncApi(username='admin',password='contrail123',tenant_name='admin',api_server_host='127.0.0.1',api_server_port='8082')
    gsc_id = vh.get_default_global_system_config_id()
    gsc_obj = vh.global_system_config_read(id=gsc_id)
    parent_obj_type='global-sys-config'
    rules={'or_list':  [{'and_list':  [{'operation': '!=','operand1': 'UveVMInterfaceAgent.active','operand2':{'json_value': 'true'}}]}]}
    alarm_fix=AlarmFixture()
