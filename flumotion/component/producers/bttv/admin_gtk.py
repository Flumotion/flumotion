# flumotion/component/producers/videotest/admin_gtk.py
# admin client-side code for bttv
# 
# Flumotion - a streaming media server
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

import gtk

from flumotion.common import errors

#import flumotion.component
from flumotion.component.base import admin_gtk

class bttvAdminGtk(admin_gtk.BaseAdminGtk):
    # FIXME: do something with this
    def setUIState(self, state):
        self.updateLabels(state)
        if not self.shown:
            self.shown = True
            self.statistics.show_all()
        
    def render(self):
        # FIXME: gladify
        self.widget = gtk.Table(4,2)
        huelabel = gtk.Label("Hue:")
        self.widget.attach(huelabel, 0, 1, 0, 1, 0, 0, 6, 6)
        huelabel.show()
        saturationlabel = gtk.Label("Saturation:")
        self.widget.attach(saturationlabel, 0, 1, 1, 2, 0, 0, 6, 6)
        saturationlabel.show()
        brightnesslabel = gtk.Label("Brightness:")
        self.widget.attach(brightnesslabel, 0, 1, 2, 3, 0, 0, 6, 6)
        brightnesslabel.show()
        contrastlabel = gtk.Label("Contrast:")
        self.widget.attach(contrastlabel, 0, 1, 3, 4, 0, 0, 6, 6)
        contrastlabel.show()
        
        d = self.callRemote("getColorBalanceProperties")
        d.addCallback(self.getColorBalancePropertiesCallback)
        d.addErrback(self.getColorBalancePropertiesErrback)

        return self.widget
        
    def getColorBalancePropertiesCallback(self, result):
        self.debug("%s: minimum: %d maximum: %d value: %d" % (result[0][0], result[0][1], result[0][2], result[0][3]))

        for i in result:
            # create scale that uses 0 decimal places, and only updates after a little time after user finished moving scale
            scale = gtk.HScale()
            scale.set_range(i[1], i[2])
            scale.set_value(i[3])
            scale.set_increments(1,100)
            scale.set_digits(0)
            scale.set_update_policy(gtk.UPDATE_DELAYED)
            changeid = scale.connect('value-changed',self.cb_colorbalance_change)

            if i[0] == 'Hue':
                self.huescale = scale
                self.huechangeid = changeid
            if i[0] == 'Saturation':
                self.saturationscale = scale
                self.saturationchangeid = changeid
            if i[0] == 'Brightness':
                self.brightnessscale = scale
                self.brightnesschangeid = changeid
            if i[0] == 'Contrast':
                self.contrastscale = scale
                self.contrastchangeid = changeid

        

        self.widget.attach(self.huescale, 1, 2, 0, 1, gtk.EXPAND|gtk.FILL, 0, 6, 6)
        self.huescale.show()
        
        self.widget.attach(self.saturationscale, 1, 2, 1, 2, gtk.EXPAND|gtk.FILL, 0, 6, 6)
        self.saturationscale.show()

        self.widget.attach(self.brightnessscale, 1, 2, 2, 3, gtk.EXPAND|gtk.FILL, 0, 6, 6)
        self.brightnessscale.show()

        self.widget.attach(self.contrastscale, 1, 2, 3, 4, gtk.EXPAND|gtk.FILL, 0, 6, 6)
        self.contrastscale.show()
        

    def getColorBalancePropertiesErrback(self, failure):
        self.warning("Failure %s getting color balance properties: %s" % (failure.type, failure.getErrorMessage()))
        return None
    
    def cb_colorbalance_change(self, scale):
        value = scale.get_value()
        label = ""
        if scale == self.huescale:
            label = "Hue"
        if scale == self.saturationscale:
            label = "Saturation"
        if scale == self.brightnessscale:
            label = "Brightness"
        if scale == self.contrastscale:
            label = "Contrast"
        log.debug('changing colorbalance %s to %d' % (label, value))
        d = self.callRemote("change_colorbalance", label, int(value))
        d.addErrback(self.colorbalanceChangeErrBack)

    def colorbalanceChangeErrBack(self,failure):
        self.warning("Failure %s changing filename: %s" % (failure.type, failure.getErrorMessage()))

    def propertyChanged(self, name, value):
        self.debug('property %s changed to %d' % (name, value))

        changeid = -1
        if name == 'Hue':
            scale = self.huescale
            changeid = self.huechangeid
        if name == 'Saturation':
            scale = self.saturationscale
            changeid = self.saturationchangeid
        if name == 'Brightness':
            scale = self.brightnessscale
            changeid = self.brightnesschangeid
        if name == 'Contrast':
            scale = self.contrastscale
            changeid = self.contrastchangeid

        if changeid != -1:
            scale.handler_block(changeid)
            scale.set_value(value)
            scale.handler_unblock(changeid)
            

GUIClass = bttvAdminGtk
