import os
import re
import yaml
import threading
from fabric.context_managers import settings
from tcutils.util import Singleton
from tcutils.cfgparser import parse_cfg_file

class NFSMgr:

   ''' NFS Manager

       Configures & Launches nfs-server on the specified node.

       Args:
         nfs - ip of node where nfs should be launched, default: cfgm
         nfs_path - nfs dir on the server
         name - identifier for the nfs instance
         hosts - list of hosts where nfs drive should be mounted
         get_fn
         create_fn
         delete_fn - orchestration specific handlers for get, create, and
                     delete
   '''

   __metaclass__ = Singleton

   def __init__ (self, inputs, get_fn, create_fn, delete_fn, hosts, logger,
                 nfs=None, nfs_path='/nfs', name='nfs-ds'):
       self.name = name
       self.nfs_path = nfs_path
       self._delete_fn = delete_fn
       self.nfs = nfs or inputs.cfgm_ip

       if get_fn(self.name):
           logger.debug('NFS %s already in system' % self.name)
           return

       logger.debug('NFS:%s [%s] on %s' % (self.name, self.nfs_path, self.nfs))
       username = inputs.host_data[self.nfs]['username']
       password = inputs.host_data[self.nfs]['password']
       with settings(host_string=username+'@'+self.nfs, password=password,
                     warn_only=True, shell='/bin/sh -l -c'):
           sudo('mkdir %s' % self.nfs_path)
           sudo('apt-get -y install nfs-kernel-server')
           sudo("sed -i '%s /d' /etc/exports" % self.nfs_path)
           sudo('echo "%s    *(rw,sync,no_root_squash)" >> /etc/exports' \
                % self.nfs_path)
           sudo('service nfs-kernel-server restart')

       loger.debug('NFS started, mounting the volume')
       self._objs = create_fn(rhost=self.nfs, rpath=self.nfs_path, lpath=name,
                              hosts=hosts)
       atexit.register(self.cleanUp)

   def cleanUp (self):
       self._delete_fn(self._objs)

class VlanMgr:

    ''' Virtual LAN Manager

        Manages allocation & deallocation of VLan Ids.

        Args:
          vlans - list of vlan to be managed
    '''

    __metaclass__ = Singleton

    def __init__ (self, vlans):
        self._vlans = vlans

    def allocate_vlan (self):
        return self._vlans.pop(0)

    def free_vlan (self, vlan):
        self._vlans.append(vlan)

class FlavorMgr:

   ''' Flavor Manager

       Manages addition of flavors to orchestration and caches the context
       returned by the orchestration specific handler.

       Args:
         loader_fn - orchestration specific handler
   '''

   __metaclass__ = Singleton

   def __init__ (self, loader_fn, logger):
       self.logger = logger
       self._loader = loader_fn
       self._lock = threading.Lock()
       cfg_file = os.getenv('FLAVOR_CFG_FILE', 'configs/flavors.cfg')
       self.logger.debug('Using flavor config from %s' % cfg_file)
       self.flavor_info = parse_cfg_file(cfg_file)

   def get_flavor (self, flavor):
       try:
           info = self.flavor_info[flavor]
       except KeyError as e:
           if 'contrail' not in flavor:
               # non-contrail system definied flavors are preloaded, just read
               self.flavor_info[flavor] = {}
               info = self.flavor_info[flavor]
           else:
               raise e

       try:
           return info['context']
       except KeyError:
           with self._lock:
               info['context'] = self._loader(name=flavor, **info)
               return info['context']

class ImageMgr:

   ''' Image Manager

       Manages addition of vm-images to orchestration and caches the objects.

       Args:
         loader_fn - orchestration specific handler
   '''

   __metaclass__ = Singleton

   def __init__ (self, loader_fn, logger):
       self.logger = logger
       self._loader = loader_fn
       self._lock = threading.Lock()
       cfg_file = os.getenv('IMAGE_CFG_FILE', 'configs/images.yaml')
       self.logger.debug('Using image config from %s' % cfg_file)
       self._images_info = yaml.load(open(cfg_file))

   def _resolve (self, ns, name):
       ns_info = self._images_info
       try:
           for i in ns.split(':'):
               ns_info = ns_info[ns]
           try:
               img_info = ns_info[name]
               try:
                   tgt_ns, tgt_name = img_info['ref'].split('/')
                   return self._resolve(tgt_ns, tgt_name)
               except KeyError:
                   return img_info
           except KeyError:
               raise NameError('No Image entry %s in %s' % (name, ns))
       except KeyError:
           raise Exception('No namespace %s' % ns)

   def get_image_account (self, ns, img):
       img_info = self._resolve(ns, img)
       return img_info['username'], img_info['password']

   def get_image_flavor (self, ns, img):
       img_info = self._resolve(ns, img)
       return img_info.get('flavor', None)

   def get_image (self, ns, img):
       img_info = self._resolve(ns, img)
       #TODO global lock could be a bottleneck, if so, redo image level lock
       with self._lock:
           try:
               return img_info['context']
           except KeyError:
               img_info['context'] = self._loader(ns, img_info,
                                           self._get_image_url(img_info))
               return img_info['context']

   def _get_image_url (self, img_info):
        webserver = img_info.get('webserver', None)
        webserver = webserver or os.getenv('IMAGE_WEB_SERVER', '10.204.216.50')
        location = img_info['location']
        image = img_info['file']
        test_dir = os.path.realpath(os.path.join(os.path.dirname(\
                       os.path.realpath(__file__)),'..'))
        if test_dir and os.path.isfile("%s/images/%s" % (test_dir, image)):
            url = "file://%s/images/%s" % (test_dir, image)
        elif re.match(r'^file://', location):
            url = '%s/%s' % (location, image)
        else:
            url = 'http://%s/%s/%s' % (webserver, location, image)
        return url

class RoundRobin (object):

   def set_zones_and_hosts (self, zones, hosts):

       ''' Sets up the zones & hosts on which to RoundRobin

           Args:
           zones - dict of zones, example,
                   { 'zone-1': { 'hosts': [<list of hosts>] },
                     'zone-2': { 'hosts': [<list of hosts>] },
                     ...
                   }
           hosts - dict of all the hosts in the setup, example,
                   { 'host-1': {...},
                     'host-2': {...},
                     ...
                   }
       '''

       self._zones = zones
       self._hosts = hosts
       self._rr_zone = self._next_zone()
       self._rr_host = {}
       for c in self._zones:
           self._rr_host[c] = self._next_host(c)

   def _next_zone (self):
       while True:
           for zone in self._zones:
               yield zone

   def _next_host (self, zone):
       while True:
           for host in self._zones[zone]['hosts']:
               yield host

   def _find_host_zone (self, host):
       for c in self._zones:
           if host in self._zones[c]['hosts']:
               return c

   def __len__ (self):
       return len(self._zones)

   def next (self, zone=None):
       c = zone if zone else next(self._rr_zone)
       return c, next(self._rr_host[c])

class RoundRobinZoneRestricted (RoundRobin):

   def __init__ (self, zone):
       self._restrict_zone = zone

   def set_zones_and_hosts (self, zones, hosts):
       zone = {self._restrict_zone: {'hosts': zones[self._restrict_zone]}}
       host = {}
       for h in zones[self._restrict_zone]['hosts']:
           host[h] = hosts[h]
       super(RoundRobinZoneRestricted, self).set_zones_and_hosts(zone, host)
