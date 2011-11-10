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

from twisted.internet import defer
from twisted.web import server

from flumotion.component.common.streamer.fragmentedresource import\
    FragmentedResource

__version__ = "$Rev: $"

M3U8_CONTENT_TYPE = 'application/vnd.apple.mpegurl'
PLAYLIST_EXTENSION = '.m3u8'

### the Twisted resource that handles the base URL


class HTTPLiveStreamingResource(FragmentedResource):

    logCategory = 'hls-streamer'

    def __init__(self, streamer, httpauth, secretKey, sessionTimeout):
        """
        @param streamer: L{HTTPLiveStreamer}
        """
        self.ring = streamer.getRing()
        FragmentedResource.__init__(self, streamer, httpauth, secretKey,
            sessionTimeout)

    def _renderKey(self, res, request):
        self._writeHeaders(request, 'binary/octect-stream')
        if request.method == 'GET':
            key = self.ring.getEncryptionKey(request.args['key'][0])
            request.write(key)
            self.bytesSent += len(key)
            self._logWrite(request)
        elif request.method == 'HEAD':
            self.debug('handling HEAD request')
        request.finish()
        return res

    def _renderPlaylist(self, res, request, resource):
        self.debug('_render(): asked for playlist %s', resource)
        request.setHeader("Connection", "Keep-Alive")
        self._writeHeaders(request, M3U8_CONTENT_TYPE)
        if request.method == 'GET':
            playlist = self.ring.renderPlaylist(resource, request.args)
            request.write(playlist)
            self.bytesSent += len(playlist)
            self._logWrite(request)
        elif request.method == 'HEAD':
            self.debug('handling HEAD request')
        request.finish()
        return res

    def _renderFragment(self, res, request, resource):
        self.debug('_render(): asked for fragment %s', resource)
        request.setHeader('Connection', 'close')
        self._writeHeaders(request)
        if request.method == 'GET':
            data = self.ring.getFragment(resource)
            request.setHeader('content-length', len(data))
            request.write(data)
            self.bytesSent += len(data)
            self._logWrite(request)
        if request.method == 'HEAD':
            self.debug('handling HEAD request')
        request.finish()
        return res

    def _render(self, request):
        if not self.isReady():
            return self._handleNotReady(request)
        if self.reachedServerLimits():
            return self._handleServerFull(request)

        # A GET request will be like 'mountpoint+resource':
        # 'GET /iphone/fragment-0.ts' or 'GET /fragment-0.ts'
        # The mountpoint is surrounded by '/' in setMountPoint()
        # so we can safely look for the mountpoint and extract the
        # resource name
        if not request.path.startswith(self.mountPoint):
            return self._renderForbidden(request)
        resource = request.path.replace(self.mountPoint, '', 1)

        d = defer.maybeDeferred(self._checkSession, request)

        # Playlists
        if resource.endswith(PLAYLIST_EXTENSION):
            d.addCallback(self._renderPlaylist, request, resource)
        # Keys
        elif resource == 'key' and 'key' in request.args:
            d.addCallback(self._renderKey, request)
        # Fragments
        else:
            d.addCallback(self._renderFragment, request, resource)

        d.addErrback(self._renderNotFoundResponse, request)
        return server.NOT_DONE_YET

    render_GET = _render
    render_HEAD = _render
