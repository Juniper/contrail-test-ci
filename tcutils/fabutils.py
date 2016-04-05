from fabric.operations import get, put, sudo
from fabric.api import run, env
from fabric.exceptions import CommandTimeout, NetworkError
from fabric.contrib.files import exists
from fabric.context_managers import settings, hide, cd


import re
import logging
import time
import random
import os

log = logging.getLogger('log01')
sku_dict = {'2014.1': 'icehouse', '2014.2': 'juno', '2015.1': 'kilo', '12.0': 'liberty'}


def get_os_env(var):
    if var in os.environ:
        return os.environ.get(var)
    else:
        return None
# end get_os_env


def remove_unwanted_output(text):
    """ Fab output usually has content like [ x.x.x.x ] out : <content>
    Args:
        text: text to parse
    """
    if not text:
        return None

    return_list = text.split('\n')

    return_list1 = []
    for line in return_list:
        line_split = line.split(' out: ')
        if len(line_split) == 2:
            return_list1.append(line_split[1])
        else:
            if ' out:' not in line:
                return_list1.append(line)
    real_output = '\n'.join(return_list1)
    return real_output


def run_cmd(host_string, cmd, password=None, gateway=None,
            gateway_password=None, with_sudo=False, timeout=120,
            as_daemon=False, raw=False, cwd=None, warn_only=True):
    """ Run command on remote node through another node (gateway).
        This is useful to run commands on VMs through compute node
    Args:
        host_string: host_string on which the command to run
        password: Password
        cmd: command
        gateway: host_string of the node through which host_string will connect
        gateway_password: Password of gateway hoststring
        with_sudo: use Sudo
        timeout: timeout
        cwd: change directory to provided parameter
        as_daemon: run in background
        warn_only: run fab with warn_only
        raw: If raw is True, will return the fab _AttributeString object itself without removing any unwanted output
    """
    if as_daemon:
        cmd = 'nohup ' + cmd + ' &'

    if cwd:
        cmd = 'cd %s; %s' % (cd, cmd)

    (username, host_ip) = host_string.split('@')

    if username == 'root':
        with_sudo = False

    shell = '/bin/bash -l -c'

    if username == 'cirros':
        shell = '/bin/sh -l -c'

    _run = sudo if with_sudo else run

    # with hide('everything'), settings(host_string=host_string,
    with settings(
            host_string=host_string,
            gateway=gateway,
            warn_only=warn_only,
            shell=shell,
            disable_known_hosts=True,
            abort_on_prompts=False):
        env.forward_agent = True
        gateway_hoststring = (gateway if re.match(r'\w+@[\d\.]+:\d+', gateway)
                              else gateway + ':22')
        node_hoststring = (host_string
                           if re.match(r'\w+@[\d\.]+:\d+', host_string)
                           else host_string + ':22')
        if password:
            env.passwords.update({node_hoststring: password})
            # If gateway_password is not set, guess same password
            # (if key is used, it will be tried before password)
            if not gateway_password:
                env.passwords.update({gateway_hoststring: password})

        if gateway_password:
            env.passwords.update({gateway_hoststring: gateway_password})
            if not password:
                env.passwords.update({node_hoststring: gateway_password})

        log.debug(cmd)
        tries = 1
        output = None
        while tries > 0:
            if timeout:
                try:
                    output = _run(cmd, timeout=timeout)
                except CommandTimeout:
                    pass
            else:
                output = _run(cmd)
            if output and 'Fatal error' in output:
                tries -= 1
                time.sleep(5)
            else:
                break
        # end while

        if not raw:
            real_output = remove_unwanted_output(output)
        else:
            real_output = output
        return real_output


def run_netconf_on_node(host_string, password, cmds, op_format='text'):
    '''
    Run netconf from node to a VM.Usecase: vSRX or vMX or any netconf supporting device.
    '''
    (username, host_ip) = host_string.split('@')
    timeout = 10
    device = 'junos'
    hostkey_verify = "False"
    # Sometimes, during bootup, there could be some intermittent conn. issue
    tries = 1
    output = None
    copy_fabfile_to_agent()
    while tries > 0:
        if 'show' in cmds:
            cmd_str = 'fab -u %s -p "%s" -H %s -D -w --hide status,user,running get_via_netconf:\"%s\",\"%s\",\"%s\",\"%s\",\"%s\"' % (
                username, password, host_ip, cmds, timeout, device, hostkey_verify, op_format)
        else:
            cmd_str = 'fab -u %s -p "%s" -H %s -D -w --hide status,user,running config_via_netconf:\"%s\",\"%s\",\"%s\",\"%s\"' % (
                username, password, host_ip, cmds, timeout, device, hostkey_verify)
        log.debug(cmd_str)
        output = run(cmd_str)
        log.debug(output)
        if ((output) and ('Fatal error' in output)):
            tries -= 1
            time.sleep(5)
        else:
            break
    # end while
    return output
# end run_netconf_on_node


def copy_fabfile_to_agent():
    src = 'tcutils/fabfile.py'
    dst = '~/fabfile.py'
    if 'fab_copied_to_hosts' not in env.keys():
        env.fab_copied_to_hosts = list()
    if not env.host_string in env.fab_copied_to_hosts:
        if not exists(dst):
            put(src, dst)
        env.fab_copied_to_hosts.append(env.host_string)


