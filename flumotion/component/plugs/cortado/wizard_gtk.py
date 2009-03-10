# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2004,2005,2006,2007,2008 Fluendo, S.L. (www.fluendo.com).
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

"""Wizard plugin for the cortado http plug
"""

from zope.interface import implements

from flumotion.admin.assistant.interfaces import IHTTPConsumerPlugin
from flumotion.admin.assistant.models import HTTPServer, HTTPPlug
from flumotion.common.fraction import fractionAsFloat, fractionFromValue

__version__ = "$Rev$"

# Copied from posixpath.py


def slashjoin(a, *p):
    """Join two or more pathname components, inserting '/' as needed"""
    path = a
    for b in p:
        if b.startswith('/'):
            path = b
        elif path == '' or path.endswith('/'):
            path += b
        else:
            path += '/' + b
    return path


class CortadoHTTPPlug(HTTPPlug):
    """I am a model representing the configuration file for a
    Cortado HTTP streaming plug.
    """
    plugType = "component-cortado"

    # Component

    def getProperties(self):
        p = super(CortadoHTTPPlug, self).getProperties()

        p.codebase = self.server.getCodebase()
        p.stream_url = self.streamer.getURL()
        p.has_video = self.videoProducer is not None
        p.has_audio = self.audioProducer is not None

        width = 320
        height = 240
        if self.videoProducer:
            width = self.videoProducer.properties.width
            height = self.videoProducer.properties.height

        p.width = width
        p.height = height
        p.buffer_size = 40

        return p


class CortadoHTTPServer(HTTPServer):
    """I am a model representing the configuration file for a
    HTTP server component which will be used to serve a cortado
    java applet.
    Most of the interesting logic here is actually in a plug.
    """
    componentType = 'http-server'

    def __init__(self, streamer, audioProducer, videoProducer, mountPoint):
        """
        @param streamer: streamer
        @type  streamer: L{HTTPStreamer}
        @param audioProducer: audio producer
        @type  audioProducer: L{flumotion.admin.assistant.models.AudioProducer}
           subclass or None
        @param videoProducer: video producer
        @type  videoProducer: L{flumotion.admin.assistant.models.VideoProducer}
           subclass or None
        @param mountPoint:
        @type  mountPoint:
        """
        self.streamer = streamer

        super(CortadoHTTPServer, self).__init__(mountPoint=mountPoint,
                                                worker=streamer.worker)

        porter = streamer.getPorter()
        self.properties.porter_socket_path = porter.getSocketPath()
        self.properties.porter_username = porter.getUsername()
        self.properties.porter_password = porter.getPassword()
        self.properties.port = porter.getPort()
        self.properties.type = 'slave'
        plug = CortadoHTTPPlug(self, streamer, audioProducer, videoProducer)
        self.addPlug(plug)

    def getCodebase(self):
        """Returns the base of directory of the applet
        @returns: directory
        """
        return 'http://%s:%d%s' % (self.streamer.hostname,
                                   self.properties.port,
                                   self.properties.mount_point)

    def getProperties(self):
        properties = super(CortadoHTTPServer, self).getProperties()
        hostname = self.streamer.getHostname()
        if hostname:
            properties.hostname = hostname
        return properties


class CortadoWizardPlugin(object):
    implements(IHTTPConsumerPlugin)

    def __init__(self, wizard):
        self.wizard = wizard

    def workerChanged(self, worker):
        d = self.wizard.runInWorker(
            worker,
            'flumotion.worker.checks.cortado', 'checkCortado')

        def check(found):
            return bool(found)
        d.addCallback(check)
        return d

    def getConsumer(self, streamer, audioProducer, videoProducer):
        mountPoint = slashjoin(streamer.properties.mount_point,
                               "cortado/")
        return CortadoHTTPServer(streamer, audioProducer,
                                 videoProducer,
                                 mountPoint)
