# -*- Mode: Python; test-case-name: flumotion.test.test_http -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# flumotion/component/http/http.py: a consumer that streams over HTTP
# Flumotion - a streaming media server
# Copyright (C) 2004 Fluendo (www.fluendo.com)

# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
# See "LICENSE.GPL" in the source distribution for more information.

# This program is also licensed under the Flumotion license.
# See "LICENSE.Flumotion" in the source distribution for more information.

import os
import time
import thread

import gobject
import gst

from twisted.internet import reactor
from twisted.web import server

from flumotion.component import feedcomponent
from flumotion.common import bundle, common
from flumotion.utils import gstutils
from flumotion.utils.gstutils import gsignal

from flumotion.component.http import resources

__all__ = ['HTTPMedium', 'MultifdSinkStreamer']
    
# FIXME: generalize this class and move it out here ?
class Stats:
    def __init__(self, sink):
        self.sink = sink
        
        self.no_clients = 0        
        self.start_time = time.time()
        # keep track of the highest number and the last epoch this was reached
        self.peak_client_number = 0 
        self.peak_epoch = self.start_time

        # keep track of average clients by tracking last average and its time
        self.average_client_number = 0
        self.average_time = self.start_time
        
    def _updateAverage(self):
        # update running average of clients connected
        now = time.time()
        # calculate deltas
        dt1 = self.average_time - self.start_time
        dc1 = self.average_client_number
        dt2 = now - self.average_time
        dc2 = self.no_clients
        self.average_time = now # we can update now that we used self.av
        if dt1 == 0:
            # first measurement
            self.average_client_number = 0
        else:
            self.average_client_number = (dc1 * dt1 / (dt1 + dt2) +
                                          dc2 * dt2 / (dt1 + dt2))

    def clientAdded(self):
        self._updateAverage()

        self.no_clients += 1

        # >= so we get the last epoch this peak was achieved
        if self.no_clients >= self.peak_client_number:
            self.peak_epoch = time.time()
            self.peak_client_number = self.no_clients
    
    def clientRemoved(self):
        self._updateAverage()
        self.no_clients -= 1

    def getBytesSent(self):
        return self.sink.get_property('bytes-served')
    
    def getBytesReceived(self):
        return self.sink.get_property('bytes-to-serve')
    
    def getUptime(self):
        return time.time() - self.start_time
    
    def getClients(self):
        return self.no_clients
    
    def getPeakClients(self):
        return self.peak_client_number

    def getPeakEpoch(self):
        return self.peak_epoch
    
    def getAverageClients(self):
        return self.average_client_number

    def getState(self):
        c = self
        s = {}
 
        bytes_sent      = c.getBytesSent()
        bytes_received  = c.getBytesReceived()
        uptime          = c.getUptime()

        s['stream-mime'] = c.get_mime()
        s['stream-uptime'] = common.formatTime(uptime)
        bitspeed = bytes_received * 8 / uptime
        s['stream-bitrate'] = common.formatStorage(bitspeed) + 'bit/s'
        s['stream-totalbytes'] = common.formatStorage(bytes_received) + 'Byte'

        s['clients-current'] = str(c.getClients())
        s['clients-max'] = str(c.getMaxClients())
        s['clients-peak'] = str(c.getPeakClients())
        s['clients-peak-time'] = time.ctime(c.getPeakEpoch())
        s['clients-average'] = str(int(c.getAverageClients()))

        bitspeed = bytes_sent * 8 / uptime
        s['consumption-bitrate'] = common.formatStorage(bitspeed) + 'bit/s'
        s['consumption-totalbytes'] = common.formatStorage(bytes_sent) + 'Byte'

        return s

