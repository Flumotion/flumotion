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
from twisted.internet import defer

from flumotion.common import errors, log
from flumotion.common.messages import N_, ngettext, gettexter, Warning
from flumotion.configure import configure
from flumotion.wizard.models import Component, Consumer
from flumotion.wizard.basesteps import ConsumerStep

__version__ = "$Rev$"
_ = gettext.gettext
T_ = gettexter('flumotion')

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
    @ivar hostname: the hostname this will be streamed on
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
        self.properties.burst_on_connect = False
        self.hostname = None

    def getURL(self):
        """Fetch the url to this stream
        @returns: the url
        """
        return 'http://%s:%d%s' % (
            self.properties.get('hostname', self.hostname),
            self.properties.port,
            self.properties.mount_point)

    # Component

    def getProperties(self):
        properties = super(HTTPStreamer, self).getProperties()
        if self.has_bandwidth_limit:
            properties.bandwidth_limit = int(
                properties.bandwidth_limit * 1e6)
        else:
            if 'bandwidth_limit' in properties:
                del properties.bandwidth_limit

        if not self.has_client_limit:
            if 'client_limit' in properties:
                del properties.client_limit

        if self.has_plugins:
            properties.porter_socket_path = self.socket_path
            properties.porter_username = self.porter_username
            properties.porter_password = self.porter_password
            properties.type = 'slave'

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


class HTTPStep(ConsumerStep):
    """I am a step of the configuration wizard which allows you
    to configure a stream to be served over HTTP.
    """
    gladeFile = os.path.join(
        os.path.dirname(
        os.path.abspath(__file__)),
        'wizard.glade')

    def __init__(self, wizard):
        self.model = HTTPStreamer()
        ConsumerStep.__init__(self, wizard)

    # ConsumerStep

    def getConsumerModel(self):
        return self.model

    def getComponentType(self):
        return 'http-streamer'

    def getServerConsumers(self):
        source_step = self.wizard.getStep('Production')
        return self.plugarea.getServerConsumers(
           source_step.getAudioProducer(),
           source_step.getVideoProducer())

    def getPorters(self):
        return self.plugarea.getPorters()

    # WizardStep

    def setup(self):
        self.port.data_type = int
        self.client_limit.data_type = int
        self.bandwidth_limit.data_type = float
        self.mount_point.data_type = str
        self.burst_on_connect.data_type = bool

        self.model.properties.port = self.default_port

        self.plugarea = PlugPluginArea(self.model)
        self.main_vbox.pack_start(self.plugarea, False, False)
        self.plugarea.show()

        self._populatePlugins()

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
        self._checkElements()
        self._verify()

    def workerChanged(self, worker):
        self.model.worker = worker
        self._checkElements()

    # Private

    def _populatePlugins(self):
        def gotEntries(entries):
            log.debug('httpwizard', 'got %r' % (entries,))
            for entry in entries:
                if not self._canAddPlug(entry):
                    continue
                def response(factory, entry):
                    # FIXME: verify that factory implements IHTTPConsumerPlugin
                    plugin = factory(self.wizard)
                    if hasattr(plugin, 'workerChanged'):
                        d = plugin.workerChanged(self.worker)
                        def cb(found, plugin, entry):
                            if found:
                                self._addPlug(
                                    plugin, N_(entry.description))
                        d.addCallback(cb, plugin, entry)
                    else:
                        self._addPlug(plugin, N_(entry.description))
                d = self.wizard.getWizardPlugEntry(entry.component_type)
                d.addCallback(response, entry)

        d = self.wizard.getWizardEntries(wizardTypes=['http-consumer'])
        d.addCallbacks(gotEntries)

    def _canAddPlug(self, entry):
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

        encoding_step = self.wizard.getStep('Encoding')
        if encoding_step.getMuxerFormat() not in muxerTypes:
            return False

        audioFormat = encoding_step.getAudioFormat()
        videoFormat = encoding_step.getVideoFormat()
        if ((audioFormat and audioFormat not in audioTypes) or
            (videoFormat and videoFormat not in videoTypes)):
            return False

        return True

    def _addPlug(self, plugin, description):
        self.plugarea.addPlug(plugin, description)

    def _checkElements(self):
        self.wizard.waitForTask('http streamer check')

        def importError(failure):
            print 'FIXME: trap', failure, 'in .../httpstreamer/wizard_gtk.py'
            self.info('could not import twisted-web')
            message = Warning(T_(N_(
                "Worker '%s' cannot import module '%s'."),
                self.worker, 'twisted.web'))
            message.add(T_(N_("\nThis module is part of the '%s'."),
                           'Twisted Project'))
            message.add(T_(N_("\nThe project's homepage is %s"),
                           'http://www.twistedmatrix.com/'))
            message.id = 'module-twisted-web'
            self.wizard.add_msg(message)
            self.wizard.taskFinished(True)

        def finished(hostname):
            self.model.hostname = hostname
            self.wizard.taskFinished()

        def checkWorkerHostname(unused):
            d = self.wizard.runInWorker(
                self.worker, 'flumotion.worker.checks.http',
                'runHTTPStreamerChecks')
            d.addCallback(finished)

        def checkElements(elements):
            if elements:
                f = ngettext("Worker '%s' is missing GStreamer element '%s'.",
                    "Worker '%s' is missing GStreamer elements '%s'.",
                    len(elements))
                message = Warning(
                    T_(f, self.worker, "', '".join(elements)), id='httpstreamer')
                self.wizard.add_msg(message)
                self.wizard.taskFinished(True)
                return defer.fail(errors.FlumotionError('missing multifdsink element'))

            self.wizard.clear_msg('httpstreamer')

            # now check import
            d = self.wizard.checkImport(self.worker, 'twisted.web')
            d.addCallback(checkWorkerHostname)
            d.addErrback(importError)

        # first check elements
        d = self.wizard.requireElements(self.worker, 'multifdsink')
        d.addCallback(checkElements)

        # requireElements calls checkElements which unconditionally
        # unblocks the next call. Work around that behavior here.
        d.addErrback(lambda unused: self.wizard.taskFinished(True))

    def _verify(self):
        self.client_limit.set_sensitive(
            self.has_client_limit.get_active())
        self.bandwidth_limit.set_sensitive(
            self.has_bandwidth_limit.get_active())
        self._update_blocked()

    def _update_blocked(self):
        # FIXME: This should be updated and only called when all pending
        #        tasks are done.
        self.wizard.blockNext(
            self.wizard.pendingTask() or self.mount_point.get_text() == '')

    # Callbacks

    def on_mount_point_changed(self, entry):
        self._verify()
        self.wizard.blockNext(self.model.has_cortado and entry.get_text() == "/")

    def on_has_client_limit_toggled(self, checkbutton):
        self._verify()

    def on_has_bandwidth_limit_toggled(self, checkbutton):
        self._verify()


class HTTPBothStep(HTTPStep):
    name = _('HTTP Streamer (audio & video)')
    sidebarName = _('HTTP audio/video')
    default_port = configure.defaultStreamPortRange[0]

    # ConsumerStep

    def getConsumerType(self):
        return 'audio-video'


class HTTPAudioStep(HTTPStep):
    name = _('HTTP Streamer (audio only)')
    sidebarName = _('HTTP audio')
    default_port = configure.defaultStreamPortRange[1]

    # ConsumerStep

    def getConsumerType(self):
        return 'audio'


class HTTPVideoStep(HTTPStep):
    name = _('HTTP Streamer (video only)')
    sidebarName = _('HTTP video')
    default_port = configure.defaultStreamPortRange[2]

    # ConsumerStep

    def getConsumerType(self):
        return 'video'

