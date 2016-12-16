#TODO: this module replaces control_node.py
from contrail_fixtures import ContrailFixture
from tcutils.util import retry
from vnc_api.vnc_api import BgpRouter

class BgpRouterFixture (ContrailFixture):

   vnc_class = BgpRouter

   def __init__ (self, connections, uuid=None, params=None, fixs=None):
       super(BgpRouterFixture, self).__init__(
           uuid=uuid,
           connections=connections,
           params=params,
           fixs=fixs)
       self.cn_inspect = self.connections.cn_inspect

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
       obj = self._vnc.get_bgp_router(self.uuid)
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
       self.uuid = self._ctrl.create_bgp_router(
           **self._args)

   def _delete (self):
       self.logger.info('Deleting %s' % self)
       self._ctrl.delete_bgp_router(
           obj=self._obj, uuid=self.uuid)

   def _update (self):
       self.logger.info('Updating %s' % self)
       self._ctrl.update_bgp_router(
           obj=self._obj, uuid=self.uuid, **self.args)

   def verify_on_setup (self):
       self.assert_on_setup(*self._verify_in_api_server())
       self.assert_on_setup(*self._verify_peer_in_control_nodes())
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
       if self._vnc.get_bgp_router(self.uuid):
           msg = '%s not removed from api-server' % self
           self.logger.debug(msg)
           return False, msg
       self.logger.debug('%s removed from api-server' % self)
       return True, None

   @retry(delay=5, tries=6)
   def _verify_peer_in_control_nodes (self):
       for entry1 in self.inputs.bgp_ips:
           cn_bgp_entry = self.cn_inspect[entry1].get_cn_bgp_neigh_entry(
                                                          encoding='BGP')
           if not cn_bgp_entry:
               return False, '%s does not have any BGP Peer' % entry1

           for entry in cn_bgp_entry:
               if entry['state'] != 'Established':
                   msg = 'Peering is not Established with Peer %s [%s]' % (
                          entry['peer'], entry['state'])
                   return False, msg
               self.logger.debug('Peering with Peer %s is %s' % (entry['peer'],
                                  entry['state']))
       return True, None
