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

import gettext
import random

from flumotion.configure import configure
from flumotion.component.misc.cortado.cortado_location import CORTADO_FILENAME
from flumotion.wizard.basesteps import WorkerWizardStep
from flumotion.wizard.models import Component, Consumer, Plug

__version__ = "$Rev$"
_ = gettext.gettext
X_ = _

def _generateRandomString(numchars):
    """Generate a random US-ASCII string of length numchars
    """
    str = ""
    chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
    for _ in range(numchars):
        str += chars[random.randint(0, len(chars)-1)]

    return str


class HTTPPorter(Component):
    component_type = 'porter'
    def __init__(self, streamer):
        super(HTTPPorter, self).__init__(worker=streamer.worker)
        self.properties.socket_path = streamer.socket_path
        self.properties.port = streamer.properties.port
        self.properties.username = streamer.porter_username
        self.properties.password = streamer.porter_password

    # Component

    def getProperties(self):
        properties = super(HTTPPorter, self).getProperties()
        # FIXME: kiwi should do this.
        properties['port'] = int(properties['port'])
        return properties


class HTTPStreamer(Consumer):
    """
    @ivar has_client_limit: If a client limit was set
    @ivar has_bandwidth_limit: If a bandwidth limit was set
    @ivar has_cortado: If we should embed cortado
    @ivar socket_path: Path to the porter socket
    @ivar porter_username: Username for the porter
    @ivar porter_password: Password for the porter
    """
    component_type = 'http-streamer'
    def __init__(self):
        super(HTTPStreamer, self).__init__()
        self.has_client_limit = True
        self.has_bandwidth_limit = False
        self.has_cortado = False
        self.socket_path = '/tmp/flu-xxx.socket'
        self.porter_username = _generateRandomString(12)
        self.porter_password = _generateRandomString(12)

    def getURL(self):
        """Fetch the url to this stream
        @returns: the url
        """
        return 'http://%s:%d%s' % (
            self.properties.get('hostname', self.worker),
            self.properties.port,
            self.properties.mount_point)

    # Component

    def getProperties(self):
        properties = super(HTTPStreamer, self).getProperties()
        if self.has_bandwidth_limit:
            properties['bandwidth-limit'] = int(
                properties['bandwidth-limit'] * 1e6)
        else:
            del properties['bandwidth-limit']

        if not self.has_client_limit:
            del properties['client-limit']

        if self.has_cortado:
            properties['porter-socket-path'] = self.socket_path
            properties['porter-username'] = self.porter_username
            properties['porter-password'] = self.porter_password
            properties['type'] = 'slave'
            del properties['port']

        return properties


class CortadoPlug(Plug):
    plug_type = "cortado-plug"
    socket = "flumotion.component.misc.cortado.cortado.CortadoPlug"
    def __init__(self, server, streamer, audio_producer, video_producer):
        """
        @param server: server
        @type  server: L{CortadoHTTPServer}
        @param streamer: streamer
        @type  streamer: L{HTTPStreamer}
        @param audio_producer: audio producer
        @type  audio_producer: L{flumotion.wizard.models.AudioProducer} subclass or None
        @param video_producer: video producer
        @type  video_producer: L{flumotion.wizard.models.VideoProducer} subclass or None
        """
        super(CortadoPlug, self).__init__()
        self.server = server
        self.streamer = streamer
        self.audio_producer = audio_producer
        self.video_producer = video_producer

    # Component

    def getProperties(self):
        p = super(CortadoPlug, self).getProperties()

        p['codebase'] = self.server.getCodebase()
        p['stream-url'] = self.streamer.getURL()
        p['has-video'] = self.video_producer is not None
        p['has-audio'] = self.audio_producer is not None

        if self.video_producer:
            width = self.video_producer.properties.width
            height = self.video_producer.properties.height
            framerate = self.video_producer.properties.framerate
        else:
            width = 320
            height = 240
            framerate = 1

        p['width'] = width
        p['height'] = height
        p['framerate'] = framerate
        p['buffer-size'] = 40

        return p


class CortadoHTTPServer(Component):
    """
    This is a component which serves cortado on /cortado/index.html
    It shares the port of a http-streamer through a porter.
    """
    component_type = 'http-server'
    def __init__(self, streamer, audio_producer, video_producer):
        """
        @param streamer: streamer
        @type  streamer: L{HTTPStreamer}
        @param audio_producer: audio producer
        @type  audio_producer: L{flumotion.wizard.models.AudioProducer}
           subclass or None
        @param video_producer: video producer
        @type  video_producer: L{flumotion.wizard.models.VideoProducer}
           subclass or None
        """
        self.streamer = streamer

        super(CortadoHTTPServer, self).__init__(worker=streamer.worker)

        self.properties.mount_point = "/cortado"
        self.properties.porter_socket_path = streamer.socket_path
        self.properties.porter_username = streamer.porter_username
        self.properties.porter_password = streamer.porter_password
        self.properties.type = 'slave'

        plug = CortadoPlug(self, streamer, audio_producer, video_producer)
        self.addPlug(plug)

    def getCodebase(self):
        """Returns the base of directory of the applet
        @returns: directory
        """
        return 'http://%s:%d%s/' % (self.worker,
                                    self.streamer.properties.port,
                                    self.properties.mount_point)


