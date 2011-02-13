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

"""Wizard plugin for the html5 http plug
"""

import gettext
from zope.interface import implements

from flumotion.admin.assistant.interfaces import IHTTPConsumerPlugin, \
        IHTTPConsumerPluginLine
from flumotion.admin.assistant.models import HTTPServer, HTTPPlug, Muxer, \
        Encoder
from flumotion.ui.plugarea import WizardPlugLine

_ = gettext.gettext

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


class Html5HTTPPlug(HTTPPlug):
    """I am a model representing the configuration file for a
    HTML5 HTTP streaming plug.
    """
    plugType = "component-html5"

    # Component

    def getProperties(self):
        p = super(Html5HTTPPlug, self).getProperties()
        #TODO: find the encoders and muxer and pass in to the Html5HTTPPlug
        # find muxer
        muxer = self.streamer
        while not isinstance(muxer, Muxer):
            muxer = muxer.eaters[0]

        p.codecs = ""
        p.mime_type = ""
        if muxer.componentType == "ogg-muxer":
            p.mime_type = "video/ogg"
        elif muxer.componentType == "webm-muxer":
            p.mime_type = "video/webm"
        # now find the encoders
        for eater in muxer.eaters:
            encoder = eater
            codec = ""
            while not isinstance(encoder, Encoder):
                encoder = encoder.eaters[0]
            if encoder.componentType == "theora-encoder":
                codec = "theora"
            elif encoder.componentType == "vorbis-encoder":
                codec = "vorbis"
            elif encoder.componentType == "vp8-encoder":
                codec = "vp8"
            if p.codecs:
                p.codecs = "%s,%s" % (p.codecs, codec)
            else:
                p.codecs = codec 

        p.stream_url = self.streamer.getURL()

        width = 320
        height = 240
        if self.videoProducer:
            width = self.videoProducer.properties.width
            height = self.videoProducer.properties.height

        p.width = width
        p.height = height

        return p


class Html5HTTPServer(HTTPServer):
    """I am a model representing the configuration file for a
    HTTP server component which will be used to serve an html5 
    video watching page.
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
        super(Html5HTTPServer, self).__init__(mountPoint=mountPoint,
                                                worker=streamer.worker)

        porter = streamer.getPorter()
        self.properties.porter_socket_path = porter.getSocketPath()
        self.properties.porter_username = porter.getUsername()
        self.properties.porter_password = porter.getPassword()
        self.properties.port = porter.getPort()
        self.properties.type = 'slave'
        plug = Html5HTTPPlug(self, streamer, audioProducer, videoProducer)
        self.addPlug(plug)

    def getProperties(self):
        properties = super(Html5HTTPServer, self).getProperties()
        hostname = self.streamer.getHostname()
        if hostname:
            properties.hostname = hostname
        return properties


class Html5PlugLine(WizardPlugLine):
    implements(IHTTPConsumerPluginLine)
    gladeFile = ''

    def __init__(self, wizard, description):
        WizardPlugLine.__init__(self, wizard, None, description)
        self.setActive(True)

    def plugActiveChanged(self, active):
        pass

    def getConsumer(self, streamer, audioProducer, videoProducer):
        mountPoint = slashjoin(streamer.properties.mount_point, "html5/")
        return Html5HTTPServer(streamer, audioProducer,
                                 videoProducer, mountPoint)


class Html5WizardPlugin(object):
    implements(IHTTPConsumerPlugin)

    def __init__(self, wizard):
        self.wizard = wizard

    def getPlugWizard(self, description):
        return Html5PlugLine(self.wizard, description)
