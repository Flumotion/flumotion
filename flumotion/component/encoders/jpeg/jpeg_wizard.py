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

def _fraction_from_float(number, denominator):
    """
    Return a string to be used in serializing to XML.
    """
    return "%d/%d" % (number * denominator, denominator)


class Framerate(Int):
    def save(self, value):
        # save as fraction
        return _fraction_from_float(value, 2)


class JPEGWizardPlugin(EncodingWizardPlugin):
    def get_profile_presets(self):
        return [(_("0 (largest)"), 0, False),
                (_("20"), 20, False),
                (_("40"), 40, False),
                (_("60"), 60, False),
                (_("85 (default)"), 85, True),
                (_("95"), 95, False),
                (_("100 (smallest)"), 100, False)]

    def create_profile(self, name, quality, isdefault):
        properties = dict(quality=quality)

        return Profile(name, isdefault, properties)

    def get_custom_properties(self):
        return [
            Int("quality",_("Quality"),
                85, 0, 100),
            Framerate("framerate",_("Framerate"),
                      5, 0.01, 100),
            ]

    def worker_changed(self, worker):
        self.wizard.require_elements(self.worker, 'jpegenc')
