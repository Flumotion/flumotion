# -*- Mode: Python; test-case-name: flumotion.test.test_http -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2004,2005,2006 Fluendo, S.L. (www.fluendo.com).
# All rights reserved.

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

from twisted.internet import reactor, error
from twisted.web import server

from flumotion.component import feedcomponent
from flumotion.common import bundle, common, gstreamer, errors, compat

# proxy import
from flumotion.component.component import moods
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

    def updateState(self, set):
        c = self
 
        bytes_sent      = c.getBytesSent()
        bytes_received  = c.getBytesReceived()
        uptime          = c.getUptime()

        set('stream-mime', c.get_mime())
        set('stream-uptime', common.formatTime(uptime))
        bitspeed = bytes_received * 8 / uptime
        set('stream-bitrate', common.formatStorage(bitspeed) + 'bit/s')
        set('stream-totalbytes', common.formatStorage(bytes_received) + 'Byte')
        set('stream-bitrate-raw', bitspeed)
        set('stream-totalbytes-raw', bytes_received)

        set('clients-current', str(c.getClients()))
        set('clients-max', str(c.getMaxClients()))
        set('clients-peak', str(c.getPeakClients()))
        set('clients-peak-time', c.getPeakEpoch())
        set('clients-average', str(int(c.getAverageClients())))

        bitspeed = bytes_sent * 8 / uptime
        set('consumption-bitrate', common.formatStorage(bitspeed) + 'bit/s')
        set('consumption-totalbytes', common.formatStorage(bytes_sent) + 'Byte')
        set('consumption-bitrate-raw', bitspeed)
        set('consumption-totalbytes-raw', bytes_sent)


class HTTPMedium(feedcomponent.FeedComponentMedium):
    def __init__(self, comp):
        """
        @type comp: L{Stats}
        """
        feedcomponent.FeedComponentMedium.__init__(self, comp)

        self.comp.connect('log-message', self._comp_log_message_cb)

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
    if gst.gst_version < (0, 9):
        pipe_template = 'multifdsink name=sink ' + \
                                    'buffers-max=500 ' + \
                                    'buffers-soft-max=250 ' + \
                                    'recover-policy=3'
    else:
        pipe_template = 'multifdsink name=sink ' + \
                                    'sync=false ' + \
                                    'buffers-max=500 ' + \
                                    'buffers-soft-max=250 ' + \
                                    'recover-policy=3'

    gsignal('client-removed', object, int, int, object)
    gsignal('log-message', str)
    
    component_medium_class = HTTPMedium

    def init(self):
        reactor.debug = True

        self.caps = None
        self.resource = None
        self.mountPoint = None
        self.port = None
        self.burst_on_connect = False

        # handle regular updating
        self.needsUpdate = False
        self._tenSecondCount = 10

        # handle added and removed queue
        self._added_lock = thread.allocate_lock()
        self._added_queue = []
        self._removed_lock = thread.allocate_lock()
        self._removed_queue = []

        for i in ('stream-mime', 'stream-uptime', 'stream-bitrate',
                  'stream-totalbytes', 'clients-current', 'clients-max',
                  'clients-peak', 'clients-peak-time', 'clients-average',
                  'consumption-bitrate', 'consumption-totalbytes',
                  'stream-bitrate-raw', 'stream-totalbytes-raw',
                  'consumption-bitrate-raw', 'consumption-totalbytes-raw'):
            self.uiState.addKey(i, None)

    def get_pipeline_string(self, properties):
        return self.pipe_template

    def configure_pipeline(self, pipeline, properties):
        Stats.__init__(self, sink=self.get_element('sink'))

        # FIXME: call self._callLaterId.cancel() somewhere on shutdown
        self._callLaterId = reactor.callLater(1, self._checkUpdate)

        # FIXME: do a .cancel on this Id somewhere
        self._queueCallLaterId = reactor.callLater(0.1, self._handleQueue)
        
        self._post_init(properties)

    def _post_init(self, properties):
        self.port = int(properties.get('port', 8800))
        mountPoint = properties.get('mount_point', '')
        if mountPoint.startswith('/'):
            mountPoint = mountPoint[1:]
        self.mountPoint = mountPoint

        # FIXME: tie these together more nicely
        self.resource = resources.HTTPStreamingResource(self)
        
        if properties.has_key('logfile'):
            file = properties['logfile']
            self.debug('Logging to %s' % file)
            try:
                self.resource.setLogfile(file)
            except IOError, data:
                raise errors.PropertiesError(
                    'could not open log file %s for writing (%s)' % (
                        file, data[1]))

        self.burst_on_connect = properties.get('burst_on_connect', False)

        if properties.has_key('user_limit'):
            self.resource.setUserLimit(int(properties['user_limit']))
            
        if properties.has_key('bouncer'):
            self.resource.setBouncerName(properties['bouncer'])

        if properties.has_key('domain'):
            self.resource.setDomain(properties['domain'])

        if self.config.has_key('avatarId'):
            self.resource.setRequesterName(self.config['avatarId'])

    def __repr__(self):
        return '<MultifdSinkStreamer (%s)>' % self.name

    # UI code
    def sendLog(self, message):
        self.emit('log-message', message)

    def _checkUpdate(self):
        self._tenSecondCount -= 1
        if self.needsUpdate or self._tenSecondCount <= 0:
            self._tenSecondCount = 10
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
        def set(k, v):
            if self.uiState.get(k) != v:
                self.uiState.set(k, v)
        # fixme: have updateState just update what changed itself
        # without the hack above
        self.updateState(set)

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
        # used to be commented out to see if it solves GIL problems
        stats = sink.emit('get-stats', fd)
        #stats = None
        self._removed_queue.append((sink, fd, reason, stats))
        self._removed_lock.release()

    ### END OF THREAD-AWARE CODE

    def link_setup(self, eaters, feeders):
        sink = self.get_element('sink')

        # check how to set client sync mode
        if gstreamer.element_factory_has_property('multifdsink', 'sync-method'):
            if self.burst_on_connect:
                sink.set_property('sync-method', 2)
            else:
                sink.set_property('sync-method', 0)
        else:
            # old property; does sync-to-keyframe
            sink.set_property('sync-clients', self.burst_on_connect)
            
        # FIXME: these should be made threadsafe if we use GstThreads
        sink.connect('deep-notify::caps', self._notify_caps_cb)

        if gst.gst_version < (0, 9):
            def sink_state_change_cb(element, old, state):
                # when our sink is PLAYING, then we are HAPPY
                # FIXME: add more moods
                if state == gst.STATE_PLAYING:
                    self.debug('Ready to serve clients')
                    self.setMood(moods.happy)

            sink.connect('state-change', sink_state_change_cb)

        # these are made threadsafe using idle_add in the handler
        sink.connect('client-removed', self._client_removed_cb)
        sink.connect('client-added', self._client_added_cb)

    def start(self, *args, **kwargs):
        root = resources.HTTPRoot()
        root.putChild(self.mountPoint, self.resource)
        
        self.debug('Listening on %d' % self.port)
        try:
            reactor.listenTCP(self.port, server.Site(resource=root))
            feedcomponent.ParseLaunchComponent.start(self, *args, **kwargs)
        except error.CannotListenError:
            self.warning('Port %d is not available.' % self.port)
            self.setMood(moods.sad)
            # FIXME: set message as well

compat.type_register(MultifdSinkStreamer)
