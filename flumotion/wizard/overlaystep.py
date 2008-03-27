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

from flumotion.common.messages import N_, ngettext, gettexter, Warning
from flumotion.wizard.models import VideoConverter
from flumotion.wizard.workerstep import WorkerWizardStep

__version__ = "$Rev: 6228 $"
T_ = gettexter('flumotion')
_ = gettext.gettext


class Overlay(VideoConverter):
    component_type = 'overlay-converter'

    def __init__(self, video_producer):
        super(Overlay, self).__init__()
        self._video_producer = video_producer
        self.can_overlay = False
        self.show_text = True
        self.show_logo = True
        self.properties.text = _("Fluendo")

    # Public API

    def hasOverlay(self):
        if self.can_overlay:
            if self.show_logo or self.show_text:
                return True
        return False

    # Component

    def getProperties(self):
        p = super(Overlay, self).getProperties()

        if not self.show_text:
            del p.text

        p.width = self._video_producer.getWidth()
        p.height = self._video_producer.getHeight()

        return p


class OverlayStep(WorkerWizardStep):
    name = _('Overlay')
    glade_file = 'wizard_overlay.glade'
    section = _('Production')
    component_type = 'overlay'
    icon = 'overlay.png'

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

        self.add_proxy(self.model, ['show_logo', 'show_text'])
        self.add_proxy(self.model.properties, ['text'])

    def worker_changed(self, worker):
        self.model.worker = worker
        self._check_elements()

    def get_next(self):
        if self.wizard.hasAudio():
            return self.wizard.get_step('Production').get_audio_step()

        return None

    # Private API

    def _check_elements(self):
        self.model.can_overlay = False
        self.set_sensitive(False)

        def importError(error):
            self.info('could not import PIL')
            message = Warning(T_(N_(
                "Worker '%s' cannot import module '%s'."),
                self.worker, 'PIL'))
            message.add(T_(N_("\nThis module is part of '%s'."),
                           'Python Imaging Library'))
            message.add(T_(N_("\nThe project's homepage is %s"),
                           'http://www.pythonware.com/products/pil/'))
            message.add(T_(N_("\n\nClick Next to proceed without overlay.")))
            message.id = 'module-PIL'
            self.wizard.add_msg(message)
            self.model.can_overlay = False

        def checkImport(unused):
            self.model.can_overlay = True
            self.set_sensitive(True)

        def checkElements(elements):
            if elements:
                f = ngettext("Worker '%s' is missing GStreamer element '%s'.",
                    "Worker '%s' is missing GStreamer elements '%s'.",
                    len(elements))
                message = Warning(
                    T_(f, self.worker, "', '".join(elements)), id='overlay')
                message.add(T_(N_("\n\nClick Next to proceed without overlay.")))
                self.wizard.add_msg(message)
            else:
                self.wizard.clear_msg('overlay')

            # now check import
            d = self.wizard.check_import(self.worker, 'PIL')
            d.addCallback(checkImport)
            d.addErrback(importError)

        # first check elements
        d = self.wizard.check_elements(
            self.worker, 'pngenc', 'ffmpegcolorspace', 'videomixer')
        d.addCallback(checkElements)

    # Callbacks

    def on_show_text__toggled(self, button):
        self.text.set_sensitive(button.get_active())