class HTTPStep(WorkerWizardStep):
    glade_file = 'wizard_http.glade'
    section = _('Consumption')
    component_type = 'http-streamer'

    def __init__(self, wizard):
        self._blocked = False
        self.model = HTTPStreamer()
        WorkerWizardStep.__init__(self, wizard)

    def getStreamerConsumer(self):
        """Returns the http-streamer consumer model
        @returns: the streamer consumer
        """
        return self.model

    def getServerConsumer(self):
        """Returns the http-server consumer model or None
        if there will only a stream served.
        @returns: the server consumer or None
        """
        if not self.model.has_cortado:
            return None

        source_step = self.wizard.get_step('Source')

        return CortadoHTTPServer(self.model,
                                 source_step.get_audio_producer(),
                                 source_step.get_video_producer())

    def getPorter(self):
        """Returns the porter model or None if there will only a stream served.
        @returns: the porter or None
        """
        if not self.model.has_cortado:
            return None

        return HTTPPorter(self.model)

    # WizardStep

    def setup(self):
        self.port.data_type = int
        self.mount_point.data_type = str
        self.client_limit.data_type = int
        self.bandwidth_limit.data_type = float

        self.port.set_value(self.default_port)

        if self._canEmbedCortado():
            self.model.has_cortado = True
            self.has_cortado.show()

        self.add_proxy(self.model,
                       ['has_client_limit',
                        'has_bandwidth_limit',
                        'has_cortado'])

        self.add_proxy(self.model.properties,
                       ['port',
                        'client_limit',
                        'bandwidth_limit',
                        'mount_point',
                        'burst_on_connect'])

        self.mount_point.set_text("/")

    def activated(self):
        self._check_elements()
        self._verify()

    def worker_changed(self):
        self.model.worker = self.worker
        self._check_elements()

    def get_next(self):
        return self.wizard.get_step('Consumption').get_next(self)

    # Private

    def _canEmbedCortado(self):
        # Empty string means that it couldn't be found by configure
        if not CORTADO_FILENAME:
            return False

        encoding_step = self.wizard.get_step('Encoding')
        if encoding_step.get_muxer_type() not in [
            'ogg-muxer',
            'multipart-muxer']:
            return False

        audio_encoder = encoding_step.get_audio_encoder()
        if audio_encoder and audio_encoder.component_type not in [
            'vorbis-encoder',
            'mulaw-encoder']:
            return False

        video_encoder = encoding_step.get_video_encoder()
        if video_encoder and video_encoder.component_type not in [
            'theora-encoder',
            'jpeg-encoder',
            'smoke-encoder']:
            return False

        return True

    def _check_elements(self):
        def got_missing(missing):
            blocked = bool(missing)
            self._block_next(blocked)

        self._block_next(True)

        d = self.wizard.require_elements(self.worker, 'multifdsink')
        d.addCallback(got_missing)

    def _verify(self):
        self.client_limit.set_sensitive(
            self.has_client_limit.get_active())
        self.bandwidth_limit.set_sensitive(
            self.has_bandwidth_limit.get_active())
        self._update_blocked()

    def _block_next(self, blocked):
        if self._blocked == blocked:
            return
        self._blocked = blocked
        self.wizard.block_next(blocked)

    def _update_blocked(self):
        self.wizard.block_next(
            self._blocked or self.mount_point.get_text() == '')

    # Callbacks

    def on_mount_point_changed(self, entry):
        self._verify()
        self._block_next(self.model.has_cortado and entry.get_text() == "/")

    def on_has_client_limit_toggled(self, checkbutton):
        self._verify()

    def on_has_bandwidth_limit_toggled(self, checkbutton):
        self._verify()


class HTTPBothStep(HTTPStep):
    name = _('HTTP Streamer (audio & video)')
    sidebar_name = _('HTTP audio/video')
    default_port = configure.defaultStreamPortRange[0]


class HTTPAudioStep(HTTPStep):
    name = _('HTTP Streamer (audio only)')
    sidebar_name = _('HTTP audio')
    default_port = configure.defaultStreamPortRange[1]


class HTTPVideoStep(HTTPStep):
    name = _('HTTP Streamer (video only)')
    sidebar_name = _('HTTP video')
    default_port = configure.defaultStreamPortRange[2]


