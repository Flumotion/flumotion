# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# flumotion/component/producers/videotest/admin_gtk.py:
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

class BTTVAdminGtk(admin_gtk.BaseAdminGtk):
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
        self.debug("%s: minimum: %d maximum: %d value: %d" % (
            result[0][0], result[0][1], result[0][2], result[0][3]))

        for i in result:
            # create scale that uses 0 decimal places,
            # and only updates after a little time after user
            # finished moving scale
            scale = gtk.HScale()
            scale.set_range(i[1], i[2])
            scale.set_value(i[3])
            scale.set_increments(1,100)
            scale.set_digits(0)
            scale.set_update_policy(gtk.UPDATE_DELAYED)
            change_id = scale.connect('value-changed',
                self.cb_colorbalance_change)

            if i[0] == 'Hue':
                self.scale_hue = scale
                self.hue_changed_id = change_id
            if i[0] == 'Saturation':
                self.scale_saturation = scale
                self.saturation_changed_id = change_id
            if i[0] == 'Brightness':
                self.scale_brightness = scale
                self.brightness_changed_id = change_id
            if i[0] == 'Contrast':
                self.scale_contrast = scale
                self.contrast_changed_id = change_id

        

        self.widget.attach(self.scale_hue, 1, 2, 0, 1, gtk.EXPAND|gtk.FILL, 0, 6, 6)
        self.scale_hue.show()
        
        self.widget.attach(self.scale_saturation, 1, 2, 1, 2, gtk.EXPAND|gtk.FILL, 0, 6, 6)
        self.scale_saturation.show()

        self.widget.attach(self.scale_brightness, 1, 2, 2, 3, gtk.EXPAND|gtk.FILL, 0, 6, 6)
        self.scale_brightness.show()

        self.widget.attach(self.scale_contrast, 1, 2, 3, 4, gtk.EXPAND|gtk.FILL, 0, 6, 6)
        self.scale_contrast.show()
        

    def getColorBalancePropertiesErrback(self, failure):
        self.warning("Failure %s getting color balance properties: %s" % (
            failure.type, failure.getErrorMessage()))
        return None
    
    def cb_colorbalance_change(self, scale):
        value = scale.get_value()
        label = ""
        if scale == self.scale_hue:
            label = "Hue"
        if scale == self.scale_saturation:
            label = "Saturation"
        if scale == self.scale_brightness:
            label = "Brightness"
        if scale == self.scale_contrast:
            label = "Contrast"
        log.debug('changing colorbalance %s to %d' % (label, value))
        d = self.callRemote("setColorBalanceProperty", label, int(value))
        d.addErrback(self.colorbalanceChangeErrback)

    def colorbalanceChangeErrback(self,failure):
        self.warning("Failure %s changing colorbalance: %s" % (failure.type,
            failure.getErrorMessage()))

    def propertyChanged(self, name, value):
        self.debug('property %s changed to %d' % (name, value))

        change_id = -1
        if name == 'Hue':
            scale = self.scale_hue
            change_id = self.hue_changed_id
        if name == 'Saturation':
            scale = self.scale_saturation
            change_id = self.saturation_changed_id
        if name == 'Brightness':
            scale = self.scale_brightness
            change_id = self.brightness_changed_id
        if name == 'Contrast':
            scale = self.scale_contrast
            change_id = self.contrast_changed_id

        if change_id != -1:
            scale.handler_block(change_id)
            scale.set_value(value)
            scale.handler_unblock(change_id)
            

GUIClass = BTTVAdminGtk