class HTTPMedium(feedcomponent.FeedComponentMedium):
    def __init__(self, comp):
        """
        @type comp: L{Stats}
        """
        feedcomponent.FeedComponentMedium.__init__(self, comp)

        self.comp.connect('ui-state-changed', self._comp_ui_state_changed_cb)

    def getState(self):
        return self.comp.getState()

    def _comp_ui_state_changed_cb(self, comp):
        self.callRemote('uiStateChanged', self.comp.get_name(), self.getState())

    def authenticate(self, bouncerName, keycard):
        """
        @rtype: L{twisted.internet.defer.Deferred}
        """
        return self.callRemote('authenticate', bouncerName, keycard)

    def removeKeycard(self, bouncerName, keycardId):
        """
        @rtype: L{twisted.internet.defer.Deferred}
        """
        return self.callRemote('removeKeycard', bouncerName, keycardId)

    def remote_expireKeycard(self, keycardId):
        self.comp.expireKeycard(keycardId)

### the actual component is a streamer using multifdsink
class MultifdSinkStreamer(feedcomponent.ParseLaunchComponent, Stats):
    # this object is given to the HTTPMedium as comp
    logCategory = 'cons-http'
    # use select for test
    pipe_template = 'multifdsink name=sink ' + \
                                'buffers-max=500 ' + \
                                'buffers-soft-max=250 ' + \
                                'sync-clients=TRUE ' + \
                                'recover-policy=3'

    gsignal('client-removed', object, int, int, object)
    gsignal('ui-state-changed')
    
    component_medium_class = HTTPMedium

    def __init__(self, name, source):
        feedcomponent.ParseLaunchComponent.__init__(self, name, [source], [],
                                                    self.pipe_template)
        Stats.__init__(self, sink=self.get_element('sink'))
        self.caps = None
        self.resource = None

        # handled regular updating
        self.needsUpdate = False
        # FIXME: call self._callLaterId.cancel() somewhere on shutdown
        self._callLaterId = reactor.callLater(1, self._checkUpdate)

        # handle added and removed queue
        self._added_lock = thread.allocate_lock()
        self._added_queue = []
        self._removed_lock = thread.allocate_lock()
        self._removed_queue = []
        # FIXME: do a .cancel on this Id somewhere
        self._queueCallLaterId = reactor.callLater(0.1, self._handleQueue)
        
    def __repr__(self):
        return '<MultifdSinkStreamer (%s)>' % self.component_name

    # UI code
    def _checkUpdate(self):
        if self.needsUpdate == True:
            self.needsUpdate = False
            self.update_ui_state()
        self._callLaterId = reactor.callLater(1, self._checkUpdate)

    def getMaxClients(self):
        return self.resource.maxAllowedClients()

    def remote_notifyState(self):
        self.update_ui_state()

    def _notify_caps_cb(self, element, pad, param):
        caps = pad.get_negotiated_caps()
        if caps is None:
            return
        
        caps_str = gstutils.caps_repr(caps)
        self.debug('Got caps: %s' % caps_str)
        
        if not self.caps is None:
            self.warning('Already had caps: %s, replacing' % caps_str)

        self.debug('Storing caps: %s' % caps_str)
        self.caps = caps
        
        self.update_ui_state()
        
    def get_mime(self):
        if self.caps:
            return self.caps.get_structure(0).get_name()

    def get_content_type(self):
        mime = self.get_mime()
        if mime == 'multipart/x-mixed-replace':
            mime += ";boundary=ThisRandomString"
        return mime
    
    def add_client(self, fd):
        sink = self.get_element('sink')
        sink.emit('add', fd)

    def remove_client(self, fd):
        sink = self.get_element('sink')
        sink.emit('remove', fd)

    def update_ui_state(self):
        self.emit('ui-state-changed')

    # handle the thread deserializing queues
    def _handleQueue(self):

        # handle added clients
        self._added_lock.acquire()

        while self._added_queue:
            (sink, fd) = self._added_queue.pop()
            self._added_lock.release()
            self._client_added_handler(sink, fd)
            self._added_lock.acquire()

        self._added_lock.release()

        # handle removed clients
        self._removed_lock.acquire()

        while self._removed_queue:
            (sink, fd, reason, stats) = self._removed_queue.pop()
            self._removed_lock.release()
            self._client_removed_handler(sink, fd, reason, stats)
            self._removed_lock.acquire()

        self._removed_lock.release()
         
        self._queueCallLaterId = reactor.callLater(0.1, self._handleQueue)

    def _client_added_handler(self, sink, fd):
        self.log('[%5d] client_added_handler from thread %d' % 
            (fd, thread.get_ident())) 
        Stats.clientAdded(self)
        # FIXME: GIL problem, don't update UI for now
        self.needsUpdate = True
        #self.update_ui_state()
        
    def _client_removed_handler(self, sink, fd, reason, stats):
        self.log('[fd %5d] client_removed_handler from thread %d, reason %s' %
            (fd, thread.get_ident(), reason)) 
        # Johan will trap GST_CLIENT_STATUS_ERROR here someday
        # because STATUS_ERROR seems to have already closed the fd somewhere
        self.emit('client-removed', sink, fd, reason, stats)
        Stats.clientRemoved(self)
        # FIXME: GIL problem, don't update UI for now
        self.needsUpdate = True
        #self.update_ui_state()

    ### START OF THREAD-AWARE CODE

    # this can be called from both application and streaming thread !
    def _client_added_cb(self, sink, fd):
        self._added_lock.acquire()
        self._added_queue.append((sink, fd))
        self._added_lock.release()

    # this can be called from both application and streaming thread !
    def _client_removed_cb(self, sink, fd, reason):
        self._removed_lock.acquire()
        # commented out to see if it solves GIL problems
        #stats = sink.emit('get-stats', fd)
        stats = None
        self._removed_queue.append((sink, fd, reason, stats))
        self._removed_lock.release()

    ### END OF THREAD-AWARE CODE

    # FIXME: a streamer doesn't have feeders, so shouldn't call the base
    # method; right now this is done so the manager knows it started.
    # fix this by implementing concept of "moods" for components
    def _sink_state_change_cb(self, element, old, state):
        feedcomponent.FeedComponent.feeder_state_change_cb(self, element,
                                                     old, state, '')
        if state == gst.STATE_PLAYING:
            self.debug('Ready to serve clients')

    def link_setup(self, eaters, feeders):
        sink = self.get_element('sink')
        # FIXME: these should be made threadsafe if we use GstThreads
        sink.connect('deep-notify::caps', self._notify_caps_cb)
        sink.connect('state-change', self._sink_state_change_cb)
        # these are made threadsafe using idle_add in the handler
        sink.connect('client-removed', self._client_removed_cb)
        sink.connect('client-added', self._client_added_cb)

gobject.type_register(MultifdSinkStreamer)

### create the component based on the config file
def createComponent(config):
    reactor.debug = True

    name = config['name']
    source = config['source']
    port = int(config['port'])
    mount_point = config.get('mount_point', '')
    
    component = MultifdSinkStreamer(name, source)
    resource = resources.setup(component, port, mount_point)

    # FIXME: tie these together more nicely
    component.resource = resource
    
    if config.has_key('logfile'):
        component.debug('Logging to %s' % config['logfile'])
        resource.setLogfile(config['logfile'])

    if config.has_key('maxclients'):
        resource.setMaxClients(int(config['maxclients']))
        
    if config.has_key('admin-password'):
        resource.setAdminPassword(config['admin-password'])

    if config.has_key('bouncer'):
        resource.setBouncerName(config['bouncer'])

    # create bundlers for UI
    # FIXME: make it so the bundles extract in the full path
    # for later when we transmit everything they depend on
    bundler = bundle.Bundler()
    # where do we live ?
    directory = os.path.split(__file__)[0]
    bundler.add(os.path.join(directory, 'gtk.py'))
    bundler.add(os.path.join(directory, 'http.glade'))
    component.addUIBundler(bundler, "admin", "gtk")
    
    return component
