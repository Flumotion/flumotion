# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# flumotion/component/effects/volume/admin_gtk.py:
# admin client-side code for volume effects
# 
# Flumotion - a streaming media server
# Copyright (C) 2004,2005 Fluendo, S.L. (www.fluendo.com). All rights reserved.

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

import gtk
import os

from flumotion.common import errors, log


from flumotion.component.base import admin_gtk

class VolumeAdminGtkNode(admin_gtk.EffectAdminGtkNode):
    logCategory = 'volume'

    def render(self):
        self.debug('rendering volume node')
        gladeFile = os.path.join('flumotion', 'component', 'effects',
            'volume', 'volume.glade')
        d = self.loadGladeFile(gladeFile)
        d.addCallback(self._loadGladeFileCallback)
        return d

    def _loadGladeFileCallback(self, widgetTree):
        from flumotion.ui import fgtk

        self.wtree = widgetTree
        self.volume = self.wtree.get_widget('volume-widget')
        self.scale_volume = fgtk.FVUMeter()
        self.volume.attach(self.scale_volume, 1, 2, 0, 1,
            gtk.EXPAND|gtk.FILL, gtk.FILL, 6, 6)
        self.scale_volume.show()
        self.shown = False
        return self.volume
        
    def volumeChanged(self, channel, peak, rms, decay):
        self.scale_volume.set_property('peak', peak)
        self.scale_volume.set_property('decay', decay)
