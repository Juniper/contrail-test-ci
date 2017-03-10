import test_v1
from common.connections import ContrailConnections
from common import isolated_creds
import testtools

import time 
import ast
from tcutils.contrail_status_check import ContrailStatusChecker

class BaseServiceConnectionsTest(test_v1.BaseTestCase_v1):

    @classmethod
    def setUpClass(cls):
        super(BaseServiceConnectionsTest, cls).setUpClass()
        cls.quantum_h= cls.connections.quantum_h
        cls.nova_h = cls.connections.nova_h
        cls.vnc_lib= cls.connections.vnc_lib
        cls.agent_inspect= cls.connections.agent_inspect
        cls.cn_inspect= cls.connections.cn_inspect
        cls.analytics_obj=cls.connections.analytics_obj
        cls.ops_inspect=cls.connections.ops_inspect
    #end setUpClass

    @classmethod
    def tearDownClass(cls):
        super(BaseServiceConnectionsTest, cls).tearDownClass()
    #end tearDownClass

    def get_all_configured_servers(self, service_name, client_role, client_process):
        ''' This function gets list of all applicable servers for
        a particular client.
        It reads .conf file to get the list
        Values to argument "client_process" can be any process which we
        see under contrail-status output eg "contrail-control"
        Values to argument "service_name" can be:
                    "collector", "xmpp", "dns", "rabbitmq" and "redis"
        Values to argument "client_role" can be:
                    "agent", "control", "config", "analytic" and "database" '''
        if "nodemgr" in client_process and service_name == "collector":
            section = "COLLECTOR"
            option = "server_list"
        elif service_name == "collector":
            section = "DEFAULT"
            option = "collectors"
        elif service_name == "xmpp":
            section = "CONTROL-NODE"
            option = "servers"
        elif service_name == "dns":
            section = "DNS"
            option = "servers"
        elif service_name == "rabbitmq":
            section = "IFMAP"
            option = "rabbitmq_server_list"
        elif service_name == "redis":
            section = "REDIS"
            option = "redis_uve_list"
        client_conf_file = client_process + ".conf"
        cmd_set = "openstack-config --get /etc/contrail/" + client_conf_file
        cmd = cmd_set + " " + section + " " + option
        if client_role == "agent":
            node_ip = self.inputs.compute_control_ips[0]
        elif client_role == "control":
            node_ip = self.inputs.bgp_control_ips[0]
        elif client_role == "config":
            node_ip = self.inputs.cfgm_control_ips[0]
        elif client_role == "analytic":
            node_ip = self.inputs.collector_control_ips[0]
        elif client_role == "database":
            node_ip = self.inputs.database_control_ips[0]
        output = self.inputs.run_cmd_on_server(node_ip, cmd,
                            self.inputs.host_data[node_ip]['username']\
                            , self.inputs.host_data[node_ip]['password'])
        server_list = []
        if "ConfigParser" in output:
            self.logger.error("Section or Option mentioned in the CLI do not"
                              "exist. Please check the options")
        else:
            output = output.split(" ")
            server_list= [elem for elem in output if elem != " "] # removing empty elements due to spaces
            self.logger.debug("Following '%s' servers were configured for '%s'"
                               "client: %s"
                              % (service_name, client_process, server_list))
            server_list = [elem.split(':')[0] for elem in server_list] # removing port info
        return server_list
    # end get_all_configured_serversget_all_configured_servers
    
    def get_all_configured_servers_for_webui(self, service_name):
        ''' This function gets list of all applicable servers for
        ContrailWebUI  client
        It reads config.global.js file to get the list
        Values to argument "service_name" can be:
                    "collector", "api or "dns" '''
        if service_name == "collector":
            cmd = 'cat /etc/contrail/config.global.js | grep "config.analytics.server_ip" | cut -d= -f2-'
        elif service_name == "api":
            cmd = 'cat /etc/contrail/config.global.js | grep "config.cnfg.server_ip" | cut -d= -f2-'
        elif service_name == "dns":
            cmd = 'cat /etc/contrail/config.global.js | grep "config.dns.server_ips" | cut -d= -f2-'
        node_ip = self.inputs.webui_control_ips[0]
        output = self.inputs.run_cmd_on_server(node_ip, cmd,
                            self.inputs.host_data[node_ip]['username']\
                            , self.inputs.host_data[node_ip]['password'])
        output = output.strip().rstrip(";")
        server_list = ast.literal_eval(output)
        self.logger.debug("Following %s servers were configured for WebUI"
                               "client: %s"
                              % (service_name, server_list))
        return server_list
    # end get_all_configured_servers_for_webui
    
    def get_all_in_use_servers(self, service_name, client_role, client_process, client_ip):
        ''' This function gets list of all applicable servers for
        a particular client.
        It reads .conf file to get the list 
        Values to argument "service_name" can be:
                    "collector", "xmpp", "dns" or "rabbitmq"
        Values to argument "client_role" can be:
                    "agent", "control", "config", "analytic" and "database" '''
        client_node_name = self.inputs.host_data[client_ip]['name']
        server_addr_list = []
        server_addr_status = []
        # First 'if' statement is to get all connections of "agent"
        # "Vrouter-agent" connects to 'XMPP', 'DNS' and "COLLECTOR' Servers
        if service_name == "xmpp" or service_name == "dns" or \
            service_name == "collector" and client_role == "agent":
            vrouter_uve_dict = self.ops_inspect.get_ops_vrouter(
                                                    client_node_name)
            index = self.find_index(vrouter_uve_dict, client_process)
            connection_info = vrouter_uve_dict['NodeStatus']\
                            ['process_status'][index]['connection_infos']
            for connections in connection_info:
                if service_name == "xmpp":
                    if connections['type'] == 'XMPP' and \
                        connections['name'].split(":")[0] == "control-node":
                        server_addr_list.append(connections[
                                            'server_addrs'][0].split(':')[0])
                        server_addr_status.append(connections['status'])
                elif service_name == "dns":
                    if connections['type'] == 'XMPP' and \
                        connections['name'].split(":")[0] == "dns-server":
                        server_addr_list.append(connections[
                                            'server_addrs'][0].split(':')[0])
                        server_addr_status.append(connections['status'])
        elif (service_name == "collector" or service_name == "rabbitmq")\
            and client_role == "control":
            if client_process != "contrail-dns":
                control_uve_dict = self.ops_inspect.get_ops_bgprouter(
                                                    client_node_name)
            else:
                control_uve_dict = self.ops_inspect.get_ops_dns(
                                                    client_node_name)
            index = self.find_index(control_uve_dict, client_process)
            connection_info = control_uve_dict['NodeStatus']\
                            ['process_status'][index]['connection_infos']
            for connections in connection_info:
                if service_name == "rabbitmq":
                    if connections['type'] == 'Database' and \
                        connections['name'] == "RabbitMQ":
                        server_addr_list.append(connections[
                                            'server_addrs'][0].split(':')[0])
                        server_addr_status.append(connections['status'])
        elif service_name == "collector" and client_role == "config":
            config_uve_dict = self.ops_inspect.get_ops_config(
                                                    client_node_name)
            index = self.find_index(config_uve_dict, client_process)
            connection_info = config_uve_dict['NodeStatus']\
                            ['process_status'][index]['connection_infos']
        elif (service_name == "collector" or service_name == "redis")\
            and client_role == "analytic":
            collector_uve_dict = self.ops_inspect.get_ops_collector(
                                                    client_node_name)
            index = self.find_index(collector_uve_dict, client_process)
            connection_info = collector_uve_dict['NodeStatus']\
                            ['process_status'][index]['connection_infos']
        elif service_name == "collector" and client_role == "database":
            database_uve_dict = self.ops_inspect.get_ops_db(
                                                    client_node_name)
            index = self.find_index(database_uve_dict, client_process)
            connection_info = database_uve_dict['NodeStatus']\
                            ['process_status'][index]['connection_infos']
        for connections in connection_info:
            if service_name == "collector":
                if connections['type'] == 'Collector':
                    server_addr_list.append(connections[
                                        'server_addrs'][0].split(':')[0])
                    server_addr_status.append(connections['status'])
            elif service_name == "redis":
                if connections['type'] == 'Redis-UVE':
                    if connections['name'] != "AggregateRedis":
                        server_addr_list.append(connections[
                                        'server_addrs'][0].split(':')[0])
                        server_addr_status.append(connections['status'])
        self.logger.info("Client process '%s' running on node '%s' is connected"
                          " to '%s' server running on IPs %s with status %s" \
                         % (client_process, client_node_name, service_name,
                            server_addr_list, server_addr_status))
        return server_addr_list, server_addr_status
    # end get_all_in_use_servers
    
    def add_remove_server(self, operation, server_ip, section, option,
                           client_role, client_process, index = 0):
        ''' This function add or remove an entry from list of servers 
        configured in .conf file of the client.
        It reads .conf file to get the list.
        It then searches if entry already exist or not and do the operation
        Values to argument "client_process" can be any process which we
                see under contrail-status output eg "contrail-control"
        Values to argument "operation" can be:
                "add" or "remove"
        Values to argument "client_role" can be:
                "agent", "control", "config", "analytic" and "database"
        '''
        client_conf_file = client_process + ".conf"
        cmd_set = "openstack-config --get /etc/contrail/" + client_conf_file
        cmd = cmd_set + " " + section + " " + option
        if client_role == "agent":
            for ip in self.inputs.compute_control_ips:
                server_list = self.get_new_server_list(operation, ip,
                                                       cmd, server_ip, index)
                self.configure_server_list(ip, client_process,
                               section, option, server_list)
        elif client_role == "control":
            for ip in self.inputs.bgp_control_ips:
                server_list = self.get_new_server_list(operation, ip,
                                                       cmd, server_ip, index)
                self.configure_server_list(ip, client_process,
                               section, option, server_list)
        elif client_role == "config":
            for ip in self.inputs.cfgm_control_ips:
                server_list = self.get_new_server_list(operation, ip,
                                                       cmd, server_ip, index)
                self.configure_server_list(ip, client_process,
                               section, option, server_list)
        elif client_role == "analytic":
            for ip in self.inputs.collector_control_ips:
                server_list = self.get_new_server_list(operation, ip,
                                                       cmd, server_ip, index)
                self.configure_server_list(ip, client_process,
                               section, option, server_list)
        elif client_role == "database":
            for ip in self.inputs.database_control_ips:
                server_list = self.get_new_server_list(operation, ip,
                                                       cmd, server_ip, index)
                self.configure_server_list(ip, client_process,
                               section, option, server_list)
        status_checker = ContrailStatusChecker(self.inputs)
        result = status_checker.wait_till_contrail_cluster_stable()[0]
        if result == False:
            assert result, "Contrail cluster not up after add/remove of entry"
    
    def get_new_server_list(self, operation, client_ip, cmd, server_ip,
                            index):
        '''
        client_ip = IP of node where "cmd" will be executed
        server_ip = IP of server to be searched in .conf file
        cmd = openstack-config command to run on client node to get server list
        operation
        '''
        output = self.inputs.run_cmd_on_server(client_ip, cmd,
                            self.inputs.host_data[client_ip]['username']\
                            , self.inputs.host_data[client_ip]['password'])
        output = output.split(" ")
        server_list= [elem for elem in output if elem != " "]
        server_port = server_list[0].split(":")[1]
        server = server_ip + ":" + server_port
        if operation == "add":
            if server in server_list:
                self.logger.debug("IP already present in list")
            else:
                server_list.insert(index, server)
                self.logger.debug("IP added in the list on node %s"
                                  % client_ip)
        elif operation == "remove":
            if server not in server_list:
                self.logger.debug("IP not in list")
            else:
                server_list.remove(server)
                self.logger.debug("IP removed from the list on node %s"
                                  % client_ip)
        return server_list
    
    def configure_server_list(self, client_ip, client_process,
                               section, option, server_list):
        '''
        This function configures the .conf file with new server_list
        and then send a sighup to the client so that configuration
        change is effective.
        '''
        client_conf_file = client_process + ".conf"
        server_string =  " ".join(server_list)
        cmd_set = "openstack-config --set /etc/contrail/" + client_conf_file
        cmd = cmd_set + " " + section + " " + option + ' "%s"' % server_string
        self.inputs.run_cmd_on_server(client_ip, cmd,
                            self.inputs.host_data[client_ip]['username']\
                            , self.inputs.host_data[client_ip]['password'])
        pid_cmd = "service %s status | awk '{print $4}' | cut -f1,1 -d','"\
                    % client_process
        pid = self.inputs.run_cmd_on_server(client_ip, pid_cmd,
                            self.inputs.host_data[client_ip]['username']\
                            , self.inputs.host_data[client_ip]['password'])
        sighup_cmd = "kill -SIGHUP %s " % pid
        self.inputs.run_cmd_on_server(client_ip, sighup_cmd,
                            self.inputs.host_data[client_ip]['username']\
                            , self.inputs.host_data[client_ip]['password'])
        
    def find_index(self, uve_dict, client_process):
        ''' Finding the index of client process in the dictionary '''
        index = 0
        for processes in uve_dict['NodeStatus']\
                    ['process_status']:
            if processes['module_id'] == client_process:
                break
            else:
                index = index+1
        return index          
    
    def skip_if_setup_incompatible(self, client_node_type, min_client_count,
                                   server_node_type, min_server_count):
        '''
        This function skips the test case if expected number of clients and 
        servers are not running
        **client_node_type can be "agent", "control", "analytic", "config"
        and "database"
        **server_node_type can be:
             "control" if testing for 'xmpp' or 'dns' servers,
             "collector" if testing for 'analytic' server,
             "config"if testing for rabbitMQ server
        '''
        result = True
        # Below 'if' block checks for client count
        if client_node_type == "agent":
            if min_client_count > len(self.inputs.compute_control_ips):
                result = False
        elif client_node_type == "control":
            if min_client_count > len(self.inputs.bgp_control_ips):
                result = False
        elif client_node_type == "analytic":
            if min_client_count > len(self.inputs.collector_control_ips):
                result = False
        elif client_node_type == "config":
            if min_client_count > len(self.inputs.cfgm_control_ips):
                result = False
        elif client_node_type == "database":
            if min_client_count > len(self.inputs.database_control_ips):
                result = False
        # Below 'if' block checks for server count
        if server_node_type == "analytic":
            if min_server_count > len(self.inputs.collector_control_ips):
                result = False
        elif server_node_type == "control":
            if min_server_count > len(self.inputs.bgp_control_ips):
                result = False
        elif server_node_type == "config":
            if min_server_count > len(self.inputs.cfgm_control_ips):
                result = False
        if not result:
            self.logger.debug("Expected number of '%s' servers or '%s' clients "
                              " are not present in the topology" % 
                              (server_node_type, client_node_type))
            skip = True
            msg = "Skipping because setup requirements are not met"
            raise testtools.TestCase.skipException(msg)
        
