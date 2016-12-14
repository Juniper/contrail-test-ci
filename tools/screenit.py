#!/usr/bin/python
#
# Launch screen sessions for nodes in the cluster and vms
# 
# sshpass needs to be already installed on all the nodes in the cluster

import os
import sys
import json
import time
import argparse
from netaddr import *
from fabric.operations import local

from novaclient import client as nova_client

from common.contrail_test_init import ContrailTestInit
from tcutils.cfgparser import parse_cfg_file
from tcutils.agent.vna_introspect_utils import AgentInspect

SSHOPT = "-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null "
nc_h = None
inputs = None


def read_json_file(filename='sanity_testbed.json'):
    global host_data
    json_file = open(filename, 'r')
    json_data = json_file.read()
    host_data = json.loads(json_data)['hosts']

    for host in host_data:
        short_name = host['name'].split('.')[0]
        host_data[short_name] = host
        host['short_name'] = short_name


def get_nodes_with_role(role_name):
    nodes = []
    for host_ip in inputs.host_ips:
        host = inputs.host_data[host_ip]
        role_types = [x['type'] for x in host['roles']]
        if role_name in role_types:
            nodes.append(host)
    return nodes
# end


def launch_screen(screen_name, win_name):
    local('screen -S %s -X screen -t %s' % (screen_name, win_name))
    time.sleep(1)


def screen_it(screen_name, win_name, cmd, node_ip=None):
    if not node_ip:
        launch_screen(screen_name, win_name)
        local('screen -S %s -p %s -X stuff "%s\n"' %
              (screen_name, win_name, cmd))
    else:
        launch_screen(screen_name, win_name)
        password = inputs.host_data[node_ip]['password']
        username = inputs.host_data[node_ip]['username']
        cmd1 = 'sshpass -p %s ssh -t -t %s %s@%s' % (password, SSHOPT, username,
                                                     node_ip)
        local('screen -S %s -p %s -X stuff "%s\n"' %
              (screen_name, win_name, cmd1))
        time.sleep(1)
        local('screen -S %s -p %s -X stuff "%s\n"' %
              (screen_name, win_name, cmd))


def get_nova_h():
    global nc_h
    auth_url = inputs.auth_url or os.getenv('OS_AUTH_URL')
    password = inputs.admin_password or os.getenv('OS_PASSWORD')
    username = inputs.admin_username or os.getenv('OS_USERNAME')
    project_name = inputs.admin_tenant or os.getenv('OS_TENANT_NAME')
    insecure = os.getenv('OS_INSECURE', True)
    region_name = inputs.region_name or os.getenv('OS_REGION_NAME')
    nc_h = nova_client.Client('2',
                              username=username,
                              project_id=project_name,
                              api_key=password,
                              auth_url=auth_url,
                              insecure=insecure,
                              endpoint_type='publicURL',
                              region_name=region_name)
    import pdb; pdb.set_trace()
    return nc_h


def get_nova_vms():
    global nc_h
    if not nc_h:
        nc_h = get_nova_h()
    vms = nc_h.servers.list(search_opts={'all_tenants': 1})
    return vms


def get_nova_images():
    global nc_h
    if not nc_h:
        nc_h = get_nova_h()
    _images = nc_h.images.list()
    images = {}
    for image in _images:
        images[image.id] = image
    return images


def create_remote_screen(ip, screen_name):
    inputs.run_cmd_on_server(ip, 'screen -S %s -d -m -t %s' %
                             (screen_name, screen_name))


def get_vm_user_password(images, vm_obj):
    test_images_info = parse_cfg_file('configs/images.cfg')
    image_name = images[vm_obj.image['id']].name
    return (test_images_info[image_name]['username'],
            test_images_info[image_name]['password'])


