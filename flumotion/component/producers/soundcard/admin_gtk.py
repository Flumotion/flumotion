# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
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

#import sys
#print "THOMAS: sys.path: %r" % sys.path

from flumotion.component.base import admin_gtk
from flumotion.component.effects.volume import admin_gtk as vadmin_gtk

# this reload makes stuff work; we should find out how to make
# registerPackagePath do this properly
reload(vadmin_gtk)

#import flumotion.component
#print "THOMAS: flumotion.component.__path__: %r" % flumotion.component.__path__

#import flumotion.component.effects.volume

#print "THOMAS: volume.admin_gtk: %r" % vadmin_gtk
#if hasattr(vadmin_gtk, '__path__'):
#	print "THOMAS: .... paths: %r" % vadmin_gtk.__path__
#if hasattr(vadmin_gtk, '__file__'):
#	print "THOMAS: .... __file__: %r" % vadmin_gtk.__file__

#print "THOMAS: package's __path__: %r" % flumotion.component.effects.volume.__path__

class SoundcardAdminGtk(admin_gtk.BaseAdminGtk):
    def setup(self):
        self._nodes = {}
        volume = vadmin_gtk.VolumeAdminGtkNode(self.state, self.admin,
            self.view, 'inputVolume')
        self._nodes['Volume'] = volume

    def getNodes(self):
        return self._nodes

    def component_volumeChanged(self, channel, rms, peak, decay):
        volume = self._nodes['Volume']
        volume.volumeChanged(channel, rms, peak, decay)

GUIClass = SoundcardAdminGtk

