#TODO: replaces alarm_test.py
from contrail_fixtures import ContrailFixture
from tcutils.util import retry
from vnc_api.vnc_api import Alarm

class AlarmFixture_v2 (ContrailFixture):

   vnc_class = Alarm

   def __init__ (self, connections, uuid=None, params=None, fixs=None):
       super(AlarmFixture_v2, self).__init__(
           uuid=uuid,
           connections=connections,
           params=params,
           fixs=fixs)
       self.api_s_inspect = connections.api_server_inspect
       # Note: Add type specific initialization

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
       obj = self._vnc.get_alarm(self.uuid)
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
       self.uuid = self._ctrl.create_alarm(
           **self._args)

   def _delete (self):
       self.logger.info('Deleting %s' % self)
       self._ctrl.delete_alarm(
           obj=self._obj, uuid=self.uuid)

   def _update (self):
       self.logger.info('Updating %s' % self)
       self._ctrl.update_alarm(
           obj=self._obj, uuid=self.uuid, **self.args)

   def verify_on_setup (self):
       self.assert_on_setup(*self._verify_in_api_server())
       self.assert_on_cleanup(*self._verify_alarm_config())
       #TODO: check if more verification is needed

   def verify_on_cleanup (self):
       self.assert_on_cleanup(*self._verify_not_in_api_server())
       #TODO: check if more verification is needed

   def _verify_in_api_server (self):
       if not self._read_vnc_obj()[0]:
           return False, '%s not found in api-server' % self
       return True, None

   @retry(delay=5, tries=6)
   def _verify_not_in_api_server (self):
       if self._vnc.get_alarm(self.uuid):
           msg = '%s not removed from api-server' % self
           self.logger.debug(msg)
           return False, msg
       self.logger.debug('%s removed from api-server' % self)
       return True, None

   def verify_alarm_configuration(self):
       alarm_config = self.api_s_inspect.get_cs_alarm(alarm_id=self.alarm_id)
       alarm = alarm_config.get('alarm')
       name = alarm.get('display_name')
       if not (name == self.alarm_name):
           msg = 'Alarm name is missing in the config'
           self.logger.debug(msg)
           return False, msg
       uve_keys_dict = alarm.get('uve_keys')
       uve_keys = uve_keys_dict.get('uve_key')
       if not (uve_keys == self.uve_keys):
           msg = 'Uve_keys not present or doesn\'t match %s %s' % (uve_keys,
                                                                   self.uve_keys)
           self.logger.debug(msg)
           return False, msg
       rules = alarm.get('alarm_rules')
       if not rules:
           msg = 'Rules are not present in config'
           self.logger.debug(msg)
           return False, msg
       self.logger.info('Alarm %s configured properly ' %self.alarm_name)
       return True, None


class AlarmFixture (AlarmFixture_v2):

   ''' Fixture for backward compatibility '''

   def __init__ (self, connections, alarm_name=None, uve_keys=[],
                 project_fixture=None, alarm_rules=None):
       self.params = {
           'name' : alarm_name,
           'alarm_rules' : alarm_rules,
           'uve_keys' : {'uve_keys_uve_key' : uve_keys},
       }
       if project_fixture:
           self.params['parent_type'] = 'project'
           self.params['project'] = project_fixture.fq_name
       else:
           self.params['parent_type'] = 'global-system-config'
           self.params['global_system_config'] = ['default-global-system-config']
       super(AlarmFixture, self).__init__(connections=connections,
           params=self.params)

   def set_alarm_rules(self, exp_list):
       self.params['alarm_rules'] = exp_list
       self.update(self.params)

   def set_alarm_severity(self, severity):
       self.params['alarm_severity'] = severity
       self.update(self.params)

   def set_uve_keys(self, uve_key):
       self.params['uve_key'] = uve_key
       self.update(self.params)
