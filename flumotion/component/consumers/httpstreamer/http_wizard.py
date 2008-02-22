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

"""HTTP wizard integration

This provides a step which you can chose:
- http port
- bandwidth/client limit
- mount point (eg, the url it will be accessed as)
- burst on connect
- cortado java applet

A component of type 'http-streamer' will always be created.
In addition, if you include the java applet, a 'porter' and
'http-server' will be included to share the port between the streamer
and the server and to serve an html file plus the java applet itself.
On the http-server the applet will be provided with help of a plug.
"""

import gettext
import os
import random

import gobject
from kiwi.utils import gsignal
import gtk

from flumotion.configure import configure
from flumotion.wizard.models import Component, Consumer
from flumotion.wizard.workerstep import WorkerWizardStep

__version__ = "$Rev$"
_ = gettext.gettext
N_ = _

def _generateRandomString(numchars):
    """Generate a random US-ASCII string of length numchars
    """
    s = ""
    chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
    for unused in range(numchars):
        s += chars[random.randint(0, len(chars)-1)]

    return s


class HTTPPorter(Component):
    """I am a model representing the configuration file for a
    HTTP porter component.
    """
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
        properties.port = int(properties.port)
        return properties


class HTTPStreamer(Consumer):
    """I am a model representing the configuration file for a
    HTTP streamer component.
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
        self.has_plugins = False
        self.socket_path = 'flu-%s.socket' % (_generateRandomString(6),)
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
            properties.bandwidth_limit = int(
                properties.bandwidth_limit * 1e6)
        else:
            del properties.bandwidth_limit

        if not self.has_client_limit:
            del properties.client_limit

        if self.has_plugins:
            properties.porter_socket_path = self.socket_path
            properties.porter_username = self.porter_username
            properties.porter_password = self.porter_password
            properties.type = 'slave'
            del properties.port

        return properties


class PlugPluginLine(gtk.VBox):
    """I am a line in the plug plugin area representing a single plugin.
    Rendered, I am visible as a checkbutton containing a label with the
    description of the plugin.
    Signals::
      - enable-changed: emitted when I am enabled/disabled
    @ivar plugin: plugin instance
    """
    gsignal('enable-changed')
    def __init__(self, plugin, description):
        """
        @param plugin: plugin instance
        @param description: description of the plugin
        """
        gtk.VBox.__init__(self)
        self.plugin = plugin
        self.checkbutton = gtk.CheckButton(description)
        self.checkbutton.connect('toggled',
                                 self._on_checkbutton__toggled)
        self.checkbutton.set_active(True)
        self.pack_start(self.checkbutton)
        self.checkbutton.show()

    def isEnabled(self):
        """Find out if the plugin is going to be enabled or not
        @returns: enabled
        @rtype: bool
        """
        return self.checkbutton.get_active()

    def _on_checkbutton__toggled(self, checkbutton):
        self.emit('enable-changed')
gobject.type_register(PlugPluginLine)


class PlugPluginArea(gtk.VBox):
    """I am plugin area representing all available plugins. I keep track
    of the plugins and their internal state. You can ask me to add new plugins
    or get the internal models of the plugins.
    """
    def __init__(self, streamer):
        self.streamer = streamer
        gtk.VBox.__init__(self, spacing=6)
        self._lines = []

    # Public

    def addPlug(self, plugin, description):
        """Add a plug, eg a checkbutton with a description such as
        'Cortado Java applet'.
        @param plugin: plugin instance
        @param description: label description
        """
        line = PlugPluginLine(plugin, description)
        line.connect('enable-changed', self._on_plugline__enable_changed)
        self._lines.append(line)
        self.pack_start(line, False, False)
        line.show()
        self._updateStreamer()

    def getPorters(self):
        """Fetch a list of porters which are going to be used by all
        available plugins.
        @returns: porters
        @rtype: a sequence of L{HTTPPorters}
        """
        for unused in self._getEnabledPlugins():
            yield HTTPPorter(self.streamer)

    def getServerConsumers(self, audio_producer, video_producer):
        """Fetch a list of server consumers which are going to be used by all
        available plugins.
        @returns: consumers
        @rtype: a sequence of L{HTTPServer} subclasses
        """
        for plugin in self._getEnabledPlugins():
            yield plugin.getConsumer(self.streamer, audio_producer,
                                     video_producer)

    # Private

    def _hasEnabledPlugins(self):
        for line in self._lines:
            if line.isEnabled():
                return True
        return False

    def _getEnabledPlugins(self):
        for line in self._lines:
            if line.isEnabled():
                yield line.plugin

    def _updateStreamer(self):
        self.streamer.has_plugins = self._hasEnabledPlugins()

    # Callbacks

    def _on_plugline__enable_changed(self, line):
        self._updateStreamer()

class HTTPStep(WorkerWizardStep):
    """I am a step of the configuration wizard which allows you
    to configure a stream to be served over HTTP.
    """
    glade_file = os.path.join(
        os.path.dirname(
        os.path.abspath(__file__)),
        'http-wizard.glade')

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

    def getServerConsumers(self):
        """Returns the http-server consumer model or None
        if there will only a stream served.
        @returns: the server consumer or None
        """
        source_step = self.wizard.get_step('Source')
        return self.plugarea.getServerConsumers(
           source_step.get_audio_producer(),
           source_step.get_video_producer())

    def getPorters(self):
        """Returns the porter model or None if there will only a stream served.
        @returns: the porter or None
        """
        return self.plugarea.getPorters()

    # WizardStep

    def setup(self):
        self.port.data_type = int
        self.mount_point.data_type = str
        self.client_limit.data_type = int
        self.bandwidth_limit.data_type = float

        self.port.set_value(self.default_port)

        self.plugarea = PlugPluginArea(self.model)
        self.main_vbox.pack_start(self.plugarea, False, False)
        self.plugarea.show()

        self._populate_plugins()

        self.add_proxy(self.model,
                       ['has_client_limit',
                        'has_bandwidth_limit'])

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

    def worker_changed(self, worker):
        self.model.worker = worker
        self._check_elements()

    def get_next(self):
        return self.wizard.get_step('Consumption').get_next(self)

    # Private

    def _populate_plugins(self):
        def got_entries(entries):
            for entry in entries:
                def response(factory, entry):
                    plugin = factory(self.wizard)
                    if hasattr(plugin, 'worker_changed'):
                        d = plugin.worker_changed(self.worker)
                        def cb(found, plugin, entry):
                            if found:
                                self._addPlug(plugin, entry)
                        d.addCallback(cb, plugin, entry)
                    else:
                        self._addPlug(plugin, entry)
                d = self.wizard.get_wizard_plug_entry(entry.component_type)
                d.addCallback(response, entry)

        d = self.wizard._admin.getWizardEntries(
            wizard_types=['http-consumer'])
        d.addCallback(got_entries)

    def _addPlug(self, plugin, entry):
        # This function filters out entries which are
        # not matching the accepted media types of the entry
        muxerTypes = []
        audioTypes = []
        videoTypes = []
        for mediaType in entry.getAcceptedMediaTypes():
            kind, name = mediaType.split(':', 1)
            if kind == 'muxer':
                muxerTypes.append(name)
            elif kind == 'video':
                videoTypes.append(name)
            elif kind == 'audio':
                audioTypes.append(name)
            else:
                raise AssertionError

        encoding_step = self.wizard.get_step('Encoding')
        if encoding_step.get_muxer_format() not in muxerTypes:
            return

        audio_format = encoding_step.get_audio_format()
        video_format = encoding_step.get_video_format()
        if ((audio_format and audio_format not in audioTypes) or
            (video_format and video_format not in videoTypes)):
            return

        self.plugarea.addPlug(plugin, N_(entry.description))

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


