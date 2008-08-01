# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2004,2005,2006,2007,2008 Fluendo, S.L. (www.fluendo.com).
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

from flumotion.component.base.effectsnode import EffectAdminGtkNode

__version__ = "$Rev$"


class ColorbalanceAdminGtkNode(EffectAdminGtkNode):
    logCategory = 'colorbalance'

    gladeFile = 'flumotion/component/effects/colorbalance/colorbalance.glade'

    # FIXME: the scale and the spinbutton should just be using the same
    # adjustment

    def haveWidgetTree(self):
        self.widget = self.wtree.get_widget('widget-colorbalance')
        self._createUI()

    def _createUI(self):
        for k in 'Hue', 'Saturation', 'Brightness', 'Contrast':
            lower = k.lower()
            scale = self.wtree.get_widget('scale-%s' % lower)
            spinbutton = self.wtree.get_widget('spinbutton-%s' % lower)

            value = 0.0

            scale.set_value(value)
            spinbutton.set_value(value)

            scale_change_id = scale.connect('value-changed',
                self.cb_colorbalance_change, k)
            spinbutton_change_id = spinbutton.connect('value-changed',
                self.cb_colorbalance_change, k)

            setattr(self, 'scale_%s' % lower, scale)
            setattr(self, 'spinbutton_%s' % lower, spinbutton)
            setattr(self, '%s_scale_change_id' % lower, scale_change_id)
            setattr(self, '%s_spinbutton_change_id' % lower,
                    spinbutton_change_id)

    def cb_colorbalance_change(self, widget, label):
        value = widget.get_value()
        self.debug('changing colorbalance %s to %f' % (label, value))
        # we do a first propertyChanged so the spinbutton and scale are synced
        self.propertyChanged(label, value)
        self.debug('informing effect of change')

        def errback(failure, label):
            self.warning("Failure %s changing colorbalance %s: %s",
                         failure.type, label, failure.getErrorMessage())
        def callback(result, label):
            self.debug("remote replied colorbalance %s changed to %f",
                       label, result)

        d = self.effectCallRemote("setColorBalanceProperty", label, value)
        d.addErrback(errback, label)
        d.addCallback(callback, label)

    def setUIState(self, state):
        EffectAdminGtkNode.setUIState(self, state)
        for k in 'Hue', 'Saturation', 'Brightness', 'Contrast':
            self.propertyChanged(k, state.get('colorbalance-%s' % k))

    def stateSet(self, state, key, value):
        if key.startswith('colorbalance-'):
            key = key[len('colorbalance-'):]
            self.propertyChanged(key, value)

    def propertyChanged(self, name, value):
        self.debug('syncing colorbance property %s to %f' % (name, value))

        lower = name.lower()
        scale = getattr(self, 'scale_%s' % lower)
        spinbutton = getattr(self, 'spinbutton_%s' % lower)
        scale_change_id = getattr(self, '%s_scale_change_id' % lower)
        spinbutton_change_id = getattr(self, '%s_spinbutton_change_id' % lower)

        scale.handler_block(scale_change_id)
        scale.set_value(value)
        scale.handler_unblock(scale_change_id)
        spinbutton.handler_block(spinbutton_change_id)
        spinbutton.set_value(value)
        spinbutton.handler_unblock(spinbutton_change_id)
