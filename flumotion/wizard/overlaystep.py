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

from flumotion.common import messages

from flumotion.admin.assistant.models import VideoConverter
from flumotion.common.i18n import N_, gettexter, ngettext
from flumotion.wizard.workerstep import WorkerWizardStep

__version__ = "$Rev: 6228 $"
T_ = gettexter()
_ = gettext.gettext


class Overlay(VideoConverter):
    componentType = 'overlay-converter'

    def __init__(self, video_producer):
        super(Overlay, self).__init__()
        self._videoProducer = video_producer
        self.can_overlay = False
        self.show_logo = True
        self.properties.show_text = True
        self.properties.text = _("Flumotion")

    # Public API

    def hasOverlay(self):
        if self.can_overlay:
            if self.show_logo or self.properties.show_text:
                return True
        return False

    # Component

    def getProperties(self):
        p = super(Overlay, self).getProperties()

        if not self.properties.show_text:
            del p.text

        p.width = self._videoProducer.getWidth()
        p.height = self._videoProducer.getHeight()

        return p


class OverlayStep(WorkerWizardStep):
    name = 'Overlay'
    title = _('Overlay')
    section = _('Production')
    gladeFile = 'overlay-wizard.glade'
    icon = 'overlay.png'
    componentType = 'overlay'

    def __init__(self, wizard, video_producer):
        self.model = Overlay(video_producer)
        WorkerWizardStep.__init__(self, wizard)

    # Public API

    def getOverlay(self):
        if self.model.hasOverlay():
            return self.model

    # Wizard Step

    def setup(self):
        self.text.data_type = str

        self.add_proxy(self.model, ['show_logo'])
        self.add_proxy(self.model.properties, ['show_text', 'text'])

    def workerChanged(self, worker):
        self.model.worker = worker
        self._checkElements()

    def getNext(self):
        if self.wizard.hasAudio():
            return self.wizard.getStep('Production').getAudioStep()

        return None

    # Private API

    def _setSensitive(self, sensitive):
        self.show_text.set_sensitive(sensitive)
        self.show_logo.set_sensitive(sensitive)
        self.text.set_sensitive(sensitive)

    def _checkElements(self):
        self.model.can_overlay = False

        def importError(error):
            self.info('could not import PIL')
            message = messages.Warning(
                T_(N_("Worker '%s' cannot import module '%s'."),
                   self.worker, 'PIL'))
            message.add(
                T_(N_("\nThis module is part of '%s'."),
                   'Python Imaging Library'))
            message.add(
                T_(N_("\nThe project's homepage is %s"),
                   'http://www.pythonware.com/products/pil/'))
            message.add(
                T_(N_("\n\nClick \"Forward\" to proceed without overlay.")))
            message.id = 'module-PIL'
            self.wizard.add_msg(message)
            self.wizard.taskFinished()
            self._setSensitive(False)

        def checkImport(unused):
            self.wizard.taskFinished()
            # taskFinished updates sensitivity
            self.model.can_overlay = True

        def checkElements(elements):
            if elements:
                f = ngettext("Worker '%s' is missing GStreamer element '%s'.",
                    "Worker '%s' is missing GStreamer elements '%s'.",
                    len(elements))
                message = messages.Warning(
                    T_(f, self.worker, "', '".join(elements)), id='overlay')
                message.add(
                    T_(
                    N_("\n\nClick \"Forward\" to proceed without overlay.")))
                self.wizard.add_msg(message)
                self.wizard.taskFinished()
                self._setSensitive(False)
                return
            else:
                self.wizard.clear_msg('overlay')

            # now check import
            d = self.wizard.checkImport(self.worker, 'PIL')
            d.addCallback(checkImport)
            d.addErrback(importError)

        self.wizard.waitForTask('overlay')
        # first check elements
        d = self.wizard.checkElements(
            self.worker, 'pngenc', 'ffmpegcolorspace', 'videomixer')
        d.addCallback(checkElements)

    # Callbacks

    def on_show_text__toggled(self, button):
        self.text.set_sensitive(button.get_active())
