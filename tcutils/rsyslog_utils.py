from fabric.api import run
from fabric.context_managers import settings
import time
COLLECTOR_CONF_FILE = '/etc/contrail/contrail-collector.conf'
RSYSLOG_CONF_FILE = '/etc/rsyslog.conf'

def restart_collector_to_listen_on_port(
        self,
        collector_ip,
        port_no=35999):
    try:
        with settings(host_string='%s@%s' % (self.inputs.username, 
                      collector_ip), password=self.inputs.password,
                      warn_only=True, abort_on_prompts=False):
            cmd = "grep 'syslog_port' " + COLLECTOR_CONF_FILE
            output = run('%s' % (cmd), pty=True)
            if output:
                output = output.rstrip()
                cmd = "sed -i s/'" + str(output) + "'/'syslog_port="
                cmd = cmd + str(port_no) + "'/ " + COLLECTOR_CONF_FILE
                run('%s' % (cmd), pty=True)
                # Restart vizd if port no has been changed.
                cmd = "service contrail-collector restart"
                run('%s' % (cmd), pty=True)
                cmd = "service contrail-collector status | grep 'RUNNING'"
                output = run('%s' % (cmd), pty=True)
                if not 'RUNNING' in output:
                    self.logger.error(
                        "contrail-collector service restart failure!!")
            else:
                cmd = "sed -i '/DEFAULT/ a \syslog_port=" + \
                    str(port_no) + "' " + COLLECTOR_CONF_FILE
                run('%s' % (cmd), pty=True)
                # Restart vizd if port no has been changed.
                cmd = "service contrail-collector restart"
                run('%s' % (cmd), pty=True)
                cmd = "service contrail-collector status | grep 'RUNNING'"
                output = run('%s' % (cmd), pty=True)
                if not 'RUNNING' in output:
                    self.logger.error(
                        "contrail-collector service restart failure!!")
    except Exception as e:
        self.logger.exception(
            "Got exception at restart_collector_to_listen_on_port as %s" %
            (e))
# end restart_collector_to_listen_on_port


def update_rsyslog_client_connection_details(
        self,
        node_ip,
        server_ip='127.0.0.1',
        protocol='udp',
        port=35999,
        restart=False):
    try:
        with settings(host_string='%s@%s' % (self.inputs.username, node_ip),
                      password=self.inputs.password,
                      warn_only=True, abort_on_prompts=False):

            if protocol == 'tcp':
                protocol = '@@'
            else:
                protocol = '@'
            connection_string = protocol + server_ip + ':' + str(port)

            cmd = "grep '@\{1,2\}"
            cmd = cmd + "[0-9]\{1,3\}\.[0-9]\{1,3\}\.[0-9]\{1,3\}\.[0-9]\{1,3\}' "
            cmd = cmd + RSYSLOG_CONF_FILE
            output = run('%s' % (cmd), pty=True)
            if output:
                output = output.rstrip()
                cmd = "sed -i '/" + \
                    str(output) + "/c\*.* " + str(connection_string) \
                    + "' " + RSYSLOG_CONF_FILE
                run('%s' % (cmd), pty=True)
            else:
                cmd = "echo '*.* " + connection_string + \
                    "' >> " + RSYSLOG_CONF_FILE
                run('%s' % (cmd), pty=True)

            if restart is True:
                # restart rsyslog service
                cmd = "service rsyslog restart"
                run('%s' % (cmd), pty=True)
                cmd = "service rsyslog status | grep 'running'"
                output = run('%s' % (cmd), pty=True)
                if not 'running' in output:
                    self.logger.error("rsyslog service restart failure!!")

    except Exception as e:
        self.logger.exception(
            "Got exception at update_rsyslog_client_connection_details as %s" %
            (e))

# end update_syslog_client_connection_details


