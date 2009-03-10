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

import os

from twisted.web.resource import Resource
from twisted.web.static import Data, File

from flumotion.common import log
from flumotion.common.errors import ComponentStartError
from flumotion.component.misc.httpserver.httpserver import HTTPFileStreamer
from flumotion.component.plugs.base import ComponentPlug
from flumotion.component.plugs.cortado.cortado_location import \
     getCortadoFilename
from flumotion.configure import configure

__version__ = "$Rev$"


def _htmlbool(value):
    if value:
        return 'true'
    return 'false'


class CortadoDirectoryResource(Resource):
    """I generate the directory used to serve a cortado applet
    It contains::
    - a html file, usually called index.html.
    - cortado.jar - cortado java applet
    """

    def __init__(self, mount_point, properties, filename):
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
        self._cortado_filename = filename
        self._addChildren()

    def _addChildren(self):
        self.putChild("cortado.jar",
                      File(self._cortado_filename,
                           'application/x-java-archive'))

        self.putChild(self._index_name,
                      self._index_content)

    def _get_template_filename(self):
        filename = self._properties.get('html-template')
        if not filename:
            filename = os.path.join(configure.datadir,
                                    'cortado-template.html')
        return filename

    def _get_index_content(self):
        html_template = self._get_template_filename()
        ns = {}
        ns['has-audio'] = _htmlbool(self._properties['has-audio'])
        ns['has-video'] = _htmlbool(self._properties['has-video'])
        for attribute in ['codebase',
                          'width',
                          'height',
                          'stream-url',
                          'buffer-size']:
            ns[attribute] = self._properties[attribute]

        data = open(html_template, 'r').read()
        content = data % ns
        return Data(content, 'text/html')

    # Resource

    def getChildWithDefault(self, pathEl, request):
        # Maps /index.html to /
        if request.uri == self._mount_point_root:
            return self._index_content
        return Resource.getChildWithDefault(self, pathEl, request)


class ComponentCortadoPlug(ComponentPlug):
    """I am a component plug for a http-server which plugs in a
    http resource containing a cortado java applet.
    """

    def start(self, component):
        """
        @type component: L{HTTPFileStreamer}
        """
        if not isinstance(component, HTTPFileStreamer):
            raise ComponentStartError(
                "A CortadoPlug %s must be plugged into a "
                " HTTPStreamer component, not a %s" % (
                self, component.__class__.__name__))
        filename = getCortadoFilename()
        if not filename:
            raise ComponentStartError(
                "Could not find cortado jar file")
        log.debug('cortado', 'Attaching to %r' % (component, ))
        resource = CortadoDirectoryResource(component.getMountPoint(),
                                            self.args['properties'],
                                            filename)
        component.setRootResource(resource)


def test():
    import sys
    from twisted.internet import reactor
    from twisted.python.log import startLogging
    from twisted.web.server import Site
    startLogging(sys.stderr)

    properties = {'has-audio': True,
                  'has-video': True,
                  'codebase': '/',
                  'width': 320,
                  'height': 240,
                  'stream-url': '/stream.ogg',
                  'buffer-size': 40}
    root = CortadoDirectoryResource('/', properties, getCortadoFilename())
    site = Site(root)

    reactor.listenTCP(8080, site)
    reactor.run()

if __name__ == "__main__":
    test()
