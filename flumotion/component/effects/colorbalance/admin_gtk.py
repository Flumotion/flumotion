# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# flumotion/component/effects/colorbalance/admin_gtk.py:
# admin client-side code for colorbalance effects
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

from flumotion.common import errors, log

from flumotion.component.base import admin_gtk

class ColorbalanceAdminGtkNode(admin_gtk.EffectAdminGtkNode):
    logCategory = 'colorbalance'

    def render(self):
        self.debug('rendering colorbalance node')
        file = 'flumotion/component/effects/colorbalance/colorbalance.glade'
        d = self.loadGladeFile(file)
        d.addCallback(self._loadGladeFileCallback)
        
        return d

    def _loadGladeFileCallback(self, widgetTree):
        self.wtree = widgetTree
        self.widget = self.wtree.get_widget('widget-colorbalance')

        d = self.effectCallRemote("getColorBalanceProperties")
        d.addCallback(self.getColorBalancePropertiesCallback)
        d.addErrback(self.getColorBalancePropertiesErrback)
        d.addCallback(lambda result: self.widget)

        return d
        
    def getColorBalancePropertiesCallback(self, result):
        for i in result:
            scale_widgetname = 'scale-%s' % i[0]
            spinbutton_widgetname = 'spinbutton-%s' % i[0]
            scale = self.wtree.get_widget(scale_widgetname.lower())
            spinbutton = self.wtree.get_widget(spinbutton_widgetname.lower())

            scale.set_value(i[1])
            spinbutton.set_value(i[1])

            scale_change_id = scale.connect('value-changed',
                self.cb_colorbalance_change)
            spinbutton_change_id = spinbutton.connect('value-changed',
                self.cb_colorbalance_change)

            if i[0] == 'Hue':
                self.scale_hue = scale
                self.spinbutton_hue = spinbutton
                self.hue_scale_change_id = scale_change_id
                self.hue_spinbutton_change_id = spinbutton_change_id
                
            if i[0] == 'Saturation':
                self.scale_saturation = scale
                self.spinbutton_saturation = spinbutton
                self.saturation_scale_change_id = scale_change_id
                self.saturation_spinbutton_change_id = spinbutton_change_id
               
            if i[0] == 'Brightness':
                self.scale_brightness = scale
                self.spinbutton_brightness = spinbutton
                self.brightness_scale_change_id = scale_change_id
                self.brightness_spinbutton_change_id = spinbutton_change_id

            if i[0] == 'Contrast':
                self.scale_contrast = scale
                self.spinbutton_contrast = spinbutton
                self.contrast_scale_change_id = scale_change_id
                self.contrast_spinbutton_change_id = spinbutton_change_id

    def getColorBalancePropertiesErrback(self, failure):
        self.warning("Failure %s getting color balance properties: %s" % (
            failure.type, failure.getErrorMessage()))
        return None
    
    def cb_colorbalance_change(self, widget):
        value = widget.get_value()
        label = ""
        if widget == self.scale_hue or widget == self.spinbutton_hue:
            label = "Hue"
        if widget == self.scale_saturation or widget == self.spinbutton_saturation: 
            label = "Saturation"
        if widget == self.scale_brightness or widget == self.spinbutton_brightness:
            label = "Brightness"
        if widget == self.scale_contrast or widget == self.spinbutton_contrast:
            label = "Contrast"
        log.debug('changing colorbalance %s to %f' % (label, value))
        # we do a first propertyChanged so the spinbutton and scale are synced
        self.propertyChanged(label, value)
        d = self.effectCallRemote("setColorBalanceProperty", label, value)
        d.addErrback(self.colorbalanceChangeErrback, label)
        d.addCallback(self.colorbalanceChangeCallback, label)

    def colorbalanceChangeErrback(self, failure, label):
        self.warning("Failure %s changing colorbalance %s: %s" % (failure.type,
            label, failure.getErrorMessage()))

    def colorbalanceChangeCallback(self, result, label):
        self.debug("remote replied colorbalance %s changed to %f" % (
            label, result))
        # we do a second propertyChanged so both are synced to the result
        self.propertyChanged(label, result)

    def propertyChanged(self, name, value):
        self.debug('syncing colorbance property %s to %f' % (name, value))

        scale_change_id = -1
        if name == 'Hue':
            scale = self.scale_hue
            spinbutton = self.spinbutton_hue
            scale_change_id = self.hue_scale_change_id
            spinbutton_change_id = self.hue_spinbutton_change_id
        if name == 'Saturation':
            scale = self.scale_saturation
            spinbutton = self.spinbutton_saturation
            scale_change_id = self.saturation_scale_change_id
            spinbutton_change_id = self.saturation_spinbutton_change_id
        if name == 'Brightness':
            scale = self.scale_brightness
            spinbutton = self.spinbutton_brightness
            scale_change_id = self.brightness_scale_change_id
            spinbutton_change_id = self.brightness_spinbutton_change_id
        if name == 'Contrast':
            scale = self.scale_contrast
            spinbutton = self.spinbutton_contrast
            scale_change_id = self.contrast_scale_change_id
            spinbutton_change_id = self.contrast_spinbutton_change_id

        # if we had an actual property change, process it and block signal
        # emission while doing so
        if scale_change_id != -1:
            scale.handler_block(scale_change_id)
            scale.set_value(value)
            scale.handler_unblock(scale_change_id)
            spinbutton.handler_block(spinbutton_change_id)
            spinbutton.set_value(value)
            spinbutton.handler_unblock(spinbutton_change_id)