def _escape_some_chars(text):
    chars = ['"', '=']
    for char in chars:
        text = text.replace(char, '\\\\' + char)
    return text
# end escape_chars


def run_fab_cmd_on_node(host_string, password, cmd, as_sudo=False, timeout=120, as_daemon=False, raw=False,
                        warn_only=True):
    """
    Run fab command on a node. Usecase : as part of script running on cfgm node, can run a cmd on VM from compute node

    If raw is True, will return the fab _AttributeString object itself without removing any unwanted output
    """
    cmd = _escape_some_chars(cmd)
    (username, host_ip) = host_string.split('@')
    copy_fabfile_to_agent()
    cmd_args = '-u %s -p "%s" -H %s -D --hide status,user,running' % (username,
                password, host_ip)
    if warn_only:
        cmd_args+= ' -w '
    cmd_str = 'fab %s ' % (cmd_args)
    if as_daemon:
        cmd_str += '--no-pty '
        cmd = 'nohup ' + cmd + ' &'
    if username == 'root':
        as_sudo = False
    elif username == 'cirros':
        cmd_str += ' -s "/bin/sh -l -c" '
    if as_sudo:
        cmd_str += 'sudo_command:\"%s\"' % (cmd)
    else:
        cmd_str += 'command:\"%s\"' % (cmd)
    # Sometimes, during bootup, there could be some intermittent conn. issue
    log.debug(cmd_str)
    tries = 1
    output = None
    while tries > 0:
        if timeout:
            try:
                output = sudo(cmd_str, timeout=timeout)
                log.debug(output)
            except CommandTimeout:
                return output
        else:
            output = run(cmd_str)
        if ((output) and ('Fatal error' in output)):
            tries -= 1
            time.sleep(5)
        else:
            break
    # end while

    if not raw:
        real_output = remove_unwanted_output(output)
    else:
        real_output = output
    return real_output
# end run_fab_cmd_on_node


def fab_put_file_to_vm(host_string, password, src, dest):
    copy_fabfile_to_agent()
    (username, host_ip) = host_string.split('@')
    cmd_str = 'fab -u %s -p "%s" -H %s -D -w --hide status,user,running fput:\"%s\",\"%s\"' % (
        username, password, host_ip, src, dest)
    log.debug(cmd_str)
    output = run(cmd_str)
    real_output = remove_unwanted_output(output)
# end fab_put_file_to_vm


def sshable(host_string, password=None, gateway=None, gateway_password=None):
    host_string_split = re.split(r"[@:]", host_string)
    host_port = host_string_split[2] if len(host_string_split) > 2 else '22'
    with hide('everything'), settings(host_string=gateway,
                                      password=gateway_password,
                                      warn_only=True):
        if run('nc -w 1 -z %s %s' % (host_string_split[1], host_port)).succeeded:
            try:
                run_cmd(host_string, 'uname', password, gateway,
                        gateway_password, timeout=10)
                return True
            except Exception as e:
                log.error("Error on ssh to %s" % host_string)
                log.debug(str(e))
                return False


def fab_check_ssh(host_string, password):
    copy_fabfile_to_agent()
    (username, host_ip) = host_string.split('@')
    cmd_str = 'fab -u %s -p "%s" -H %s -D -w --hide status,user,running verify_socket_connection:22' % (
        username, password, host_ip)
    log.debug(cmd_str)
    output = run(cmd_str)
    log.debug(output)
    if 'True' in output:
        return True
    return False
# end fab_check_ssh


def run_cmd_on_server(issue_cmd, server_ip, username,
                      password, pty=True, as_sudo=False):
    with hide('everything'):
        with settings(
            host_string='%s@%s' % (username, server_ip), password=password,
                warn_only=True, abort_on_prompts=False):
            if as_sudo:
                output = sudo('%s' % (issue_cmd), pty=pty)
            else:
                output = run('%s' % (issue_cmd), pty=pty)
            return output
# end run_cmd_on_server


def copy_file_to_server(host, src, dest, filename, force=False):

    fname = "%s/%s" % (dest, filename)
    with settings(host_string='%s@%s' % (host['username'],
                                         host['ip']), password=host['password'],
                  warn_only=True, abort_on_prompts=False):
        if not exists(fname) or force:
            time.sleep(random.randint(1, 10))
            put(src, dest)
# end copy_file_to_server

def get_host_domain_name(host):
    output = None
    with settings(hide('everything'), host_string='%s@%s' % (host['username'],
        host['ip']), password=host['password'],
        warn_only=True, abort_on_prompts=False):
        output = run('hostname -d')

    return output
# end get_host_domain_name


def get_build_sku(openstack_node_ip, openstack_node_password='c0ntrail123', user='root'):
    build_sku = get_os_env("SKU")
    if build_sku is not None:
        return str(build_sku).lower()
    else:
        host_str='%s@%s' % (user, openstack_node_ip)
        cmd = 'nova-manage version'
        tries = 10
        while not build_sku and tries:
            try:
                with hide('everything'), settings(host_string=host_str,
                                                  user=user,
                                                  password=openstack_node_password):
                    output = sudo(cmd)
                    build_sku = sku_dict[re.findall("[0-9]+.[0-9]+",output)[0]]
            except NetworkError, e:
                time.sleep(1)
                pass
            tries -= 1
        return build_sku
