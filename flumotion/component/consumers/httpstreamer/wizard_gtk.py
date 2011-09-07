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
import re
import os

import gobject
from kiwi.utils import gsignal
import gtk
from twisted.internet import defer
from zope.interface import implements

from flumotion.admin.assistant.interfaces import IConsumerPlugin
from flumotion.admin.assistant.models import Consumer, Porter
from flumotion.admin.gtk.basesteps import ConsumerStep
from flumotion.configure import configure
from flumotion.common import errors, log, messages
from flumotion.common.i18n import N_, gettexter, ngettext

__version__ = "$Rev$"
_ = gettext.gettext
T_ = gettexter()


class HTTPStreamer(Consumer):
    """I am a model representing the configuration file for a
    HTTP streamer component.
    @ivar has_client_limit: If a client limit was set
    @ivar client_limit: The client limit
    @ivar has_bandwidth_limit: If a bandwidth limit was set
    @ivar bandwidth_limit: The bandwidth limit
    @ivar set_hostname: If a hostname was set
    @ivar hostname: the hostname this will be streamed on
    @ivar port: The port this server will be listening to
    """
    componentType = 'http-streamer'
    requiresPorter = True
    prefix = 'http'

    def __init__(self):
        super(HTTPStreamer, self).__init__()

        self.setPorter(
            Porter(worker=None, port=configure.defaultHTTPStreamPort))

        self.has_client_limit = False
        self.client_limit = 1000
        self.has_bandwidth_limit = False
        self.bandwidth_limit = 500.0
        self.set_hostname = False
        self.hostname = ''
        self.port = None

        self.properties.burst_on_connect = False

    # Public

    def getURL(self):
        """Fetch the url to this stream
        @returns: the url
        """
        return 'http://%s:%d%s' % (
            self.getHostname(),
            self.getPorter().getPort(),
            self.properties.mount_point)

    def getHostname(self):
        """Fetch the hostname this stream will be published on
        @returns: the hostname
        """
        return self.hostname

    def setData(self, model):
        """
        Sets the data from another model so we can reuse it.

        @param model : model to get the data from
        @type  model : L{HTTPStreamer}
        """
        self.has_client_limit = model.has_client_limit
        self.has_bandwidth_limit = model.has_bandwidth_limit
        self.client_limit = model.client_limit
        self.bandwidth_limit = model.bandwidth_limit
        self.set_hostname = model.set_hostname
        self.hostname = model.hostname
        self.properties.burst_on_connect = model.properties.burst_on_connect
        self.port = model.port

    # Component

    def getPorter(self):
        """
        Obtains this streamer's porter model.
        """
        porter = Consumer.getPorter(self)
        porter.worker = self.worker
        if self.port:
            porter.properties.port = self.port
        return porter

    def getProperties(self):
        properties = super(HTTPStreamer, self).getProperties()
        if self.has_bandwidth_limit:
            properties.bandwidth_limit = int(self.bandwidth_limit * 1e6)
        if self.has_client_limit:
            properties.client_limit = self.client_limit

        porter = self.getPorter()
        hostname = self.getHostname()
        if hostname and self.set_hostname:
            properties.hostname = hostname
        properties.porter_socket_path = porter.getSocketPath()
        properties.porter_username = porter.getUsername()
        properties.porter_password = porter.getPassword()
        properties.type = 'slave'
        # FIXME: Try to maintain the port empty when we are slave. Needed
        # for now as the adminwindow tab shows the URL based on this property.
        properties.port = self.port or self.getPorter().getProperties().port

        return properties