def restart_rsyslog_client_to_send_on_port(
        self,
        node_ip,
        server_ip,
        port_no=35999):
    try:
        with settings(host_string='%s@%s' % (self.inputs.username, node_ip),
                      password=self.inputs.password,
                      warn_only=True, abort_on_prompts=False):

            # update Working Directory in rsyslog.conf
            cmd = "grep 'WorkDirectory' " + RSYSLOG_CONF_FILE
            output = run('%s' % (cmd), pty=True)
            if output:
                output = output.rstrip()
                cmd = "sed -i '/$WorkDirectory/c\\\$WorkDirectory \/var\/tmp' "
                cmd = cmd + RSYSLOG_CONF_FILE
                run('%s' % (cmd), pty=True)
            else:
                cmd = "echo '$WorkDirectory /var/tmp' >> " + RSYSLOG_CONF_FILE
                run('%s' % (cmd), pty=True)

            # update Queue file name in rsyslog.conf
            cmd = "grep 'ActionQueueFileName' " + RSYSLOG_CONF_FILE
            output = run('%s' % (cmd), pty=True)
            if output:
                output = output.rstrip()
                cmd = "sed -i '/" + \
                    str(output) + "/c\\\$ActionQueueFileName fwdRule1' "
                cmd = cmd + RSYSLOG_CONF_FILE
                run('%s' % (cmd), pty=True)
            else:
                cmd = "echo '$ActionQueueFileName fwdRule1' >> "
                cmd = cmd + RSYSLOG_CONF_FILE
                run('%s' % (cmd), pty=True)

            # update Max Disk Space for remote logging packets in
            # rsyslog.conf
            cmd = "grep 'ActionQueueMaxDiskSpace' " + RSYSLOG_CONF_FILE
            output = run('%s' % (cmd), pty=True)
            if output:
                output = output.rstrip()
                cmd = "sed -i '/" + \
                    str(output) + "/c\\\$ActionQueueMaxDiskSpace 1g' "
                cmd = cmd + RSYSLOG_CONF_FILE
                run('%s' % (cmd), pty=True)
            else:
                cmd = "echo '$ActionQueueMaxDiskSpace 1g' >> "
                cmd = cmd + RSYSLOG_CONF_FILE
                run('%s' % (cmd), pty=True)

            # update Queue save on shutdown
            cmd = "grep 'ActionQueueSaveOnShutdown' " + RSYSLOG_CONF_FILE
            output = run('%s' % (cmd), pty=True)
            if output:
                output = output.rstrip()
                cmd = "sed -i '/" + \
                    str(output) + "/c\\\$ActionQueueSaveOnShutdown on' "
                cmd = cmd + RSYSLOG_CONF_FILE
                run('%s' % (cmd), pty=True)
            else:
                cmd = "echo '$ActionQueueSaveOnShutdown on' >> "
                cmd = cmd + RSYSLOG_CONF_FILE
                run('%s' % (cmd), pty=True)

            # update Queue type
            cmd = "grep 'ActionQueueType' " + RSYSLOG_CONF_FILE
            output = run('%s' % (cmd), pty=True)
            if output:
                output = output.rstrip()
                cmd = "sed -i '/" + \
                    str(output) + "/c\\\$ActionQueueType LinkedList' "
                cmd = cmd + RSYSLOG_CONF_FILE
                run('%s' % (cmd), pty=True)
            else:
                cmd = "echo '$ActionQueueType LinkedList' >> "
                cmd = cmd + RSYSLOG_CONF_FILE
                run('%s' % (cmd), pty=True)

            # update Connection resume retry count
            cmd = "grep 'ActionResumeRetryCount' " + RSYSLOG_CONF_FILE
            output = run('%s' % (cmd), pty=True)
            if output:
                output = output.rstrip()
                cmd = "sed -i '/" + \
                    str(output) + "/c\\\$ActionResumeRetryCount -1' "
                cmd = cmd + RSYSLOG_CONF_FILE
                run('%s' % (cmd), pty=True)
            else:
                cmd = "echo '$ActionResumeRetryCount -1' >> "
                cmd = cmd + RSYSLOG_CONF_FILE
                run('%s' % (cmd), pty=True)

            # update rsyslog client-server connection details
            update_rsyslog_client_connection_details(self, node_ip, server_ip)

            # restart rsyslog service
            cmd = "service rsyslog restart"
            run('%s' % (cmd), pty=True)
            cmd = "service rsyslog status | grep 'running'"
            output = run('%s' % (cmd), pty=True)
            if not 'running' in output:
                self.logger.error("rsyslog service restart failure!!")

    except Exception as e:
        self.logger.exception(
            "Got exception at restart_rsyslog_client_to_send_on_port as %s" %
            (e))

# end restart_rsyslog_client_to_send_on_port

def back_up_conf_files(
        self,
        hosts,
        file_path):

    for host in hosts:
        with settings(host_string='%s@%s' % (self.inputs.username, 
                      host), password=self.inputs.password,
                      warn_only=True, abort_on_prompts=False):
            cmd = "cp -f " + file_path + " " + file_path + "_backup"
            output = run('%s' % (cmd), pty=True)
    return True
# end back_up_rsyslog_conf_files

def restore_conf_for_rsyslog(
        self):
    cmd = "mv /etc/rsyslog.conf_backup /etc/rsyslog.conf; "
    cmd1 = "mv /etc/contrail/contrail-collector.conf_backup"
    cmd1 = cmd1 + " /etc/contrail/contrail-collector.conf"
    cmd2 = "service contrail-collector restart"
    cmd3 = "service rsyslog restart"

    for host in self.inputs.host_ips:
        with settings(host_string='%s@%s' % (self.inputs.username,
                      host), password=self.inputs.password,
                      warn_only=True, abort_on_prompts=False):
            run('%s' % (cmd), pty=True)
            run('%s' % (cmd3), pty=True)
    for host in self.inputs.collector_ips:
        with settings(host_string='%s@%s' % (self.inputs.username,
                      host), password=self.inputs.password,
                      warn_only=True, abort_on_prompts=False):
            run('%s' % (cmd1), pty=True)
            run('%s' % (cmd2), pty=True)

#end restore_conf_for_rsyslog

