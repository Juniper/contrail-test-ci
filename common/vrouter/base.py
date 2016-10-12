from common.neutron.base import BaseNeutronTest
from tcutils.agent.vrouter_lib import *
from tcutils.util import retry


class BaseVrouterTest(BaseNeutronTest):

    @classmethod
    def setUpClass(cls):
        super(BaseVrouterTest, cls).setUpClass()
    # end setUpClass

    @classmethod
    def tearDownClass(cls):
        super(BaseVrouterTest, cls).tearDownClass()
    # end tearDownClass

    def get_vrouter_route(self, prefix, vn_fixture=None, vrf_id=None,
                          inspect_h=None, node_ip=None):
        ''' prefix is in the form of ip/mask
        '''
        if not (vn_fixture or vrf_id):
            self.logger.debug('get_vrouter_route required atleast one of '
                              'VN Fixture or vrf id')
            return None
        if not (inspect_h or node_ip):
            self.logger.debug('get_vrouter_route needs one of inspect_h '
                              ' or node_ip')
            return None

        #vrf_id = vrf_id or vn_fixture.get_vrf_id(node_ip, refresh=True)
        inspect_h = inspect_h or self.agent_inspect_h[node_ip]
        vrf_id = vrf_id or inspect_h.get_vna_vrf_id(vn_fixture.vn_fq_name)[0]
        (prefix_ip, mask) = prefix.split('/')
        route = inspect_h.get_vrouter_route_table(vrf_id, prefix=prefix_ip,
                                                  prefix_len=mask,
                                                  get_nh_details=True)
        if len(route) > 0:
            return route[0]
    # end get_vrouter_route

    def get_vrouter_route_table(self, node_ip, vn_fixture=None, vrf_id=None):
        if not (vn_fixture or vrf_id):
            self.logger.debug('get_vrouter_route_table required atleast one of'
                              ' VN Fixture or vrf id')
            return None
        if not vrf_id:
            vrf_id = vn_fixture.get_vrf_id(node_ip)
        inspect_h = self.agent_inspect_h[node_ip]
        routes = inspect_h.get_vrouter_route_table(vrf_id)
        return routes
    # end get_vrouter_route_table

    def get_vrouter_route_table_size(self, *args, **kwargs):
        routes = self.get_vrouter_route_table(*args, **kwargs)
        self.logger.debug('Route table size : %s' % (len(routes)))
        return len(routes)
    # end get_vrouter_route_table_size

    @retry(delay=1, tries=5)
    def validate_prefix_is_of_vm_in_vrouter(self, inspect_h, prefix,
                                            vm_fixture, vn_fixture=None):
        '''
        '''
        vrf_id = None
        if not vn_fixture:
            vrf_id = inspect_h.get_vna_vrf_id(vm_fixture.vn_fq_names[0])[0]
        route = self.get_vrouter_route(prefix,
                                       vn_fixture=vn_fixture, vrf_id=vrf_id, inspect_h=inspect_h)
        if not route:
            self.logger.debug('No route seen in vrouter for %s' % (prefix))
            return False
        return self.validate_route_is_of_vm_in_vrouter(
            inspect_h,
            route,
            vm_fixture,
            vn_fixture)
    # end validate_prefix_is_of_vm_in_vrouter

    @retry(delay=3, tries=3)
    def validate_route_is_of_vm_in_vrouter(self, inspect_h, route, vm_fixture,
                                           vn_fixture=None):
        '''Validation is in vrouter
            Recommended to do verify_on_setup() on vm_fixture before calling
            this method
        '''
        result = False
        vm_intf = None
        # Get the VM tap interface to be validated
        vm_tap_intfs = vm_fixture.get_tap_intf_of_vm()
        if not vn_fixture:
            vm_intf = vm_fixture.get_tap_intf_of_vm()[0]
        else:
            for vm_tap_intf in vm_tap_intfs:
                if vm_tap_intf['vn_name'] == vn_fixture.vn_fq_name:
                    vm_intf = vm_tap_intf.copy()
            if not vm_intf:
                self.logger.debug('VM %s did not have any intf in VN %s' % (
                    vm_fixture.vm_name, vn_fixture.vn_name))
                return False

        if not (vm_intf and vm_fixture.vm_node_ip):
            self.logger.warn('Cannot check routes without enough VM details')
            return False

        result = validate_route_in_vrouter(route, inspect_h, vm_intf['name'],
                                           vm_fixture.vm_node_ip, vm_intf['label'], self.logger)
        return result
    # end validate_route_is_of_vm_in_vrouter

    def count_nh_label_in_route_table(self, node_ip, vn_fixture, nh_id, label):
        '''
        Count the number of times nh_id,label is a nh in vrouter's route table
        '''
        route_table = self.get_vrouter_route_table(node_ip,
                                                   vn_fixture=vn_fixture)
        count = 0
        for rt in route_table:
            if rt['nh_id'] == str(nh_id) and rt['label'] == str(label):
                count += 1
        return count
    # end count_nh_label_in_route_table

    @retry(delay=2, tries=5)
    def validate_discard_route(self, prefix, vn_fixture, node_ip):
        '''
        Validate that route for prefix in vrf of a VN is  pointing to a discard
        route on compute node node_ip
        '''
        route = self.get_vrouter_route(prefix,
                                       vn_fixture=vn_fixture,
                                       node_ip=node_ip)
        if not route:
            self.logger.warn('No vrouter route for prefix %s found' % (prefix))
            return False
        if not (route['label'] == '0' and route['nh_id'] == '1'):
            self.logger.warn('Discard route not set for prefix %s' % (prefix))
            self.logger.debug('Route seen is %s' % (route))
            return False
        self.logger.info('Route for prefix %s is validated to be discard'
                         ' route' %(prefix))
        return True
    # end validate_discard_route