class HTTPSpecificStep(ConsumerStep):
    """I am a step of the configuration wizard which allows you
    to configure a stream to be served over HTTP.
    """
    section = _('Consumption')
    gladeFile = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              'wizard.glade')

    def __init__(self, wizard):
        self.model = HTTPStreamer()
        ConsumerStep.__init__(self, wizard)

    def updateModel(self, model):
        """
        There is a previous httpstreamer step from where the data can be copied
        It will be copied to the actual model and the advanced
        tab would be hidden.

        @param model: The previous model we are going to copy.
        @type  model: L{HTTPStreamer}
        """
        self.model.setData(model)
        self.expander.set_expanded(False)
        self._proxy2.set_model(self.model)

    # ConsumerStep

    def getConsumerModel(self):
        return self.model

    def getServerConsumers(self):
        for line in self.plugarea.getEnabledLines():
            yield line.getConsumer(self.model,
                self.wizard.getScenario().getAudioProducer(self.wizard),
                self.wizard.getScenario().getVideoProducer(self.wizard))

    # WizardStep

    def setup(self):
        self.mount_point.data_type = str
        self.bandwidth_limit.data_type = float
        self.burst_on_connect.data_type = bool
        self.client_limit.data_type = int
        self.port.data_type = int
        self.hostname.data_type = str

        self.model.properties.mount_point = self._getDefaultMountPath()
        self._proxy1 = self.add_proxy(self.model.properties,
                                      ['mount_point', 'burst_on_connect'])
        self._proxy2 = self.add_proxy(
            self.model, ['has_client_limit',
                         'has_bandwidth_limit',
                         'client_limit',
                         'bandwidth_limit',
                         'set_hostname',
                         'hostname',
                         'port'])

        self.client_limit.set_sensitive(self.model.has_client_limit)
        self.bandwidth_limit.set_sensitive(self.model.has_bandwidth_limit)
        self.hostname.set_sensitive(self.model.set_hostname)

        self.port.connect('changed', self.on_port_changed)
        self.mount_point.connect('changed', self.on_mount_point_changed)

    def workerChanged(self, worker):
        self.model.worker = worker
        d = self._runChecks()
        d.addCallback(self._populatePlugins)
        return d

    def getNext(self):

        def setModel(next):
            if next and next.model.componentType == self.model.componentType:
                next.updateModel(self.model)
            return next
        d = defer.maybeDeferred(ConsumerStep.getNext, self)
        d.addCallback(setModel)
        return d

    # Private

    def _getDefaultMountPath(self):
        encodingStep = self.wizard.getStep('Encoding')
        return '/%s-%s/' % (str(encodingStep.getMuxerFormat()),
                            self.getConsumerType(), )

    def _suggestMountPoint(self, mountPoint):
        # FIXME: Generalise this method and use the same in f.a.a.save module.
        # Resolve naming conflicts, using a simple algorithm
        # First, find all the trailing digits, for instance in
        # 'audio-producer42' -> '42'
        mountPoint = mountPoint.rstrip('/')

        pattern = re.compile('(\d*$)')
        match = pattern.search(mountPoint)
        trailingDigit = match.group()

        # Now if we had a digit in the end, convert it to
        # a number and increase it by one and remove the trailing
        # digits the existing component name
        if trailingDigit:
            digit = int(trailingDigit) + 1
            mountPoint = mountPoint[:-len(trailingDigit)]
        # No number in the end, use 2 the first one so we end up
        # with 'audio-producer' and 'audio-producer2' in case of
        # a simple conflict
        else:
            digit = 2
        return mountPoint + str(digit) + '/'

    def _populatePlugins(self, canPopulate):
        if not canPopulate:
            return

        self.plugarea.clean()

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
                            self._addPlug(plugin.getPlugWizard(
                                N_(entry.description)), found)
                        d.addCallback(cb, plugin, entry)
                    else:
                        self._addPlug(plugin.getPlugWizard(
                            N_(entry.description)), True)
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

    def _addPlug(self, plugin, enabled):
        plugin.setEnabled(enabled)
        self.plugarea.addLine(plugin)

    def _runChecks(self):
        self.wizard.waitForTask('http streamer check')

        def hostnameErrback(failure):
            failure.trap(errors.RemoteRunError)
            self.wizard.taskFinished(blockNext=True)
            return False

        def gotHostname(hostname):
            self.model.hostname = hostname
            self._proxy2.update('hostname')
            self.wizard.taskFinished()
            return True

        def getHostname(result):
            if not result:
                return False

            d = self.wizard.runInWorker(
                    self.worker, 'flumotion.worker.checks.http',
                    'runHTTPStreamerChecks')
            d.addCallback(gotHostname)
            d.addErrback(hostnameErrback)
            return d

        def checkImport(elements):
            if elements:
                self.wizard.taskFinished(blockNext=True)
                return False

            d = self.wizard.requireImport(
                    self.worker, 'twisted.web', projectName='Twisted project',
                    projectURL='http://www.twistedmatrix.com/')
            d.addCallback(getHostname)
            return d

        # first check elements
        d = self.wizard.requireElements(self.worker, 'multifdsink')
        d.addCallback(checkImport)
        return d

    def _checkMountPoint(self, port=None, worker=None,
                         mount_point=None, need_fix=False):
        """
        Checks whether the provided mount point is available with the
        current configuration (port, worker). It can provide a valid
        mountpoint if it is required with need_fix=True.

        @param port : The port the streamer is going to be listening.
        @type  port : int
        @param worker : The worker the streamer will be running.
        @type  worker : str
        @param mount_point : The desired mount point.
        @type  mount_point : str
        @param need_fix : Whether the method should search for a valid
                          mount_point if the provided one is not.
        @type  need_fix : bool

        @returns : True if the mount_point can be used, False if it is in use.
        @rtype   : bool
        """
        self.wizard.clear_msg('http-streamer-mountpoint')

        port = port or self.model.port
        worker = worker or self.model.worker
        mount_point = mount_point or self.model.properties.mount_point

        self.wizard.waitForTask('http-streamer-mountpoint')

        if self.wizard.addMountPoint(worker, port, mount_point,
                                     self.getConsumerType()):
            self.wizard.taskFinished()
            return True
        else:
            if need_fix:
                while not self.wizard.addMountPoint(worker, port,
                                                    mount_point,
                                                    self.getConsumerType()):
                    mount_point=self._suggestMountPoint(mount_point)

                self.model.properties.mount_point = mount_point
                self._proxy1.update('mount_point')
                self.wizard.taskFinished()
                return True

            message = messages.Error(T_(N_(
                "The mount point %s is already being used for worker %s and "
                "port %s. Please correct this to be able to go forward."),
                mount_point, worker, port))
            message.id = 'http-streamer-mountpoint'
            self.wizard.add_msg(message)
            self.wizard.taskFinished(True)
            return False

    # Callbacks

    def on_mount_point_changed(self, entry):
        if not entry.get_text():
            self.wizard.clear_msg('http-streamer-mountpoint')
            message = messages.Error(T_(N_(
                "Mountpoint cannot be left empty.\n"
                "Fill the text field with a correct mount point to"
                "be able to go forward.")))
            message.id = 'http-streamer-mountpoint'
            self.wizard.add_msg(message)
            self.wizard.blockNext(True)
        else:
            self._checkMountPoint(mount_point=entry.get_text())

    def on_has_client_limit_toggled(self, cb):
        self.client_limit.set_sensitive(cb.get_active())

    def on_has_bandwidth_limit_toggled(self, cb):
        self.bandwidth_limit.set_sensitive(cb.get_active())

    def on_set_hostname__toggled(self, cb):
        self.hostname.set_sensitive(cb.get_active())

    def on_port_changed(self, widget):
        if widget.get_text().isdigit():
            self._checkMountPoint(port=int(widget.get_text()))


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


class HTTPGenericStep(HTTPSpecificStep):
    name = 'HTTPStreamerGeneric'
    title = _('HTTP Streamer (Generic)')
    sidebarName = _('HTTP Generic')
    docSection = 'help-configuration-assistant-http-streaming-generic'
    docAnchor = ''
    docVersion = 'local'

    def __init__(self, wizard, type):
        self._consumertype = type
        HTTPSpecificStep.__init__(self, wizard)

    # ConsumerStep

    def getConsumerType(self):
        return self._consumertype


class HTTPStreamerWizardPlugin(object):
    implements(IConsumerPlugin)

    def __init__(self, wizard):
        self.wizard = wizard

    def getConsumptionStep(self, type):
        if type == 'video':
            return HTTPVideoStep(self.wizard)
        elif type == 'audio':
            return HTTPAudioStep(self.wizard)
        elif type == 'audio-video':
            return HTTPBothStep(self.wizard)
        else:
            return HTTPGenericStep(self.wizard, type)
