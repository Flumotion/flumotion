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

"""Flumotion interfaces used by the wizard
"""

from zope.interface import Interface

__version__ = "$Rev$"


class IProducerPlugin(Interface):
    """A producer plugin is how you extend the production wizard page.
    The main purpose of the plugin is to get a wizard step specific
    to the plugin.
    This entry point should be defined in the xml for the component
    under the entry type "wizard".
    """

    def __call__(wizard):
        """Creates producer plugins
        @param wizard: the wizard
        @type wizard: L{ConfigurationWizard}
        """

    def getProductionStep(type):
        """Asks the plugin for a step.
        type is the kind of plugin, it's useful for components such as
        firewire for which you can point both audio and video to the
        same plugin.
        @param type: audio or video
        @type type: string
        @returns: the wizard step
        @rtype: a L{WorkerWizardStep} subclass
        """


class IEncoderPlugin(Interface):
    """An encoder plugin is how you extend the encoding wizard page.
    The main purpose of the plugin is to get a wizard step specific
    to the plugin.
    This entry point should be defined in the xml for the component
    under the entry type "wizard".
    """

    def __call__(wizard):
        """Creates encoder plugins
        @param wizard: the wizard
        @type wizard: L{ConfigurationWizard}
        """

    def getConversionStep():
        """Asks the plugin for a step.
        @returns: the wizard step
        @rtype: a L{WorkerWizardStep} subclass
        """


class IHTTPConsumerPlugin(Interface):
    """A http consumer plugin is how you extend the HTTP consumer page.
    The main purpose of the plugin is to get a consumer model
    (eg, a http server) specific for this plugin.
    This entry point should be defined in the xml for the component
    under the entry type "wizard".
    """

    def __call__(wizard):
        """Creates http consumer plugins
        @param wizard: the wizard
        @type wizard: L{ConfigurationWizard}
        """

    def workerChanged(worker):
        """Called when the worker for the step changed.
        @param worker: the worker
        @type worker: L{WorkerComponentUIState}
        """

    def getConsumer(streamer, audio_producer, video_producer):
        """Asks the plugin for a consumer model
        @param streamer: the http streamer
        @type streamer: L{HTTPStreamer} subclass
        @param audio_producer: audio producer for this stream
        @type audio_producer: L{AudioProducer} subclass
        @param video_producer: video producer for this stream
        @type video_producer: L{VideoProducer} subclass
        @returns: consumer
        @rtype: a L{HTTPServer} subclass
        """
