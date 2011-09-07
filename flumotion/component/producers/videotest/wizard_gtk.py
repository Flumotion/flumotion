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

import gtk
from zope.interface import implements

from flumotion.admin.assistant.interfaces import IProducerPlugin
from flumotion.admin.assistant.models import VideoProducer
from flumotion.admin.gtk.basesteps import VideoProducerStep
from flumotion.configure import configure

__version__ = "$Rev$"
_ = gettext.gettext


class TestVideoProducer(VideoProducer):
    componentType = 'videotest-producer'

    def __init__(self):
        super(TestVideoProducer, self).__init__()

        self.properties.pattern = 0


class TestVideoProducerStep(VideoProducerStep):
    name = 'Test Video Producer'
    title = _('Test Video Producer')
    icon = 'testsource.png'
    gladeFile = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              'wizard.glade')
    componentType = 'videotestsrc'
    docSection = 'help-configuration-assistant-producer-video-test'
    docAnchor = ''
    docVersion = 'local'

    # WizardStep

    def setup(self):
        self.pattern.data_type = int
        self.framerate.data_type = float

        patterns = [('SMPTE Color bars', 0, 'pattern_smpte.png'),
                    ('Random (television snow)', 1, 'pattern_snow.png'),
                    ('100% Black', 2, 'pattern_black.png'),
                    ('Blink', 12, 'pattern_blink.png')]
        self.pattern_icons = dict()

        for description, number, image in patterns:
            self.pattern.append_item(_(description), number)
            if image:
                self.pattern_icons[number] = os.path.join(configure.imagedir,
                                                      'wizard', image)

        self.pattern.connect('changed', self._change_image)

        self.add_proxy(self.model.properties,
                       ['pattern', 'width', 'height',
                        'framerate'])

        sizegroup = gtk.SizeGroup(gtk.SIZE_GROUP_HORIZONTAL)
        sizegroup.add_widget(self.width)
        sizegroup.add_widget(self.height)
        sizegroup.add_widget(self.framerate)

    def workerChanged(self, worker):
        self.model.worker = worker
        self.wizard.requireElements(worker, 'videotestsrc', 'level')

    def _change_image(self, combo):
        self.pattern_image.set_from_file(
            self.pattern_icons.get(combo.get_selected_data(), None))


class VideoTestWizardPlugin(object):
    implements(IProducerPlugin)

    def __init__(self, wizard):
        self.wizard = wizard
        self.model = TestVideoProducer()

    def getProductionStep(self, type):
        return TestVideoProducerStep(self.wizard, self.model)
