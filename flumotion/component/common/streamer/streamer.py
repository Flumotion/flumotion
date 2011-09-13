# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4

# Flumotion - a streaming media server
# Copyright (C) 2004,2005,2006,2007,2008,2009 Fluendo, S.L.
# Copyright (C) 2010,2011 Flumotion Services, S.A.
# All rights reserved.
#
# This file may be distributed and/or modified under the terms of
# the GNU Lesser General Public License version 2.1 as published by
# the Free Software Foundation.
# This file is distributed without any warranty; without even the implied
# warranty of merchantability or fitness for a particular purpose.
# See "LICENSE.LGPL" in the source distribution for more information.
#
# Headers in this file shall remain intact.

import time

import gst

from twisted.cred import credentials
from twisted.internet import reactor, error, defer
from twisted.web import server

from zope.interface import implements

from flumotion.common import errors
from flumotion.common import messages, netutils, interfaces
from flumotion.common import format as formatting
from flumotion.component import feedcomponent
from flumotion.component.base import http
from flumotion.component.component import moods
from flumotion.component.common.streamer.resources import HTTPRoot
from flumotion.component.misc.porter import porterclient
from flumotion.twisted import fdserver

from flumotion.common.i18n import N_, gettexter

__all__ = ['HTTPMedium']
__version__ = "$Rev$"

STATS_POLL_INTERVAL = 10
UI_UPDATE_THROTTLE_PERIOD = 2.0 # Don't update UI more than once every two
                                # seconds
T_ = gettexter()


class Stats(object):

    def __init__(self):
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
        self._currentBitrate = -1 # not known yet
        self._lastBytesReceived = -1 # not known yet

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
        self.average_time = now # we can update now that we used self.a
        if dt1 == 0:
            # first measurement
            self.average_client_number = 0
        else:
            dt = dt1 + dt2
            before = (dc1 * dt1) / dt
            after = dc2 * dt2 / dt
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

    def _updateStats(self):
        """
        Periodically, update our statistics on load deltas, and update the
        UIState with new values for total bytes, bitrate, etc.
        """

        oldtime, oldadd, oldremove = self._load_deltas_ongoing
        add, remove = self.clients_added_count, self.clients_removed_count
        now = time.time()
        diff = float(now - oldtime)

        self.load_deltas = [(add-oldadd)/diff, (remove-oldremove)/diff]
        self._load_deltas_ongoing = [now, add, remove]

        bytesReceived = self.getBytesReceived()
        if self._lastBytesReceived >= 0:
            self._currentBitrate = ((bytesReceived - self._lastBytesReceived) *
                 8 / STATS_POLL_INTERVAL)
        self._lastBytesReceived = bytesReceived

        self.update_ui_state()

        self._updateCallLaterId = reactor.callLater(STATS_POLL_INTERVAL,
            self._updateStats)

    def getCurrentBitrate(self):
        if self._currentBitrate >= 0:
            return self._currentBitrate
        else:
            return self.getBytesReceived() * 8 / self.getUptime()

    def getBytesSent(self):
        raise NotImplemented("getBytesSent must be implemented by subclasses")

    def getBytesReceived(self):
        raise NotImplemented("getBytesReceived must be implemented by "
                             "subclasses")

    def getUrl(self):
        raise NotImplementedError("getUrl must be implemented by subclasses")

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

    def getLoadDeltas(self):
        return self.load_deltas

    def updateState(self, set):
        c = self

        bytes_sent = c.getBytesSent()
        bytes_received = c.getBytesReceived()
        uptime = c.getUptime()

        set('stream-mime', c.get_mime())
        set('stream-url', c.getUrl())
        set('stream-uptime', formatting.formatTime(uptime))
        bitspeed = bytes_received * 8 / uptime
        currentbitrate = self.getCurrentBitrate()
        set('stream-bitrate', formatting.formatStorage(bitspeed) + 'bit/s')
        set('stream-current-bitrate',
            formatting.formatStorage(currentbitrate) + 'bit/s')
        set('stream-totalbytes',
            formatting.formatStorage(bytes_received) + 'Byte')
        set('stream-bitrate-raw', bitspeed)
        set('stream-totalbytes-raw', bytes_received)

        set('clients-current', str(c.getClients()))
        set('clients-max', str(c.getMaxClients()))
        set('clients-peak', str(c.getPeakClients()))
        set('clients-peak-time', c.getPeakEpoch())
        set('clients-average', str(int(c.getAverageClients())))

        bitspeed = bytes_sent * 8 / uptime
        set('consumption-bitrate',
            formatting.formatStorage(bitspeed) + 'bit/s')
        set('consumption-bitrate-current',
            formatting.formatStorage(
                currentbitrate * c.getClients()) + 'bit/s')
        set('consumption-totalbytes',
            formatting.formatStorage(bytes_sent) + 'Byte')
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
        return d

    def keepAlive(self, bouncerName, issuerName, ttl):
        """
        @rtype: L{twisted.internet.defer.Deferred}
        """
        return self.callRemote('keepAlive', bouncerName, issuerName, ttl)

    def removeKeycardId(self, bouncerName, keycardId):
        """
        @rtype: L{twisted.internet.defer.Deferred}
        """
        return self.callRemote('removeKeycardId', bouncerName, keycardId)

    ### remote methods for manager to call on

    def remote_expireKeycard(self, keycardId):
        return self.comp.httpauth.expireKeycard(keycardId)

    def remote_expireKeycards(self, keycardIds):
        return self.comp.httpauth.expireKeycards(keycardIds)

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

    def remote_removeAllClients(self):
        return self.comp.remove_all_clients()


