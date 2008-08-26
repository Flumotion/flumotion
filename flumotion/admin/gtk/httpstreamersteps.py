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

import gobject
from kiwi.utils import gsignal
import gtk
from twisted.internet import defer

from flumotion.admin.assistant.models import Consumer
from flumotion.admin.gtk.basesteps import ConsumerStep
from flumotion.common import errors, log, messages
from flumotion.common.i18n import N_, gettexter, ngettext

__version__ = "$Rev$"
_ = gettext.gettext
T_ = gettexter()


class HTTPStreamer(Consumer):
    """I am a model representing the configuration file for a
    HTTP streamer component.
    @ivar has_client_limit: If a client limit was set
    @ivar has_bandwidth_limit: If a bandwidth limit was set
    @ivar has_cortado: If we should embed cortado
    @ivar hostname: the hostname this will be streamed on
    """
    componentType = 'http-streamer'

    def __init__(self, common):
        super(HTTPStreamer, self).__init__()
        self._common = common
        self.has_cortado = False
        self.has_plugins = False
        self.hostname = None

    # Public

    def getURL(self):
        """Fetch the url to this stream
        @returns: the url
        """
        return 'http://%s:%d%s' % (
            self.properties.get('hostname', self.hostname),
            self.getPorter().getPort(),
            self.properties.mount_point)

    # Component

    def getProperties(self):
        properties = super(HTTPStreamer, self).getProperties()
        if self._common.has_bandwidth_limit:
            properties.bandwidth_limit = int(
                self._common.bandwidth_limit * 1e6)

        porter = self.getPorter()
        properties.porter_socket_path = porter.getSocketPath()
        properties.porter_username = porter.getUsername()
        properties.porter_password = porter.getPassword()
        properties.type = 'slave'
        properties.burst_on_connect = self._common.burst_on_connect

        return properties

    # Private

    def _getPort(self):
        return self._common.port


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


class HTTPSpecificStep(ConsumerStep):
    """I am a step of the configuration wizard which allows you
    to configure a stream to be served over HTTP.
    """
    gladeFile = 'httpstreamer-wizard.glade'

    def __init__(self, wizard):
        consumptionStep = wizard.getStep('Consumption')
        self.model = HTTPStreamer(consumptionStep.getHTTPCommon())
        self.model.setPorter(consumptionStep.getHTTPPorter())
        ConsumerStep.__init__(self, wizard)

    # ConsumerStep

    def getConsumerModel(self):
        return self.model

    def getComponentType(self):
        return 'http-streamer'

    def getServerConsumers(self):
        return self.plugarea.getServerConsumers(
           self.wizard.getAudioProducer(),
           self.wizard.getVideoProducer())

    def getDefaultMountPath(self):
        encodingStep = self.wizard.getStep('Encoding')
        return '/%s-%s/' % (str(encodingStep.getMuxerFormat()),
                            self.getConsumerType(), )

    # WizardStep

    def setup(self):
        self.mount_point.data_type = str

        self.plugarea = PlugPluginArea(self.model)
        self.main_vbox.pack_start(self.plugarea, False, False)
        self.plugarea.show()

        self._populatePlugins()

        self.model.properties.mount_point = self.getDefaultMountPath()
        self.add_proxy(self.model.properties, ['mount_point'])

    def activated(self):
        self._checkElements()
        self._verify()

    def workerChanged(self, worker):
        self.model.worker = worker
        self._checkElements()

    # Private

    def _populatePlugins(self):

        def gotEntries(entries):
            log.debug('httpwizard', 'got %r' % (entries, ))
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
                d = self.wizard.getWizardPlugEntry(entry.componentType)
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
            message = messages.Warning(T_(N_(
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
                message = messages.Warning(
                    T_(f, self.worker, "', '".join(elements)),
                    id='httpstreamer')
                self.wizard.add_msg(message)
                self.wizard.taskFinished(True)
                return defer.fail(errors.FlumotionError(
                    'missing multifdsink element'))

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
        self._update_blocked()

    def _update_blocked(self):
        # FIXME: This should be updated and only called when all pending
        #        tasks are done.
        self.wizard.blockNext(
            self.wizard.pendingTask() or self.mount_point.get_text() == '')

    # Callbacks

    def on_mount_point_changed(self, entry):
        self._verify()
        self.wizard.blockNext(self.model.has_cortado and
                              entry.get_text() == self.getDefaultMountPath())


class HTTPBothStep(HTTPSpecificStep):
    name = 'HTTPStreamerBoth'
    title = _('HTTP Streamer (Audio and Video)')
    sidebarName = _('HTTP Audio/Video')
    docSection = 'help-configuration-assistant-http-streaming-both'
    docAnchor = ''
    docVersion = 'local'

    # ConsumerStep

    def getConsumerType(self):
        return 'audio-video'


class HTTPAudioStep(HTTPSpecificStep):
    name = 'HTTPStreamerAudio'
    title = _('HTTP Streamer (Audio Only)')
    sidebarName = _('HTTP Audio')
    docSection = 'help-configuration-assistant-http-streaming-audio-only'
    docAnchor = ''
    docVersion = 'local'

    # ConsumerStep

    def getConsumerType(self):
        return 'audio'


class HTTPVideoStep(HTTPSpecificStep):
    name = 'HTTPStreamerVideo'
    title = _('HTTP Streamer (Video Only)')
    sidebarName = _('HTTP Video')
    docSection = 'help-configuration-assistant-http-streaming-video-only'
    docAnchor = ''
    docVersion = 'local'

    # ConsumerStep

    def getConsumerType(self):
        return 'video'
