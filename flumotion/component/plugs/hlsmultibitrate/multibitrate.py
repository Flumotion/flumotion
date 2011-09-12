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

from twisted.web.resource import Resource
from twisted.web.static import Data

from flumotion.common import log
from flumotion.common.errors import ComponentStartError
from flumotion.component.misc.httpserver.httpserver import HTTPFileStreamer
from flumotion.component.plugs.base import ComponentPlug

__version__ = "$Rev$"


HEADER = "#EXTM3U"

ENTRY_TEMPLATE = \
"""
#EXT-X-STREAM-INF:PROGRAM-ID=1,BANDWIDTH=%(bitrate)d
%(stream-url)s"""

CONTENT_TYPE = "application/vnd.apple.mpegurl"


class PlaylistResource(Resource):
    """I am a resource for m3u8 playlists, rendering multibitrate playlists
    based on the user-agent, so that IPad clients gets a variant playlist in
    which the first element correspond to the higher bitrate, whilst IPhone ones
    receive a playlist where the first element has a lower bitrate.
    """

    def __init__(self, entries, target_bitrate=200000):
        Resource.__init__(self)

        self._entries = entries
        self._target_bitrate = target_bitrate

    def render_GET(self, request):
        playlist = [HEADER]

        agent = request.getHeader('User-Agent')
        if agent:
            if 'ipad' in agent.lower():
                self._target_bitrate = 600000
            else:
                self._target_bitrate = 200000

        self._entries.sort(key=lambda x: abs(x['bitrate'] -
                                         self._target_bitrate))

        for entry in self._entries:
            playlist.append(ENTRY_TEMPLATE % entry)

        request.setHeader('Content-type', 'application/vnd.apple.mpegurl')
        return "\n".join(playlist)


class MultibiratePlaylistPlug(ComponentPlug):
    """I am a component plug for a http-server which plugs in a
    http resource containing a main.m3u8 iphone multibitrate playlsit.
    """

    def start(self, component):
        """
        @type component: L{HTTPFileStreamer}
        """
        if not isinstance(component, HTTPFileStreamer):
            raise ComponentStartError(
                "A MultibitratePlug %s must be plugged into a "
                " HTTPFileStreamer component, not a %s" % (
                self, component.__class__.__name__))
        log.debug('multibitrate', 'Attaching to %r' % (component, ))

        props = self.args['properties']
        resource = Resource()
        playlist = PlaylistResource(props.get('playlist-entry', []),
                                    props.get('target-bitrate', 200000))

        resource.putChild(props.get('playlist-name', 'main.m3u8'), playlist)
        component.setRootResource(resource)


def test():
    import sys
    from twisted.internet import reactor
    from twisted.python.log import startLogging
    from twisted.web.server import Site
    startLogging(sys.stderr)

    properties = {
        'playlist-entry': [
                  {'stream-url':
                   'http://example.com/iphone/low/stream.m3u8',
                   'bitrate': 100000},
                  {'stream-url':
                   'http://example.com/iphone/medium/stream.m3u8',
                   'bitrate': 200000},
                  {'stream-url':
                   'http://example.com/iphone/high/stream.m3u8',
                   'bitrate': 400000},
        ]}

    root = Resource()
    mount_point = Resource()
    playlist = PlaylistResource(properties['playlist-entry'])
    root.putChild('test', mount_point,)
    mount_point.putChild('main.m3u8', playlist)
    site = Site(root)

    reactor.listenTCP(8080, site)
    reactor.run()

if __name__ == "__main__":
    test()
