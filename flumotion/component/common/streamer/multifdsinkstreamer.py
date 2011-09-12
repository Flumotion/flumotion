# -*- Mode: Python; test-case-name: flumotion.test.test_http -*-
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

import gst

from twisted.internet import reactor

from flumotion.common import gstreamer
from flumotion.common import messages
from flumotion.component.common.streamer import streamer

from flumotion.common.i18n import N_, gettexter

__all__ = ['MultifdSinkStreamer']
__version__ = "$Rev$"

T_ = gettexter()


### the actual component is a streamer using multifdsink


class Stats(streamer.Stats):

    def __init__(self, sinks):
        streamer.Stats.__init__(self)
        if not isinstance(sinks, list):
            sinks = [sinks]
        self.sinks = sinks

    def getBytesSent(self):
        return sum(map(
                lambda sink: sink.get_property('bytes-served'), self.sinks))

    def getBytesReceived(self):
        return max(map(
                lambda sink: sink.get_property('bytes-to-serve'), self.sinks))


class MultifdSinkStreamer(streamer.Streamer, Stats):
    pipe_template = 'multifdsink name=sink ' + \
                                'sync=false ' + \
                                'recover-policy=3'
    defaultSyncMethod = 0

    def setup_burst_mode(self, sink):
        if self.burst_on_connect:
            if self.burst_time and \
                    gstreamer.element_factory_has_property('multifdsink',
                                                           'units-max'):
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
                sink.set_property('sync-method', 'burst-keyframe')
                sink.set_property('burst-unit', 'bytes')
                sink.set_property('burst-value', self.burst_size * 1024)

                # To use burst-on-connect, we need to ensure that multifdsink
                # has a minimum amount of data available - assume 512 kB beyond
                # the burst amount so that we should have a keyframe available
                sink.set_property('bytes-min', (self.burst_size + 512) * 1024)

                # And then we need a maximum still further above that - the
                # exact value doesn't matter too much, but we want it
                # reasonably small to limit memory usage. multifdsink doesn't
                # give us much control here, we can only specify the max
                # values in buffers. We assume each buffer is close enough
                # to 4kB - true for asf and ogg, at least
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
            sink.set_property('sync-method', self.defaultSyncMethod)

            sink.set_property('buffers-soft-max', 250)
            sink.set_property('buffers-max', 500)

    def parseExtraProperties(self, properties):
        # check how to set client sync mode
        self.burst_on_connect = properties.get('burst-on-connect', False)
        self.burst_size = properties.get('burst-size', 0)
        self.burst_time = properties.get('burst-time', 0.0)

    def configureSink(self, sink):
        self.setup_burst_mode(sink)

        if gstreamer.element_factory_has_property('multifdsink',
                                                  'resend-streamheader'):
            sink.set_property('resend-streamheader', False)
        else:
            self.debug("resend-streamheader property not available, "
                       "resending streamheader when it changes in the caps")

        sink.set_property('timeout', self.timeout)

        sink.connect('deep-notify::caps', self._notify_caps_cb)

        # these are made threadsafe using idle_add in the handler
        sink.connect('client-added', self._client_added_handler)

        # We now require a sufficiently recent multifdsink anyway that we can
        # use the new client-fd-removed signal
        sink.connect('client-fd-removed', self._client_fd_removed_cb)
        sink.connect('client-removed', self._client_removed_cb)

        sink.caps = None

    def check_properties(self, props, addMessage):
        streamer.Streamer.check_properties(self, props, addMessage)

        # tcp is where multifdsink is
        version = gstreamer.get_plugin_version('tcp')
        if version < (0, 10, 9, 1):
            m = messages.Error(T_(N_(
                "Version %s of the '%s' GStreamer plug-in is too old.\n"),
                    ".".join(map(str, version)), 'multifdsink'))
            m.add(T_(N_("Please upgrade '%s' to version %s."),
                'gst-plugins-base', '0.10.10'))
            addMessage(m)

    def configure_pipeline(self, pipeline, properties):
        sink = self.get_element('sink')
        Stats.__init__(self, sink)

        streamer.Streamer.configure_pipeline(self, pipeline, properties)
        self.parseExtraProperties(properties)
        self.configureSink(sink)

    def __repr__(self):
        return '<MultifdSinkStreamer (%s)>' % self.name

    def getMaxClients(self):
        return self.resource.maxclients

    def get_mime(self):
        if self.sinks[0].caps:
            return self.sinks[0].caps[0].get_name()

    def get_content_type(self):
        mime = self.get_mime()
        if mime == 'multipart/x-mixed-replace':
            mime += ";boundary=ThisRandomString"
        return mime

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

    def add_client(self, fd, request):
        sink = self.get_element('sink')
        sink.emit('add', fd)

    def remove_client(self, fd):
        sink = self.get_element('sink')
        sink.emit('remove', fd)

    def remove_all_clients(self):
        """Remove all the clients.

        Returns a deferred fired once all clients have been removed.
        """
        if self.resource:
            # can be None if we never went happy
            self.debug("Asking for all clients to be removed")
            return self.resource.removeAllClients()

    def _client_added_handler(self, sink, fd):
        self.log('[fd %5d] client_added_handler', fd)
        Stats.clientAdded(self)
        self.update_ui_state()

    def _client_removed_handler(self, sink, fd, reason, stats):
        self.log('[fd %5d] client_removed_handler, reason %s', fd, reason)
        if reason.value_name == 'GST_CLIENT_STATUS_ERROR':
            self.warning('[fd %5d] Client removed because of write error' % fd)

        self.resource.clientRemoved(sink, fd, reason, stats)
        Stats.clientRemoved(self)
        self.update_ui_state()

    ### START OF THREAD-AWARE CODE (called from non-reactor threads)

    def _notify_caps_cb(self, element, pad, param):
        # We store caps in sink objects as
        # each sink might (and will) serve different content-type
        caps = pad.get_negotiated_caps()
        if caps == None:
            return

        caps_str = gstreamer.caps_repr(caps)
        self.debug('Got caps: %s' % caps_str)

        if not element.caps == None:
            self.warning('Already had caps: %s, replacing' % caps_str)

        self.debug('Storing caps: %s' % caps_str)
        element.caps = caps

        reactor.callFromThread(self.update_ui_state)

    # We now use both client-removed and client-fd-removed. We call get-stats
    # from the first callback ('client-removed'), but don't actually start
    # removing the client until we get 'client-fd-removed'. This ensures that
    # there's no window in which multifdsink still knows about the fd,
    # but we've actually closed it, so we no longer get spurious duplicates.
    # this can be called from both application and streaming thread !

    def _client_removed_cb(self, sink, fd, reason):
        stats = sink.emit('get-stats', fd)
        self._pending_removals[fd] = (stats, reason)

    # this can be called from both application and streaming thread !

    def _client_fd_removed_cb(self, sink, fd):
        (stats, reason) = self._pending_removals.pop(fd)

        reactor.callFromThread(self._client_removed_handler, sink, fd,
            reason, stats)

    ### END OF THREAD-AWARE CODE
