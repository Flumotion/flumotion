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

__version__ = "$Rev$"

import gettext

from flumotion.component.encoders.encodingprofile import Int
from flumotion.component.encoders.encodingwizardplugin import \
     EncodingWizardPlugin

_ = gettext.gettext

class Bitrate(Int):
    def save(self, value):
        # kbps -> bps
        return value * 1000


class VorbisWizardPlugin(EncodingWizardPlugin):
    def get_profile_presets(self):
        return [(_("24 kbps (worst)"), 32, False),
                (_("32 kbps"), 32, False),
                (_("48 kbps"), 48, False),
                (_("64 kbps (default)"), 64, True),
                (_("96 kbps"), 96, False),
                (_("128 kbps"), 128, False),
                (_("144 kbps"), 144, False),
                (_("192 kbps (best)"), 192, False),
                ]

    def get_custom_properties(self):
        return [
            Bitrate("bitrate", _("Bitrate"),
                64, 6, 250),
            ]

    def worker_changed(self, worker):
        self.wizard.debug('running Vorbis checks')
        def hasVorbis(unused):
            self.wizard.run_in_worker(
                worker, 'flumotion.worker.checks.encoder', 'checkVorbis')

        d = self.wizard.require_elements(worker, 'vorbisenc')
        d.addCallback(hasVorbis)
