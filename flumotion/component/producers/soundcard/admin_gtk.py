# Copyright (C) 2004 Fluendo, S.L. (www.fluendo.com). All rights reserved.

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
from flumotion.component.effects.volume.admin_gtk import VolumeAdminGtkNode

class SoundcardAdminGtk(admin_gtk.BaseAdminGtk):
    def setup(self):
        self._nodes = {}
        volume = VolumeAdminGtkNode(self.name, self.admin,
            self.view, 'inputVolume')
        self._nodes['Volume'] = volume

    def getNodes(self):
        return self._nodes

    def component_volumeChanged(self, channel, rms, peak, decay):
        volume = self._nodes['Volume']
        volume.volumeChanged(channel, rms, peak, decay)

GUIClass = SoundcardAdminGtk

