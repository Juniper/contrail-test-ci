import os
import sys
import argparse
import functools
#from tcutils.util import *

def nested_set(dic, keys, value):
    for key in keys[:-1]:
        dic = dic.setdefault(key, {})
    dic[keys[-1]] = value


def command(**kwargs):
    cmd = ""
    if 'select' in kwargs:
        cmd = cmd + " --select " + kwargs['select']
    if 'where' in kwargs:
        cmd = cmd + ' --where ' + kwargs['where']
    if 'start_time' in kwargs:
        cmd = cmd + ' --start-time ' + kwargs['start_time']
    if 'end_time' in kwargs:
        cmd = cmd + ' --end-time ' + kwargs['end_time']
    if 'last' in kwargs:
        cmd = cmd + ' --last ' + kwargs['last']
    if 'table' in kwargs:
        cmd = cmd + ' --table ' + kwargs['table']
    return cmd


class ContrailLogs:

    def __init__(self, inputs, command,**kwargs):
        """
        Returns query result by contrail-logs/contrail-stats
        :Parameters:
          - `inputs`: object of class TestInputs
          - `command`: contrail-logs/contrail-stats
          - `analytics-api-ip`: collector ip to run the command,Default:127.0.0.1
          - `start_time`: start time of the query
          - `start_time`: end time of the query,Default:Now
          - `kwargs`: 
            -`select`:select fields of the query
            -`where`:where clause of the query
        """
        self.command = command
        self.inputs = inputs
        self.collector_node_user = self.inputs.host_data[
            self.inputs.collector_ip]['username']
        self.collector_node_password = self.inputs.host_data[
            self.inputs.collector_ip]['password'] 
        self.params = self.build_params(**kwargs) 
        self.cmd = self.build_command(self.params)
       
    def execute(self):
        output = self.inputs.run_cmd_on_server(self.inputs.collector_ip, self.cmd,
                                               self.collector_node_user,
                                               self.collector_node_password)
        return output.splitlines()

    def build_params(self, **kwargs):
        cmd = command(**kwargs)
        return cmd
 
    def build_command(self,params):
        cmd = self.command + ' '  + params 
        return cmd
        

class Inputs(object):
    def __init__(self,collector_ip,username,password):
        import logging
        self.logger = logging.getLogger(__name__)
        self.collector_ip = collector_ip
        self.host_data = dict()
        nested_set(self.host_data,[self.collector_ip,'username'],username) 
        nested_set(self.host_data,[self.collector_ip,'password'],password) 

    def run_cmd_on_server(self, server_ip, issue_cmd, username=None,
                          password=None, pty=True):
        from fabric.api import env, run, local
        from fabric.operations import get, put, reboot
        from fabric.context_managers import settings, hide
        from fabric.exceptions import NetworkError
        from fabric.contrib.files import exists
        with hide('everything'):
            with settings(
                host_string='%s@%s' % (username, server_ip), password=password,
                    warn_only=True, abort_on_prompts=False):
                output = run('%s' % (issue_cmd), pty=pty)
                return output
    # end run_cmd_on_server


def _parse_args( args_str):
    parser = argparse.ArgumentParser()
    args, remaining_argv = parser.parse_known_args(args_str.split())
    parser.add_argument(
                "--command", nargs='?', help="contrail-logs/contrail-stats",required=True)
    parser.add_argument(
                "--table", nargs='?', help="table to query",required=True)
    parser.add_argument(
                "--start_time", nargs='?', help="start time of the query")
    parser.add_argument(
                "--end_time", nargs='?', default="now",help="end_time of the query")
    parser.add_argument(
                "--collector_ip",  help="collector ip",required=True)
    parser.add_argument(
                "--collector_server_user", default='root', help="openstack server username")
    parser.add_argument(
                "--collector_server_password", default='c0ntrail123', help="openstack server password")
    parser.add_argument(
                "--last", default='10m', help="data of last 10 minuts/the value provided")
    args = parser.parse_args(remaining_argv)
    return args

def main(args_str = None):
    if not args_str:
       script_args = ' '.join(sys.argv[1:])
    script_args = _parse_args(script_args)

    collector_ip = script_args.collector_ip
    inputs = Inputs(collector_ip,script_args.collector_server_user,script_args.collector_server_password)
    query_command = ContrailLogs(inputs,script_args.command,
                               table = script_args.table,
                               last = script_args.last,
                               select = '"SUM(msg_info.messages)" msg_info.type name',
                               where = 'msg_info.type=FlowLogDataObject')
    output = query_command.execute()
    print output 


#Ussage:
#python query_contrail_tables.py --collector_ip 10.204.216.58 --command contrail-stats --table SandeshMessageStat.msg_info
if __name__ == "__main__":
    main()
