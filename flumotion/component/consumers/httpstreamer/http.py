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

# socket needed to get hostname
import socket

from twisted.internet import reactor, error, defer
from twisted.web import server
from twisted.cred import credentials

from flumotion.component import feedcomponent
from flumotion.common import bundle, common, gstreamer, errors, pygobject
from flumotion.common import messages, netutils, log

from flumotion.twisted import fdserver
from flumotion.component.misc.porter import porterclient

# proxy import
from flumotion.component.component import moods
from flumotion.common.pygobject import gsignal

from flumotion.component.consumers.httpstreamer import resources
from flumotion.component.base import http

from flumotion.common.messages import N_
T_ = messages.gettexter('flumotion')

__all__ = ['HTTPMedium', 'MultifdSinkStreamer']
    
# FIXME: generalize this class and move it out here ?
class Stats:
    def __init__(self, sink):
        self.sink = sink
        
        self.no_clients = 0        
        self.clients_added_count = 0
        self.clients_removed_count = 0
        self.start_time = time.time()
        # keep track of the highest number and the last epoch this was reached
        self.peak_client_number = 0 
        self.peak_epoch = self.start_time
        self.load_deltas = [0, 0]
        self._load_deltas_period = 10 # seconds
        self._load_deltas_ongoing = [time.time(), 0, 0]

        # keep track of average clients by tracking last average and its time
        self.average_client_number = 0
        self.average_time = self.start_time

        self.hostname = "localhost"
        self.port = 0
        self.mountPoint = "/"
        
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
        self.clients_added_count +=1

        # >= so we get the last epoch this peak was achieved
        if self.no_clients >= self.peak_client_number:
            self.peak_epoch = time.time()
            self.peak_client_number = self.no_clients
    
    def clientRemoved(self):
        self._updateAverage()
        self.no_clients -= 1
        self.clients_removed_count +=1

    def updateLoadDeltas(self):
        oldtime, oldadd, oldremove = self._load_deltas_ongoing
        add, remove = self.clients_added_count, self.clients_removed_count
        now = time.time()
        diff = float(now - oldtime)
            
        # we can be called very often, but only update the loaddeltas
        # once every period
        if diff > self._load_deltas_period:
            self.load_deltas = [(add-oldadd)/diff, (remove-oldremove)/diff]
            self._load_deltas_ongoing = [now, add, remove]

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

    def getUrl(self):
        return "http://%s:%d%s" % (self.hostname, self.port, self.mountPoint) 

    def getLoadDeltas(self):
        return self.load_deltas

    def updateState(self, set):
        c = self
 
        bytes_sent      = c.getBytesSent()
        bytes_received  = c.getBytesReceived()
        uptime          = c.getUptime()

        set('stream-mime', c.get_mime())
        set('stream-url', c.getUrl())
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

    def authenticate(self, bouncerName, keycard):
        """
        @rtype: L{twisted.internet.defer.Deferred} firing a keycard or None.
        """
        d = self.callRemote('authenticate', bouncerName, keycard)
        d.addErrback(log.warningFailure)
        return d

    def removeKeycardId(self, bouncerName, keycardId):
        """
        @rtype: L{twisted.internet.defer.Deferred}
        """
        return self.callRemote('removeKeycardId', bouncerName, keycardId)

    ### remote methods for manager to call on
    def remote_expireKeycard(self, keycardId):
        self.comp.resource.expireKeycard(keycardId)

    def remote_notifyState(self):
        self.comp.update_ui_state()

    def remote_rotateLog(self):
        self.comp.resource.rotateLogs()

    def remote_getStreamData(self):
        return self.comp.getStreamData()

    def remote_getLoadData(self):
        return self.comp.getLoadData()

    def remote_updatePorterDetails(self, path, username, password):
        return self.comp.updatePorterDetails(path, username, password)

