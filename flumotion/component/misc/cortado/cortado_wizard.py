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

"""XXX
"""

from flumotion.wizard.models import HTTPServer, HTTPPlug

__version__ = "$Rev$"


class CortadoHTTPPlug(HTTPPlug):
    """I am a model representing the configuration file for a
    Cortado HTTP streaming plug.
    """
    plug_type = "cortado-plug"
    socket = "flumotion.component.misc.cortado.cortado.CortadoPlug"

    # Component

    def getProperties(self):
        p = super(CortadoHTTPPlug, self).getProperties()

        p.codebase = self.server.getCodebase()
        p.stream_url = self.streamer.getURL()
        p.has_video = self.video_producer is not None
        p.has_audio = self.audio_producer is not None

        width = 320
        height = 240
        framerate = 1
        if self.video_producer:
            width = self.video_producer.properties.width
            height = self.video_producer.properties.height
            framerate = self.video_producer.properties.framerate
            if '/' in framerate:
                nom, denom = framerate.split('/')
                framerate = int(float(nom)/float(denom))

        p.width = width
        p.height = height
        p.framerate = framerate
        p.buffer_size = 40

        return p


class CortadoHTTPServer(HTTPServer):
    """I am a model representing the configuration file for a
    HTTP server component which will be used to serve a cortado
    java applet.
    Most of the interesting logic here is actually in a plug.
    """
    component_type = 'http-server'
    def __init__(self, streamer, audio_producer, video_producer, mount_point):
        """
        @param streamer: streamer
        @type  streamer: L{HTTPStreamer}
        @param audio_producer: audio producer
        @type  audio_producer: L{flumotion.wizard.models.AudioProducer}
           subclass or None
        @param video_producer: video producer
        @type  video_producer: L{flumotion.wizard.models.VideoProducer}
           subclass or None
        @param mount_point:
        @type  mount_point:
        """
        self.streamer = streamer

        super(CortadoHTTPServer, self).__init__(mount_point=mount_point,
                                                worker=streamer.worker)

        self.properties.porter_socket_path = streamer.socket_path
        self.properties.porter_username = streamer.porter_username
        self.properties.porter_password = streamer.porter_password
        self.properties.type = 'slave'

        plug = CortadoHTTPPlug(self, streamer, audio_producer, video_producer)
        self.addPlug(plug)

    def getCodebase(self):
        """Returns the base of directory of the applet
        @returns: directory
        """
        return 'http://%s:%d%s/' % (self.worker,
                                    self.streamer.properties.port,
                                    self.properties.mount_point)


class CortadoWizardPlugin(object):
    def __init__(self, wizard):
        self.wizard = wizard

    def worker_changed(self, worker):
        d = self.wizard.run_in_worker(
            worker,
            'flumotion.worker.checks.cortado', 'checkCortado')
        def check(found):
            return bool(found)
        d.addCallback(check)
        return d

    def getConsumer(self, streamer, audio_producer, video_producer):
        return CortadoHTTPServer(streamer, audio_producer,
                                 video_producer, "/cortado")
