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

from flumotion.component.base import admin_gtk
from flumotion.component.effects.volume import admin_gtk as vadmin_gtk

__version__ = "$Rev$"


class SoundcardAdminGtk(admin_gtk.BaseAdminGtk):

    def setup(self):
        self._nodes = {}
        volume = vadmin_gtk.VolumeAdminGtkNode(self.state, self.admin,
                                               'inputVolume',
                                               'Input Volume')
        self.nodes['Volume'] = volume
        return admin_gtk.BaseAdminGtk.setup(self)

    def component_volumeChanged(self, channel, rms, peak, decay):
        volume = self.nodes['Volume']
        volume.volumeChanged(channel, rms, peak, decay)

    def component_effectVolumeSet(self, effect, volume):
        """
        @param volume: volume multiplier between 0.0 and 4.0
        @type  volume: float
        """
        if effect != 'inputVolume':
            self.warning('Unknown effect %s in %r' % (effect, self))
            return
        v = self.nodes['Volume']
        v.volumeSet(volume)


GUIClass = SoundcardAdminGtk