### the actual component is a streamer using multifdsink
class MultifdSinkStreamer(feedcomponent.ParseLaunchComponent, Stats):
    # this object is given to the HTTPMedium as comp
    logCategory = 'cons-http'
    
    pipe_template = 'multifdsink name=sink ' + \
                                'sync=false ' + \
                                'recover-policy=3'
    gsignal('client-removed', object, int, int, object)
    
    componentMediumClass = HTTPMedium

    def init(self):
        reactor.debug = True
        self.debug("HTTP streamer initialising")

        self.caps = None
        self.resource = None
        self.mountPoint = None
        self.burst_on_connect = False

        self.description = None

        self.type = None

        # Used if we've slaved to a porter.
        self._pbclient = None
        self._porterUsername = None
        self._porterPassword = None
        self._porterPath = None

        # Or if we're a master, we open our own port here. Also used for URLs
        # in the porter case.
        self.port = None
        # We listen on this interface, if set.
        self.iface = None

        # handle regular updating
        self.needsUpdate = False
        self._tenSecondCount = 10

        # handle added and removed queue
        self._added_lock = thread.allocate_lock()
        self._added_queue = []
        self._removed_lock = thread.allocate_lock()
        self._removed_queue = []

        self._pending_removals = {}

        for i in ('stream-mime', 'stream-uptime', 'stream-bitrate',
                  'stream-totalbytes', 'clients-current', 'clients-max',
                  'clients-peak', 'clients-peak-time', 'clients-average',
                  'consumption-bitrate', 'consumption-totalbytes',
                  'stream-bitrate-raw', 'stream-totalbytes-raw',
                  'consumption-bitrate-raw', 'consumption-totalbytes-raw',
                  'stream-url'):
            self.uiState.addKey(i, None)

    def get_pipeline_string(self, properties):
        return self.pipe_template

    def do_check(self):
        props = self.config['properties']
        if props.get('type', 'master') == 'slave':
            for k in 'socket_path', 'username', 'password':
                if not 'porter_' + k in props:
                    msg = "slave mode, missing required property 'socket_%s'" % k
                    return defer.fail(errors.ConfigError(msg))

        if 'burst_size' in props and 'burst_time' in props:
            msg = 'both burst_size and burst_time set, cannot satisfy'
            return defer.fail(errors.ConfigError(msg))

        # tcp is where multifdsink is
        version = gstreamer.get_plugin_version('tcp') 
        if version < (0,10,9,1):
            return defer.fail(
                errors.PropertyError("multifdsink version too old"))

    def time_bursting_supported(self, sink):
        try:
            sink.get_property('units-max')
            return True
        except TypeError:
            return False

    def setup_burst_mode(self, sink):
        if self.burst_on_connect:
            if self.burst_time and self.time_bursting_supported(sink):
                self.debug("Configuring burst mode for %f second burst", 
                    self.burst_time)
                # Set a burst for configurable minimum time, plus extra to
                # start from a keyframe if needed.
                sink.set_property('sync-method', 4) # burst-keyframe
                sink.set_property('burst-unit', 2) # time
                sink.set_property('burst-value', 
                    long(self.burst_time * gst.SECOND))

                # We also want to ensure that we have sufficient data available
                # to satisfy this burst; and an appropriate maximum, all 
                # specified in units of time.
                sink.set_property('time-min', 
                    long((self.burst_time + 5) * gst.SECOND))

                sink.set_property('unit-type', 2) # time
                sink.set_property('units-soft-max',
                    long((self.burst_time + 8) * gst.SECOND))
                sink.set_property('units-max',
                    long((self.burst_time + 10) * gst.SECOND))
            elif self.burst_size:
                self.debug("Configuring burst mode for %d kB burst", 
                    self.burst_size)
                # If we have a burst-size set, use modern 
                # needs-recent-multifdsink behaviour to have complex bursting.
                # In this mode, we burst a configurable minimum, plus extra 
                # so we start from a keyframe (or less if we don't have a 
                # keyframe available)
                sink.set_property('sync-method', 4) # burst-keyframe
                sink.set_property('burst-unit', 3) # bytes
                sink.set_property('burst-value', self.burst_size * 1024)

                # To use burst-on-connect, we need to ensure that multifdsink
                # has a minimum amount of data available - assume 512 kB beyond
                # the burst amount so that we should have a keyframe available
                sink.set_property('bytes-min', (self.burst_size + 512) * 1024)
                
                # And then we need a maximum still further above that - the
                # exact value doesn't matter too much, but we want it reasonably
                # small to limit memory usage. multifdsink doesn't give us much
                # control here, we can only specify the max values in buffers.
                # We assume each buffer is close enough to 4kB - true for asf
                # and ogg, at least
                sink.set_property('buffers-soft-max', 
                    (self.burst_size + 1024) / 4)
                sink.set_property('buffers-max',
                    (self.burst_size + 2048) / 4)
                
            else:
                # Old behaviour; simple burst-from-latest-keyframe
                self.debug("simple burst-on-connect, setting sync-method 2")
                sink.set_property('sync-method', 2)

                sink.set_property('buffers-soft-max', 250)
                sink.set_property('buffers-max', 500)
        else:
            self.debug("no burst-on-connect, setting sync-method 0")
            sink.set_property('sync-method', 0)

            sink.set_property('buffers-soft-max', 250)
            sink.set_property('buffers-max', 500)
    
    def configure_pipeline(self, pipeline, properties):
        Stats.__init__(self, sink=self.get_element('sink'))

        # FIXME: call self._callLaterId.cancel() somewhere on shutdown
        self._callLaterId = reactor.callLater(1, self._checkUpdate)

        # FIXME: do a .cancel on this Id somewhere
        self._queueCallLaterId = reactor.callLater(0.1, self._handleQueue)
        
        mountPoint = properties.get('mount_point', '')
        if not mountPoint.startswith('/'):
            mountPoint = '/' + mountPoint
        self.mountPoint = mountPoint
        
        # Hostname is used for a variety of purposes. We do a best-effort guess
        # where nothing else is possible, but it's much preferable to just
        # configure this
        self.hostname = properties.get('hostname', None)
        self.iface = self.hostname # We listen on this if explicitly configured,
                                   # but not if it's only guessed at by the
                                   # below code.
        if not self.hostname:
            # Don't call this nasty, nasty, probably flaky function unless we
            # need to.
            self.hostname = netutils.guess_public_hostname()

        self.description = properties.get('description', None)
        if self.description is None:
            self.description = "Flumotion Stream"
 
        # FIXME: tie these together more nicely
        self.resource = resources.HTTPStreamingResource(self)

        # check how to set client sync mode
        sink = self.get_element('sink')
        self.burst_on_connect = properties.get('burst_on_connect', False)
        self.burst_size = properties.get('burst_size', 0)
        self.burst_time = properties.get('burst_time', 0.0)

        self.setup_burst_mode(sink)

        # FIXME: these should be made threadsafe if we use GstThreads
        sink.connect('deep-notify::caps', self._notify_caps_cb)

        # these are made threadsafe using idle_add in the handler
        sink.connect('client-added', self._client_added_cb)

        # We now require a sufficiently recent multifdsink anyway that we can
        # use the new client-fd-removed signal
        sink.connect('client-fd-removed', self._client_fd_removed_cb)
        sink.connect('client-removed', self._client_removed_cb)

        if properties.has_key('user_limit'):
            self.resource.setUserLimit(int(properties['user_limit']))
            
        if properties.has_key('bouncer'):
            self.resource.setBouncerName(properties['bouncer'])

        if properties.has_key('issuer'):
            self.resource.setIssuerClass(properties['issuer'])

        if properties.has_key('duration'):
            self.resource.setDefaultDuration(float(properties['duration']))

        if properties.has_key('domain'):
            self.resource.setDomain(properties['domain'])

        if self.config.has_key('avatarId'):
            self.resource.setRequesterId(self.config['avatarId'])

        if properties.has_key('ip-filter'):
            filter = http.LogFilter()
            for f in properties['ip-filter']:
                filter.addIPFilter(f)
            self.resource.setLogFilter(filter)

        self.type = properties.get('type', 'master')
        if self.type == 'slave':
            # already checked for these in do_check
            self._porterPath = properties['porter_socket_path']
            self._porterUsername = properties['porter_username']
            self._porterPassword = properties['porter_password']

        self.port = int(properties.get('port', 8800))

    def __repr__(self):
        return '<MultifdSinkStreamer (%s)>' % self.name

    # UI code
    def _checkUpdate(self):
        self._tenSecondCount -= 1
        self.updateLoadDeltas()
        if self.needsUpdate or self._tenSecondCount <= 0:
            self._tenSecondCount = 10
            self.needsUpdate = False
            self.update_ui_state()
        self._callLaterId = reactor.callLater(1, self._checkUpdate)

    def getMaxClients(self):
        return self.resource.maxclients

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

    def getUrl(self):
        return "http://%s:%d%s" % (self.hostname, self.port, self.mountPoint)

    def getStreamData(self):
        socket = 'flumotion.component.plugs.streamdata.StreamDataProvider'
        if self.plugs[socket]:
            plug = self.plugs[socket][-1]
            return plug.getStreamData()
        else:
            return {
                'protocol': 'HTTP',
                'description': self.description,
                'url' : self.getUrl()
                }

    def getLoadData(self):
        """
        Return a tuple (deltaadded, deltaremoved, bytes_transferred, 
        current_clients, current_load) of our current bandwidth and user values.
        The deltas are estimates of how much bitrate is added, removed
        due to client connections, disconnections, per second.
        """
        # We calculate the estimated clients added/removed per second, then
        # multiply by the stream bitrate
        deltaadded, deltaremoved = self.getLoadDeltas()

        bytes_received  = self.getBytesReceived()
        uptime          = self.getUptime()
        bitrate = bytes_received * 8 / uptime

        bytes_sent      = self.getBytesSent()
        clients_connected = self.getClients()
        current_load = bitrate * clients_connected

        return (deltaadded * bitrate, deltaremoved * bitrate, bytes_sent, 
            clients_connected, current_load)
    
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

    # We now use both client-removed and client-fd-removed. We call get-stats
    # from the first callback ('client-removed'), but don't actually start
    # removing the client until we get 'client-fd-removed'. This ensures that
    # there's no window in which multifdsink still knows about the fd, but we've    # actually closed it, so we no longer get spurious duplicates.
    # this can be called from both application and streaming thread !
    def _client_removed_cb(self, sink, fd, reason):
        stats = sink.emit('get-stats', fd)
        self._pending_removals[fd] = (stats, reason)

    # this can be called from both application and streaming thread !
    def _client_fd_removed_cb(self, sink, fd):
        self._removed_lock.acquire()
        (stats, reason) = self._pending_removals.pop(fd)
        self._removed_queue.append((sink, fd, reason, stats))
        self._removed_lock.release()

    ### END OF THREAD-AWARE CODE

    def do_stop(self):
        if self.type == 'slave' and self._pbclient:
            return self._pbclient.deregisterPath(self.mountPoint)
        else:
            return feedcomponent.ParseLaunchComponent.do_stop(self)

    def updatePorterDetails(self, path, username, password):
        """
        Provide a new set of porter login information, for when we're in slave
        mode and the porter changes.
        If we're currently connected, this won't disconnect - it'll just change
        the information so that next time we try and connect we'll use the
        new ones
        """
        if self.type == 'slave':
            self._porterUsername = username
            self._porterPassword = password

            creds = credentials.UsernamePassword(self._porterUsername, 
                self._porterPassword)
            self._pbclient.startLogin(creds, self.medium)

            # If we've changed paths, we must do some extra work.
            if path != self._porterPath:
                self._porterPath = path
                self._pbclient.stopTrying() # Stop trying to connect with the
                                            # old connector.
                self._pbclient.resetDelay()
                reactor.connectWith(
                    fdserver.FDConnector, self._porterPath, 
                    self._pbclient, 10, checkPID=False)
        else:
            raise errors.WrongStateError(
                "Can't specify porter details in master mode")

    def do_start(self, *args, **kwargs):
        root = resources.HTTPRoot()
        # TwistedWeb wants the child path to not include the leading /
        mount = self.mountPoint[1:]
        root.putChild(mount, self.resource)
        if self.type == 'slave':
            # Streamer is slaved to a porter.

            # We have two things we want to do in parallel:
            #  - ParseLaunchComponent.do_start()
            #  - log in to the porter, then register our mountpoint with
            #    the porter.
            # So, we return a DeferredList with a deferred for each of
            # these tasks. The second one's a bit tricky: we pass a dummy
            # deferred to our PorterClientFactory that gets fired once
            # we've done all of the tasks the first time (it's an 
            # automatically-reconnecting client factory, and we only fire 
            # this deferred the first time)

            d1 = feedcomponent.ParseLaunchComponent.do_start(self, 
                *args, **kwargs)

            d2 = defer.Deferred()
            mountpoints = [self.mountPoint]
            self._pbclient = porterclient.HTTPPorterClientFactory(
                server.Site(resource=root), mountpoints, d2)

            creds = credentials.UsernamePassword(self._porterUsername, 
                self._porterPassword)
            self._pbclient.startLogin(creds, self.medium)

            self.debug("Starting porter login!")
            # This will eventually cause d2 to fire
            reactor.connectWith(
                fdserver.FDConnector, self._porterPath, 
                self._pbclient, 10, checkPID=False)

            return defer.DeferredList([d1, d2])
        else:
            # Streamer is standalone.
            try:
                self.debug('Listening on %d' % self.port)
                iface = self.iface or ""
                reactor.listenTCP(self.port, server.Site(resource=root), 
                    interface=iface)
                return feedcomponent.ParseLaunchComponent.do_start(self, *args, 
                    **kwargs)
            except error.CannotListenError:
                t = 'Port %d is not available.' % self.port
                self.warning(t)
                m = messages.Error(T_(N_(
                    "Network error: TCP port %d is not available."), self.port))
                self.addMessage(m)
                self.setMood(moods.sad)
                return defer.fail(errors.ComponentStartHandledError(t))

pygobject.type_register(MultifdSinkStreamer)
