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

from flumotion.component.encoders.encodingprofile import Profile, Int
from flumotion.component.encoders.encodingwizardplugin import \
     EncodingWizardPlugin

__version__ = "$Rev$"
_ = gettext.gettext


class SmokeWizardPlugin(EncodingWizardPlugin):
    def get_profile_presets(self):
        return [(_("Default"), None, True)]

    def create_profile(self, name, unused, isdefault):
        properties = dict(qmin=10,
                          qmax=85,
                          threshold=300,
                          keyframe=20)

        return Profile(name, isdefault, properties)

    def get_custom_properties(self):
        return [
            Int("qmin", _("Minimum JPEG quality"),
                10, 0, 100),
            Int("qmax",_("Maximum JPEG quality"),
                85, 0, 100),
            Int("threshold", _("Motion estimation"),
                300, 0, 1000000000),
            Int("keyframe",_("Keyframe interval"),
                20, 0, 100000),
        ]

    def worker_changed(self, worker):
        self.wizard.require_elements(self.worker, 'smokeenc')

    def get_custom_property_columns(self):
        return 1

