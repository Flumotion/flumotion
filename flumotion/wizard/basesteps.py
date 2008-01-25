# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2004,2005,2006,2007 Fluendo, S.L. (www.fluendo.com).
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
from flumotion.common.messages import N_, ngettext
from flumotion.ui.wizard import WizardStep

__version__ = "$Rev$"
T_ = messages.gettexter('flumotion')
_ = gettext.gettext

class WorkerWizardStep(WizardStep):

    def __init__(self, wizard):
        WizardStep.__init__(self, wizard)
        self.worker = None

    def worker_changed(self):
        pass

    def run_in_worker(self, module, function, *args, **kwargs):
        return self.wizard.run_in_worker(self.worker, module, function,
                                         *args, **kwargs)


class AudioSourceStep(WorkerWizardStep):
    section = _('Production')
    def __init__(self, wizard, model):
        self.model = model
        WorkerWizardStep.__init__(self, wizard)


class VideoSourceStep(WorkerWizardStep):
    section = _('Production')
    icon = 'widget_doc.png'

    def __init__(self, wizard, model):
        self.model = model
        WorkerWizardStep.__init__(self, wizard)

    # WizardStep

    def get_next(self):
        return OverlayStep(self.wizard, self.model)

    def get_state(self):
        options = WorkerWizardStep.get_state(self)
        options['width'] = int(options['width'])
        options['height'] = int(options['height'])
        return options


class VideoEncoderStep(WorkerWizardStep):
    section = _('Conversion')

    def __init__(self, wizard, model):
        self.model = model
        WorkerWizardStep.__init__(self, wizard)


class AudioEncoderStep(WorkerWizardStep):
    glade_file = 'wizard_audio_encoder.glade'
    section = _('Conversion')

    def __init__(self, wizard, model):
        self.model = model
        WorkerWizardStep.__init__(self, wizard)

    # WizardStep

    def get_next(self):
        return None


class OverlayStep(WorkerWizardStep):
    name = _('Overlay')
    glade_file = 'wizard_overlay.glade'
    section = _('Production')
    component_type = 'overlay'
    icon = 'overlay.png'

    def __init__(self, wizard, video_producer):
        WorkerWizardStep.__init__(self, wizard)
        self._video_producer = video_producer
        self.can_overlay = True

    # Wizard Step

    def worker_changed(self):
        self._worker_changed()

    def get_next(self):
        if self.wizard.get_step_option('Source', 'has-audio'):
            return self.wizard.get_step('Source').get_audio_step()

        return None

    def setup(self):
        self.text.data_type = str
        self.text.set_text(_("Fluendo"))

    # Private API

    def _worker_changed(self):
        self.can_overlay = False
        self.set_sensitive(False)

        def importError(error):
            self.info('could not import PIL')
            message = messages.Warning(T_(N_(
                "Worker '%s' cannot import module '%s'."),
                self.worker, 'PIL'))
            message.add(T_(N_("\nThis module is part of '%s'."),
                           'Python Imaging Library'))
            message.add(T_(N_("\nThe project's homepage is %s"),
                           'http://www.pythonware.com/products/pil/'))
            message.add(T_(N_("\n\nClick Next to proceed without overlay.")))
            message.id = 'module-PIL'
            self.wizard.add_msg(message)
            self.can_overlay = False

        def checkImport(unused):
            self.can_overlay = True
            self.set_sensitive(True)

        def checkElements(elements):
            if elements:
                f = ngettext("Worker '%s' is missing GStreamer element '%s'.",
                    "Worker '%s' is missing GStreamer elements '%s'.",
                    len(elements))
                message = messages.Warning(
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

    def on_show_text__toggled(self, button):
        self.text.set_sensitive(button.get_active())