class Streamer(feedcomponent.ParseLaunchComponent, Stats):
    implements(interfaces.IStreamingComponent)

    checkOffset = True

    # this object is given to the HTTPMedium as comp
    logCategory = 'cons-http'

    pipe_template = 'multifdsink name=sinksync=false recover-policy=3'

    componentMediumClass = HTTPMedium

    def init(self):
        reactor.debug = True
        self.debug("HTTP streamer initialising")

        self.caps = None
        self.resource = None
        self.httpauth = None
        self.mountPoint = None
        self.burst_on_connect = False
        self.timeout = 0L

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

        self._tport = None

        self._updateCallLaterId = None
        self._lastUpdate = 0
        self._updateUI_DC = None

        self._pending_removals = {}

        for i in ('stream-mime', 'stream-uptime', 'stream-current-bitrate',
                  'stream-bitrate', 'stream-totalbytes', 'clients-current',
                  'clients-max', 'clients-peak', 'clients-peak-time',
                  'clients-average', 'consumption-bitrate',
                  'consumption-bitrate-current',
                  'consumption-totalbytes', 'stream-bitrate-raw',
                  'stream-totalbytes-raw', 'consumption-bitrate-raw',
                  'consumption-totalbytes-raw', 'stream-url'):
            self.uiState.addKey(i, None)

    def getDescription(self):
        return self.description

    def get_pipeline_string(self, properties):
        return self.pipe_template

    def check_properties(self, props, addMessage):

        if props.get('type', 'master') == 'slave':
            for k in 'socket-path', 'username', 'password':
                if not 'porter-' + k in props:
                    raise errors.ConfigError("slave mode, missing required"
                                             " property 'porter-%s'" % k)

        if 'burst-size' in props and 'burst-time' in props:
            raise errors.ConfigError('both burst-size and burst-time '
                                     'set, cannot satisfy')

    def configureAuthAndResource(self):
        raise NotImplementedError("configureAuthAndResource must be "
                                  "implemented by subclasses")

    def parseProperties(self, properties):
        mountPoint = properties.get('mount-point', '')
        if not mountPoint.startswith('/'):
            mountPoint = '/' + mountPoint
        self.mountPoint = mountPoint

        # Hostname is used for a variety of purposes. We do a best-effort guess
        # where nothing else is possible, but it's much preferable to just
        # configure this
        self.hostname = properties.get('hostname', None)
        self.iface = self.hostname # We listen on this if explicitly
                                   # configured, but not if it's only guessed
                                   # at by the below code.
        if not self.hostname:
            # Don't call this nasty, nasty, probably flaky function unless we
            # need to.
            self.hostname = netutils.guess_public_hostname()

        self.description = properties.get('description', None)
        if self.description is None:
            self.description = "Flumotion Stream"

        # check how to set client sync mode

        if 'client-limit' in properties:
            limit = int(properties['client-limit'])
            self.resource.setUserLimit(limit)
            if limit != self.resource.maxclients:
                m = messages.Info(T_(N_(
                    "Your system configuration does not allow the maximum "
                    "client limit to be set to %d clients."),
                    limit))
                m.description = T_(N_(
                    "Learn how to increase the maximum number of clients."))
                m.section = 'chapter-optimization'
                m.anchor = 'section-configuration-system-fd'
                self.addMessage(m)

        if 'bandwidth-limit' in properties:
            limit = int(properties['bandwidth-limit'])
            if limit < 1000:
                # The wizard used to set this as being in Mbps, oops.
                self.debug("Bandwidth limit set to unreasonably low %d bps, "
                    "assuming this is meant to be Mbps", limit)
                limit *= 1000000
            self.resource.setBandwidthLimit(limit)

        if 'redirect-on-overflow' in properties:
            self.resource.setRedirectionOnLimits(
                properties['redirect-on-overflow'])

        if 'bouncer' in properties:
            self.httpauth.setBouncerName(properties['bouncer'])

        if 'allow-default' in properties:
            self.httpauth.setAllowDefault(properties['allow-default'])

        if 'duration' in properties:
            self.httpauth.setDefaultDuration(
                float(properties['duration']))

        if 'domain' in properties:
            self.httpauth.setDomain(properties['domain'])

        if 'avatarId' in self.config:
            self.httpauth.setRequesterId(self.config['avatarId'])

        if 'ip-filter' in properties:
            logFilter = http.LogFilter()
            for f in properties['ip-filter']:
                logFilter.addIPFilter(f)
            self.resource.setLogFilter(logFilter)

        if 'timeout' in properties:
            self.timeout = properties['timeout'] * gst.SECOND

        self.type = properties.get('type', 'master')
        if self.type == 'slave':
            # already checked for these in do_check
            self._porterPath = properties['porter-socket-path']
            self._porterUsername = properties['porter-username']
            self._porterPassword = properties['porter-password']

        self.port = int(properties.get('port', 8800))

    def configure_pipeline(self, pipeline, properties):
        self._updateCallLaterId = reactor.callLater(10, self._updateStats)
        self.configureAuthAndResource()
        self.parseProperties(properties)

    def getMaxClients(self):
        return self.resource.maxclients

    def hasCaps(self):
        # all the sinks should have caps set
        sinkHasCaps = map(lambda sink: sink.caps is not None, self.sinks)
        return None not in sinkHasCaps

    def get_mime(self):
        raise NotImplemented("get_mime must be implemented by subclasses")

    def get_content_type(self):
        raise NotImplemented("get_content_type must be implemented by "
                             "subclasses")

    def getUrl(self):
        port = self.port

        if self.type == 'slave' and self._pbclient:
            if not self._pbclient.remote_port:
                return ""
            port = self._pbclient.remote_port

        if (not port) or (port == 80):
            port_str = ""
        else:
            port_str = ":%d" % port

        return "http://%s%s%s" % (self.hostname, port_str, self.mountPoint)

    def getStreamData(self):
        socket = 'flumotion.component.plugs.streamdata.StreamDataProviderPlug'
        if self.plugs[socket]:
            plug = self.plugs[socket][-1]
            return plug.getStreamData()
        else:
            return {'protocol': 'HTTP',
                    'description': self.description,
                    'url': self.getUrl()}

    def getLoadData(self):
        """Return a tuple (deltaadded, deltaremoved, bytes_transferred,
        current_clients, current_load) of our current bandwidth and
        user values.
        The deltas are estimates of how much bitrate is added, removed
        due to client connections, disconnections, per second.
        """
        # We calculate the estimated clients added/removed per second, then
        # multiply by the stream bitrate
        deltaadded, deltaremoved = self.getLoadDeltas()

        bytes_received = self.getBytesReceived()
        uptime = self.getUptime()
        bitrate = bytes_received * 8 / uptime

        bytes_sent = self.getBytesSent()
        clients_connected = self.getClients()
        current_load = bitrate * clients_connected

        return (deltaadded * bitrate, deltaremoved * bitrate, bytes_sent,
            clients_connected, current_load)

    def update_ui_state(self):
        """Update the uiState object.
        Such updates (through this function) are throttled to a maximum rate,
        to avoid saturating admin clients with traffic when many clients are
        connecting/disconnecting.
        """

        def setIfChanged(k, v):
            if self.uiState.get(k) != v:
                self.uiState.set(k, v)

        def update_ui_state_later():
            self._updateUI_DC = None
            self.update_ui_state()

        now = time.time()

        # If we haven't updated too recently, do it immediately.
        if now - self._lastUpdate >= UI_UPDATE_THROTTLE_PERIOD:
            if self._updateUI_DC:
                self._updateUI_DC.cancel()
                self._updateUI_DC = None

            self._lastUpdate = now
            # fixme: have updateState just update what changed itself
            # without the hack above
            self.updateState(setIfChanged)
        elif not self._updateUI_DC:
            # Otherwise, schedule doing this in a few seconds (unless an update
            # was already scheduled)
            self._updateUI_DC = reactor.callLater(UI_UPDATE_THROTTLE_PERIOD,
                                                  update_ui_state_later)

    def do_stop(self):
        if self._updateCallLaterId:
            self._updateCallLaterId.cancel()
            self._updateCallLaterId = None

        if self.httpauth:
            self.httpauth.stopKeepAlive()

        if self._tport:
            self._tport.stopListening()

        l = []
        # After we stop listening (so new connections aren't possible),
        # disconnect (and thus log) all the old ones.
        clients = self.remove_all_clients()
        if clients:
            l.append(clients)

        if self.type == 'slave' and self._pbclient:
            l.append(self._pbclient.deregisterPath(self.mountPoint))
        return defer.DeferredList(l)

    def updatePorterDetails(self, path, username, password):
        """Provide a new set of porter login information, for when we're
        in slave mode and the porter changes.
        If we're currently connected, this won't disconnect - it'll just change
        the information so that next time we try and connect we'll use the
        new ones
        """
        if self.type == 'slave':
            self._porterUsername = username
            self._porterPassword = password

            creds = credentials.UsernamePassword(self._porterUsername,
                self._porterPassword)

            self._pbclient.startLogin(creds, self._pbclient.medium)

            # If we've changed paths, we must do some extra work.
            if path != self._porterPath:
                self.debug("Changing porter login to use \"%s\"", path)
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

    def do_pipeline_playing(self):
        # Override this to not set the component happy; instead do this once
        # both the pipeline has started AND we've logged in to the porter.
        if hasattr(self, '_porterDeferred'):
            d = self._porterDeferred
        else:
            d = defer.succeed(None)
        self.httpauth.scheduleKeepAlive()
        d.addCallback(lambda res:
                      feedcomponent.ParseLaunchComponent.do_pipeline_playing(
            self))
        return d

    def do_setup(self):
        root = HTTPRoot()
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

            self._porterDeferred = d = defer.Deferred()
            mountpoints = [self.mountPoint]
            self._pbclient = porterclient.HTTPPorterClientFactory(
                server.Site(resource=root), mountpoints, d)

            creds = credentials.UsernamePassword(self._porterUsername,
                self._porterPassword)
            self._pbclient.startLogin(creds, self._pbclient.medium)

            self.info("Starting porter login at \"%s\"", self._porterPath)
            # This will eventually cause d to fire
            reactor.connectWith(
                fdserver.FDConnector, self._porterPath,
                self._pbclient, 10, checkPID=False)
        else:
            # Streamer is standalone.
            try:
                iface = self.iface or ""
                self.info('Listening on port %d, interface=%r',
                          self.port, iface)
                self._tport = reactor.listenTCP(
                    self.port, server.Site(resource=root),
                    interface=iface)
            except error.CannotListenError:
                t = 'Port %d is not available.' % self.port
                self.warning(t)
                m = messages.Error(T_(N_(
                    "Network error: TCP port %d is not available."),
                                      self.port))
                self.addMessage(m)
                self.setMood(moods.sad)
                return defer.fail(errors.ComponentSetupHandledError(t))
