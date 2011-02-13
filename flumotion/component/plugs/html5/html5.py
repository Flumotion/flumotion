# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2008 Fluendo, S.L. (www.fluendo.com).
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

from twisted.web.resource import Resource
from twisted.web.static import Data

from flumotion.common import log
from flumotion.common.errors import ComponentStartError
from flumotion.component.misc.httpserver.httpserver import HTTPFileStreamer
from flumotion.component.plugs.base import ComponentPlug

__version__ = "$Rev$"

HTML5TEMPLATE = \
"""
<html>
<head><title>Flumotion Stream</title></head>
<body>
<video height="%(height)d" width="%(width)d" controls autoplay>
<source type='%(mime-type)s; codecs="%(codecs)s"' src="%(stream-url)s">
</source>
</video>
</body>
"""


def _htmlbool(value):
    if value:
        return 'true'
    return 'false'


class Html5DirectoryResource(Resource):
    """I generate the directory used to serve an html5 viewing page
    It contains::
    - a html file, usually called index.html.
    """

    def __init__(self, mount_point, properties):
        Resource.__init__(self)

        index_name = properties.get('index', 'index.html')

        root = mount_point
        if not root.endswith("/"):
            root += "/"
        if index_name != 'index.html':
            root = None
        self._mount_point_root = root
        self._properties = properties
        self._index_content = self._get_index_content()
        self._index_name = index_name
        self._addChildren()

    def _addChildren(self):
        self.putChild(self._index_name,
                      self._index_content)
        self.putChild('', self._index_content)

    def _get_index_content(self):
        ns = {}
        for attribute in ['codecs',
                          'mime-type',
                          'width',
                          'height',
                          'stream-url']:
            ns[attribute] = self._properties[attribute]

        content = HTML5TEMPLATE % ns
        return Data(content, 'text/html')


class ComponentHtml5Plug(ComponentPlug):
    """I am a component plug for a http-server which plugs in a
    http resource containing a html5 viewing page.
    """

    def start(self, component):
        """
        @type component: L{HTTPFileStreamer}
        """
        if not isinstance(component, HTTPFileStreamer):
            raise ComponentStartError(
                "An HTML5Plug %s must be plugged into a "
                " HTTPFileStreamer component, not a %s" % (
                self, component.__class__.__name__))
        log.debug('html5', 'Attaching to %r' % (component, ))
        resource = Html5DirectoryResource(component.getMountPoint(),
                                          self.args['properties'])
        component.setRootResource(resource)


def test():
    import sys
    from twisted.internet import reactor
    from twisted.python.log import startLogging
    from twisted.web.server import Site
    startLogging(sys.stderr)

    properties = {'width': 320,
                  'height': 240,
                  'stream-url': '/stream.ogg',
                  'buffer-size': 40}
    root = Html5DirectoryResource('/', properties)
    site = Site(root)

    reactor.listenTCP(8080, site)
    reactor.run()

if __name__ == "__main__":
    test()
