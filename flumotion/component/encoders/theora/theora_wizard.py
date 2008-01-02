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

from flumotion.component.encoders.encodingprofile import Profile, Int
from flumotion.component.encoders.encodingwizardplugin import \
     EncodingWizardPlugin

_ = gettext.gettext


class Bitrate(Int):
    def save(self, value):
        # kbps -> bps
        return value * 1000


class NoiseSensitivty(Int):
    def save(self, value):
        # percentage -> [0..32768]
        return int(value * (32768 / 100.0))


class TheoraWizardPlugin(EncodingWizardPlugin):
    def get_profile_presets(self):
        return [(_("64 kbps (worst)"), 64, False),
                (_("100 kbps"), 100, False),
                (_("200 kbps"), 200, False),
                (_("400 kbps (default)"), 400, True),
                (_("700 kbps"), 700, False),
                (_("900 kbps"), 900, False),
                (_("1200 kbps (best)"), 1200, False)]

    def create_profile(self, name, bitrate, isdefault):
        properties = dict(bitrate=bitrate,
                          keyframe_maxdistance=64,
                          noise_sensitivity=0,
                          sharpness=0)

        return Profile(name, isdefault, properties)

    def get_custom_properties(self):
        return [
            Bitrate("bitrate", _("Bitrate"),
                    400, 0, 4000),
            #Int("quality",_("Quality"),
            #    16, 0, 63),
            Int("keyframe_maxdistance",_("Keyframe max distance"),
                64, 1, 32768),
            NoiseSensitivty("noise_sensitivity", _("Noise sensitivity"),
                            0, 0, 100),
            Int("sharpness", _("Sharpness"),
                0, 0, 2),
            ]

    def worker_changed(self, worker):
        self.wizard.debug('running Theora checks')

        def hasTheora(unused):
            self.wizard.run_in_worker(
                worker, 'flumotion.worker.checks.encoder', 'checkTheora')

        d = self.wizard.require_elements(worker, 'theoraenc')
        d.addCallback(hasTheora)