def screen_node(screen_name):
    screen_str = 'screen -S %s -d -m -t %s' % (screen_name, screen_name)
    local(screen_str)
    tmp_var = "%w"
    local('screen -r %s -X hardstatus alwayslastline "%s"' % (screen_name,
                                                              tmp_var))
    time.sleep(1)
    local('screen -r %s -X defscrollback 30000' % (screen_name))
    time.sleep(1)

def cleanup_screens(screen_name):
    local('screen -X -S %s quit' % (screen_name))

def main():
    args_str = ' '.join(sys.argv[1:])
    args = _parse_args(args_str)
    global inputs
    inputs = ContrailTestInit('sanity_params.ini')
    # read_json_file('/tmp/sanity_testbed.json')
    nodes = {}
    roles = ['openstack', 'control', 'compute', 'cfgm', 'collector',
             'database']

    if args.cleanup:
        if not args.name:
            print 'Need the name of the screen to be cleaned'
            return
        cleanup_screens(args.name)
        return

    for role in roles:
        nodes[role] = get_nodes_with_role(role)

    if args.screen_type == 'nodes':
        screen1_name = args.name or 'nodes'
        screen_node(screen1_name)
    elif args.screen_type == 'vms':
        screen2_name = args.name or 'vms'
        screen_node(screen2_name)
    else:
        # Both screens
        screen1_name = 'nodes'
        screen2_name = 'vms'
        screen_node(screen1_name)
        screen_node(screen2_name)


    if args.screen_type != 'vms':
        for role in roles:
            for host in nodes[role]:
                if args.host and args.host.split('.')[0] != host['name']:
                    continue
                host_ip = str(IPNetwork(host['ip']).ip)
                host_name = host['name']
                username = host['username']
                password = host['password']
                cmd = 'sshpass -p %s ssh -t -t %s %s@%s' % (password, SSHOPT, username,
                                                            host_ip)
                win_name = '%s-%s' % (role, host_name)
                screen_it(screen1_name, win_name, cmd)

    if args.screen_type != 'nodes':
        # Launch a screen session vms on each compute node
        agent_inspect = {}
        for host in nodes['compute']:
            host_ip = str(IPNetwork(host['ip']).ip)
            short_name = host['name'].split('.')[0]
            agent_inspect[short_name] = AgentInspect(host_ip)

        vms = get_nova_vms()
        images = get_nova_images()

        for vm in vms:
            if vm.status != 'ACTIVE':
                continue
            short_name = getattr(
                vm, 'OS-EXT-SRV-ATTR:hypervisor_hostname').split('.')[0]
            if not short_name:
                continue
            if args.host and args.host.split('.')[0] != short_name:
                continue
            agent_inspect_h = agent_inspect[short_name]
            tap_intf = agent_inspect_h.get_vna_tap_interface_by_vm(vm.id)[0]
            vm_mdata_ip = tap_intf['mdata_ip_addr']
            (vm_user, vm_password) = get_vm_user_password(images, vm)
            cmd = 'sshpass -p %s ssh -t -t %s %s@%s' % (vm_password, SSHOPT, vm_user,
                                                        vm_mdata_ip)
            win_name = vm.name
            node_ip = inputs.host_data[short_name]['ip']
            screen_it(screen2_name, win_name, cmd, node_ip)


def _parse_args(args_str=None):
    description = '''
Screen launcher for nodes or vms in the cluster.
sshpass needs to be already present on this node and all compute nodes
'''
    parser = argparse.ArgumentParser(description=description)
    defaults = {
        'screen_type': 'all',
        'name': None,
        'host': None,
        'cleanup' : False,
    }
    parser.set_defaults(**defaults)
    parser.add_argument(
        '--screen_type', help='Type of screen(nodes/vms/all)', default='all')
    parser.add_argument(
        '--name', help='Name of the screen session, Default names are nodes/vms')
    parser.add_argument(
        '--host', help='Node short name for which screen sessions to be launched')
    parser.add_argument(
        '--cleanup', help='cleanup the named screen sessions', action='store_true')
    args = parser.parse_args(args_str.split())
    return args

if __name__ == "__main__":
    main()
