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
import os

from zope.interface import implements

from flumotion.admin.assistant.interfaces import IEncoderPlugin
from flumotion.admin.assistant.models import VideoEncoder
from flumotion.admin.gtk.basesteps import VideoEncoderStep

__version__ = "$Rev$"
_ = gettext.gettext


def _fraction_from_float(number, denominator):
    """
    Return a string to be used in serializing to XML.
    """
    return "%d/%d" % (number * denominator, denominator)


class JPEGVideoEncoder(VideoEncoder):
    componentType = 'jpeg-encoder'

    def __init__(self):
        super(JPEGVideoEncoder, self).__init__()

        self.properties.framerate = 5.0
        self.properties.quality = 84

    def getProperties(self):
        properties = super(JPEGVideoEncoder, self).getProperties()
        properties.framerate = _fraction_from_float(properties.framerate, 2)
        return properties


class JPEGStep(VideoEncoderStep):
    name = 'JPEG encoder'
    title = _('JPEG Encoder')
    sidebarName = 'JPEG'
    section = _('Conversion')
    gladeFile = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              'wizard.glade')
    componentType = 'jpeg'
    docSection = 'help-configuration-assistant-encoder-jpeg'
    docAnchor = ''
    docVersion = 'local'

    # WizardStep

    def setup(self):
        self.framerate.data_type = float
        self.quality.data_type = int

        self.add_proxy(self.model.properties,
                       ['framerate', 'quality'])

    def workerChanged(self, worker):
        self.model.worker = worker
        self.wizard.requireElements(worker, 'jpegenc')


class JPEGWizardPlugin(object):
    implements(IEncoderPlugin)

    def __init__(self, wizard):
        self.wizard = wizard
        self.model = JPEGVideoEncoder()

    def getConversionStep(self):
        return JPEGStep(self.wizard, self.model)
