# -*- Mode: Python; test-case-name: flumotion.test.test_http -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# flumotion/component/consumers/httpstreamer/httpstreamer.py
# a consumer that streams over HTTP
#
# Flumotion - a streaming media server
# Copyright (C) 2004,2005 Fluendo, S.L. (www.fluendo.com). All rights reserved.

# This file may be distributed and/or modified under the terms of
# the GNU General Public License version 2 as published by
# the Free Software Foundation.
# This file is distributed without any warranty; without even the implied
# warranty of merchantability or fitness for a particular purpose.
# See "LICENSE.GPL" in the source distribution for more information.

# Licensees having purchased or holding a valid Flumotion Advanced
# Streaming Server license may use this file in accordance with the
# Flumotion Advanced Streaming Server Commercial License Agreement.
# See "LICENSE.Flumotion" in the source distribution for more information.

# Headers in this file shall remain intact.

import time
import thread

import gobject
import gst

from twisted.internet import reactor
from twisted.web import server

from flumotion.component import feedcomponent
from flumotion.common import bundle, common, gstreamer

from flumotion.common.component import moods
from flumotion.common.pygobject import gsignal

from flumotion.component.consumers.httpstreamer import resources

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
            dt = dt1 + dt2
            before = (dc1 * dt1) / dt
            after =  dc2 * dt2 / dt
            self.average_client_number = before + after

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
        self.comp.connect('log-message', self._comp_log_message_cb)

    def getState(self):
        return self.comp.getState()

    # FIXME: decide on "state", "stats", or "statistics"
    def _comp_ui_state_changed_cb(self, comp):
        self.callRemote('adminCallRemote', 'statsChanged', self.getState())

    def _comp_log_message_cb(self, comp, message):
        self.callRemote('adminCallRemote', 'logMessage', message)

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

    ### remote methods for manager to call on
    def remote_expireKeycard(self, keycardId):
        self.comp.resource.expireKeycard(keycardId)

    def remote_notifyState(self):
        self.comp.update_ui_state()


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
    gsignal('log-message', str)
    
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
        return '<MultifdSinkStreamer (%s)>' % self.name

    # UI code
    def sendLog(self, message):
        self.emit('log-message', message)

    def _checkUpdate(self):
        if self.needsUpdate:
            self.needsUpdate = False
            self.update_ui_state()
        self._callLaterId = reactor.callLater(1, self._checkUpdate)

    def getMaxClients(self):
        return self.resource.maxAllowedClients()

    def _notify_caps_cb(self, element, pad, param):
        caps = pad.get_negotiated_caps()
        if caps == None:
            return
        
        caps_str = gstreamer.caps_repr(caps)
        self.debug('Got caps: %s' % caps_str)
        
        if not self.caps == None:
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

        # handle added clients; added first because otherwise removed fd's
        # are re-used before we handle added
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
        self.log('[fd %5d] client_added_handler from thread %d' % 
            (fd, thread.get_ident())) 
        Stats.clientAdded(self)
        # FIXME: GIL problem, don't update UI for now
        self.needsUpdate = True
        #self.update_ui_state()
        
    def _client_removed_handler(self, sink, fd, reason, stats):
        self.log('[fd %5d] client_removed_handler from thread %d, reason %s' %
            (fd, thread.get_ident(), reason)) 
        if reason.value_name == 'GST_CLIENT_STATUS_ERROR':
            self.warning('[fd %5d] Client removed because of write error' % fd)
        if reason.value_name == 'GST_CLIENT_STATUS_DUPLICATE':
            # a _removed because of DUPLICATE never had the _added signaled
            # in the first place, so we shouldn't update stats for it and just
            # fughedaboudit
            self.warning('[fd %5d] Client refused because the same fd is already registered' % fd)
            return

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

    def _sink_state_change_cb(self, element, old, state):
        # when our sink is PLAYING, then we are HAPPY
        # FIXME: add more moods
        if state == gst.STATE_PLAYING:
            self.debug('Ready to serve clients')
            self.setMood(moods.happy)

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

    return component
