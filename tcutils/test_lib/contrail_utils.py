'''
Contrail feature specific utility methods
'''
import threading
from netaddr import *

from tcutils.util import Lock

def get_ri_name(vn_fq_name):
    '''
    Return RI name given a VN fq name
    vn_fq_name can be a list or a string(colon separated)
    '''
    if type(vn_fq_name) == list:
        vn_name = vn_fq_name[-1]
        return vn_fq_name + vn_name
    else:
        vn_name = vn_fq_name.split(':')[-1]
        return vn_fq_name + ':' + vn_name
# end get_ri_name

def get_interested_computes(connections, vn_fq_names=[]):
    '''
    Returns a list of compute node ips interested in one or more VNs
    '''
    peers = []
    inputs = connections.inputs
    for control_node in inputs.bgp_ips:
        for vn_fq_name in vn_fq_names:
            inspect_h = connections.cn_inspect[control_node]
            peers.extend(inspect_h.get_cn_ri_membership(vn_fq_name=vn_fq_name))

    # peers can include control-only nodes, we need only compute
    computes = list(set(peers) & \
                    set(inputs.compute_names))
    interested_computes = [self.inputs.host_data[x]['host_ip'] \
                                 for x in computes ]
    return interested_computes
# end get_interested_computes

def get_free_ips(cidr, vnc_api_h, vn_id, count=1):
    '''
    Returns a list of IPAddress objects

    Get one or more free IPs from a CIDR in a VN (as seen by contrail-api)
    Note that this helps only in contrail test environment

    You may also want to use tcutils.util.get_lock() along with this
    '''
    vn_obj = vnc_api_h.virtual_network_read(id=vn_id)
    available_ips = list(IPNetwork(cidr).iter_hosts())
    ip_uuids = [x['uuid'] for x in vn_obj.get_instance_ip_back_refs() or []]
    for x in ip_uuids:
        ip_obj = vnc_api_h.instance_ip_read(id=x)
        available_ips.remove(IPAddress(ip_obj.instance_ip_address))
    if available_ips:
        return available_ips[:count]
    else:
        return None
# end get_free_ips
