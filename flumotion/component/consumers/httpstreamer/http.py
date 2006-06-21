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
from flumotion.common import messages, netutils

from flumotion.twisted import fdserver
from flumotion.component.misc.porter import porterclient

# proxy import
from flumotion.component.component import moods
from flumotion.common.pygobject import gsignal

from flumotion.component.consumers.httpstreamer import resources

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
        return self.callRemote('authenticate', bouncerName, keycard)

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

class HTTPPorterClientFactory(porterclient.PorterClientFactory):

    def __init__(self, childFactory, mountPoint, do_start_deferred):
        porterclient.PorterClientFactory.__init__(self, childFactory)
        self._mountPoint = mountPoint
        self._do_start_deferred = do_start_deferred

    def _fireDeferred(self, r):
        # If we still have the deferred, fire it (this happens after we've
        # completed log in the _first_ time, not subsequent times)
        if self._do_start_deferred:
            self.debug("Firing initial deferred: should indicate that login is "
                "complete")
            self._do_start_deferred.callback(None)
            self._do_start_deferred = None

    def gotDeferredLogin(self, deferred):
        # This is called when we start logging in to give us the deferred for
        # the login process. Once we're logged in, we want to set our
        # remote ref, then register our path with the porter, then (possibly)
        # fire a different deferred
        self.debug("Got deferred login, adding callbacks")
        deferred.addCallback(self.medium.setRemoteReference)
        deferred.addCallback(lambda r: self.registerPath(self._mountPoint))
        deferred.addCallback(self._fireDeferred)

### the actual component is a streamer using multifdsink
class MultifdSinkStreamer(feedcomponent.ParseLaunchComponent, Stats):
    # this object is given to the HTTPMedium as comp
    logCategory = 'cons-http'
    
    # use select for test
    pipe_template = 'multifdsink name=sink ' + \
                                'sync=false ' + \
                                'buffers-max=500 ' + \
                                'buffers-soft-max=250 ' + \
                                'recover-policy=3'

    gsignal('client-removed', object, int, int, object)
    
    component_medium_class = HTTPMedium

    def init(self):
        reactor.debug = True

        self.caps = None
        self.resource = None
        self.mountPoint = None
        self.burst_on_connect = False

        self.description = None

        # Used if we've slaved to a porter.
        self._pbclient = None
        self._porterUsername = None
        self._porterPassword = None
        self._porterId = None
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
        self.burst_on_connect = properties.get('burst_on_connect', False)
        sink = self.get_element('sink')
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

        # these are made threadsafe using idle_add in the handler
        sink.connect('client-removed', self._client_removed_cb)
        sink.connect('client-added', self._client_added_cb)

        if properties.has_key('user_limit'):
            self.resource.setUserLimit(int(properties['user_limit']))
            
        if properties.has_key('bouncer'):
            self.resource.setBouncerName(properties['bouncer'])

        if properties.has_key('issuer'):
            self.resource.setIssuerClass(properties['issuer'])

        if properties.has_key('domain'):
            self.resource.setDomain(properties['domain'])

        if self.config.has_key('avatarId'):
            self.resource.setRequesterName(self.config['avatarId'])

        self.type = properties.get('type', 'master')
        if self.type == 'slave':
            if properties.has_key('porter_socket_path'):
                self._porterPath = properties['porter_socket_path']
                self._porterUsername = properties['porter_user']
                self._porterPassword = properties['porter_pass']
            else:
                self._porterPath = None
                self._porterId = "/atmosphere/" + properties['porter_name']

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
        m3ufile = "#EXTM3U\n" \
                  "#EXTINF:-1:%s\n" \
                  "%s" % (self.description, self.getUrl())

        return {
                'protocol': 'HTTP',
                'content-type': "audio/x-mpegurl",
                'description' : m3ufile
            }

    def getLoadData(self):
        """
        Return a tuple (deltaadded, deltaremoved, bytes_transferred, 
        current_clients) of our current bandwidth and user values.
        The deltas are estimates of how much bitrate is added, removed i
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

        return (deltaadded * bitrate, deltaremoved * bitrate, bytes_sent, 
            clients_connected)
    
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

    def failedSlavedStart(self, failure):
        self.warning("Failed to start slaved streamer: %s" % failure)
        m = messages.Error(T_(
            N_("Porter '%s' not found, cannot slave this streamer to it."), 
            self._porterId))
        self.addMessage(m)
        self.setMood(moods.sad)

    def do_stop(self):
        def stoppedStreamer(result):
            self.setMood(moods.sleeping)
            return result

        if self.type == 'slave':
            d = self._pbclient.deregisterPath(self.mountPoint)
            d.addCallback(stoppedStreamer)
            return d
        else:
            return feedcomponent.ParseLaunchComponent.do_stop(self)

    def do_start(self, *args, **kwargs):
        def gotPorterDetails(porter):
            (self._porterPath, self._porterUsername, 
                self._porterPassword) = porter
                
            reactor.connectWith(fdserver.FDConnector, self._porterPath, 
                self._pbclient, 10, checkPID=False)

            creds = credentials.UsernamePassword(self._porterUsername, 
                self._porterPassword)
            self.debug("Starting porter login!")
            self._pbclient.startLogin(creds, self.medium)

        root = resources.HTTPRoot()
        # TwistedWeb wants the child path to not include the leading /
        mount = self.mountPoint[1:]
        root.putChild(mount, self.resource)
        
        if self.type == 'slave':
            # Streamer is slaved to a porter.

            # We have two things we want to do in parallel:
            #  - ParseLaunchComponent.do_start()
            #  - get the porter details (either from locals, or via a 
            #    remote call, then log in to the porter, then register
            #    our mountpoint with the porter.
            # So, we return a DeferredList with a deferred for each of
            # these tasks. The second one's a bit tricky: we pass a dummy
            # deferred to our PorterClientFactory that gets fired once
            # we've done all of the tasks the first time (it's an 
            # automatically-reconnecting client factory, and we only fire 
            # this deferred the first time)

            d1 = feedcomponent.ParseLaunchComponent.do_start(self, 
                *args, **kwargs)

            d2 = defer.Deferred()
            self._pbclient = HTTPPorterClientFactory(
                server.Site(resource=root), self.mountPoint, d2)

            dl = defer.DeferredList([d1, d2])

            # Now we create another deferred for when we've got the porter
            # info, which will (one way or another) get called. From that,
            # we start actually logging in - eventually causing d2 to fire.
            if not self._porterPath:
                self.debug("Doing remote call to get porter details")
                d = self.medium.callRemote("componentCallRemote",
                    self._porterId, "getPorterDetails")
            else:
                self.debug("Creating dummy deferred")
                d = defer.succeed((self._porterPath, self._porterUsername, 
                    self._porterPassword))

            d.addCallback(gotPorterDetails)
            d.addErrback(self.failedSlavedStart)

            return dl
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
