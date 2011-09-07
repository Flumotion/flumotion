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

import gettext
import os

from zope.interface import implements

from flumotion.admin.assistant.interfaces import IEncoderPlugin
from flumotion.admin.assistant.models import VideoEncoder
from flumotion.common.fraction import fractionAsFloat
from flumotion.admin.gtk.basesteps import VideoEncoderStep

__version__ = "$Rev$"
_ = gettext.gettext


class VP8VideoEncoder(VideoEncoder):
    """
    @ivar framerate: number of frames per second; to be set by view
    @type framerate: float
    """
    componentType = 'vp8-encoder'

    def __init__(self):
        super(VP8VideoEncoder, self).__init__()
        self.has_quality = False
        self.has_bitrate = True
        self.framerate = 25.0

        self.properties.keyframe_delta = 2.0
        self.properties.bitrate = 400
        self.properties.quality = 16

    def getProperties(self):
        properties = super(VP8VideoEncoder, self).getProperties()
        if self.has_bitrate:
            del properties.quality
            properties.bitrate *= 1000
        elif self.has_quality:
            del properties.bitrate
        else:
            raise AssertionError

        # convert the human-friendly delta to maxdistance
        properties.keyframe_maxdistance = int(properties.keyframe_delta *
            self.framerate)
        del properties.keyframe_delta

        self.debug('keyframe_maxdistance: %r',
            properties.keyframe_maxdistance)

        return properties


class VP8Step(VideoEncoderStep):
    name = 'VP8Encoder'
    title = _('VP8 Encoder')
    sidebarName = _('VP8')
    gladeFile = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              'wizard.glade')
    componentType = 'vp8'
    docSection = 'help-configuration-assistant-encoder-vp8'
    docAnchor = ''
    docVersion = 'local'

    # WizardStep

    def setup(self):
        self.bitrate.data_type = int
        self.quality.data_type = int
        self.keyframe_delta.data_type = float
        self.has_quality.data_type = bool
        self.has_bitrate.data_type = bool

        self.add_proxy(self.model,
                       ['has_quality', 'has_bitrate'])
        self.add_proxy(self.model.properties,
                       ['bitrate', 'quality', 'keyframe_delta'])

        # we specify keyframe_delta in seconds, but vp8 expects
        # a number of frames, so we need the framerate and calculate
        # we need to go through the Step (which is the view) because models
        # don't have references to other models
        producer = self.wizard.getScenario().getVideoProducer(self.wizard)
        self.model.framerate = fractionAsFloat(producer.getFramerate())
        self.debug('Framerate of video producer: %r' % self.model.framerate)
        step = 1 / self.model.framerate
        page = 1.0
        self.keyframe_delta.set_increments(step, page)

    def workerChanged(self, worker):
        self.model.worker = worker
        self.wizard.requireElements(worker, 'vp8enc')

    # Callbacks

    def on_radiobutton_toggled(self, button):
        # This is bound to both radiobutton_bitrate and radiobutton_quality
        self.bitrate.set_sensitive(self.has_bitrate.get_active())
        self.quality.set_sensitive(self.has_quality.get_active())

        self.model.has_bitrate = self.has_bitrate.get_active()
        self.model.has_quality = self.has_quality.get_active()


class VP8WizardPlugin(object):
    implements(IEncoderPlugin)

    def __init__(self, wizard):
        self.wizard = wizard
        self.model = VP8VideoEncoder()

    def getConversionStep(self):
        return VP8Step(self.wizard, self.model)
