# -*- Mode: Python; test-case-name: flumotion.test.test_feedcomponent010 -*-
# vi:si:et:sw=4:sts=4:ts=4

# Flumotion - a streaming media server
# Copyright (C) 2004,2005,2006,2007,2008,2009 Fluendo, S.L.
# Copyright (C) 2010,2011 Flumotion Services, S.A.
# All rights reserved.
#
# This file may be distributed and/or modified under the terms of
# the GNU Lesser General Public License version 2.1 as published by
# the Free Software Foundation.
# This file is distributed without any warranty; without even the implied
# warranty of merchantability or fitness for a particular purpose.
# See "LICENSE.LGPL" in the source distribution for more information.
#
# Headers in this file shall remain intact.

"""
Component tab in the component UI
"""

import gettext
import os
import time

import gtk

from flumotion.common import format as formatting
from flumotion.common.i18n import gettexter
from flumotion.component.base.baseadminnode import BaseAdminGtkNode
from flumotion.extern.log.log import getDebug
from flumotion.common.planet import AdminFlowState


_ = gettext.gettext
__version__ = "$Rev$"
T_ = gettexter()


class ComponentAdminGtkNode(BaseAdminGtkNode):
    gladeFile = os.path.join('flumotion', 'component', 'base',
        'component.glade')

    def __init__(self, state, admin):
        BaseAdminGtkNode.__init__(self, state, admin, title=_("Component"))

        self._startTime = None
        self._debugging = None
        self._initialFluMask = ''
        self._initialGstMask = ''

    def setDebugEnabled(self, enabled):
        BaseAdminGtkNode.setDebugEnabled(self, enabled)
        if self._debugging:
            self._debugging.set_property('visible', enabled)

        self._initialFluMask = getDebug()
        self._initialGstMask = os.environ.get('GST_DEBUG', '')

    def haveWidgetTree(self):
        self.widget = self.wtree.get_widget('main-vbox')
        assert self.widget, "No component-widget in %s" % self.gladeFile
        self.gst_mask = self.wtree.get_widget('gst_mask')
        self.gst_label = self.wtree.get_widget('gst_label')
        self.flu_mask = self.wtree.get_widget('flu_mask')
        self.gst_profile = self.wtree.get_widget('gst_profile')
        self.gst_profile.connect('changed', self._on_gst_profile_changed)
        self.flu_profile = self.wtree.get_widget('flu_profile')
        self.flu_profile.connect('changed', self._on_flu_profile_changed)
        self.gst_button = self.wtree.get_widget('gst_button')
        self.gst_button.connect('clicked', self._on_gst_button_clicked)
        self.gst_mask.connect('activate', self._on_gst_button_clicked)
        self.flu_button = self.wtree.get_widget('flu_button')
        self.flu_button.connect('clicked', self._on_flu_button_clicked)
        self.flu_mask.connect('activate', self._on_flu_button_clicked)

        # pid
        l = self.wtree.get_widget('label-pid')
        pid = self.state.get('pid')
        l.set_text(str(pid))

        # Find the labels which we'll update when we get uiState updates.
        self._label_start_time = self.wtree.get_widget('label-since')
        self._label_uptime = self.wtree.get_widget('label-uptime')
        self._label_cpu = self.wtree.get_widget('label-cpu')
        self._label_vsize = self.wtree.get_widget('label-vsize')
        self._label_component_type = self.wtree.get_widget(
            'label-component-type')

        self._label_resets = self.wtree.get_widget('label-resets')
        self._label_resets_count = self.wtree.get_widget('label-resets-count')
        self.widget.show()

        self._prepareDebugging()

        self._debugging = self.wtree.get_widget('debugging')
        if self._debugEnabled:
            self._debugging.show()

        componentType = self.state.get('config')['type']
        self._label_component_type.set_text(componentType)

        return self.widget

    def _validateMask(self, mask):
        if ':' not in mask or mask.count(':') != 1:
            return False
        name, level = mask.split(':', 1)
        try:
            int(level)
        except ValueError:
            return False
        return True

    def _on_gst_profile_changed(self, combo):
        print("fired on gst combo box changed!")
        profile = combo.get_selected()
        print("Got selected item: %s" % str(profile))
        if profile is not None:
            gtk.Entry.set_text(self.gst_mask, profile)
        self.gst_mask.set_sensitive(profile is None)

    def _on_flu_profile_changed(self, combo):
        print("fired on flu combo box changed!")
        profile = combo.get_selected()
        if profile is not None:
            gtk.Entry.set_text(self.flu_mask, profile)
        self.flu_mask.set_sensitive(profile is None)

    def _on_flu_button_clicked(self, widget):
        debug = self.flu_mask.get_text()
        if not self._debugEnabled or not self._validateMask(debug):
            return
        self.info('setting flu debug to %s for %s' % (
            debug, self.state.get('name')))
        self.admin.componentCallRemote(self.state, 'setFluDebug', debug)

    def _on_gst_button_clicked(self, widget):
        debug = self.gst_mask.get_text()
        if not self._debugEnabled or not self._validateMask(debug):
            return
        self.info('setting gst debug to %s for %s' % (
            debug, self.state.get('name')))
        self.admin.componentCallRemote(self.state, 'setGstDebug', debug)

    def _prepareDebugging(self):
        debugEnabled = self._debugEnabled
        self._debugEnabled = False
        default = [(_('Nothing'), '*:0'),
                   (_('Everything'), '*:4'),
                   (_('Custom'), None)]
        self.flu_profile.prefill(default)

        if isinstance(self.state.get('parent'), AdminFlowState):
            self.gst_profile.prefill(default)
            x = 2
        else:
            self.gst_profile.hide()
            self.gst_label.hide()
            self.gst_mask.hide()
            self.gst_button.hide()

        self._debugEnabled = debugEnabled

    def _setStartTime(self, value):
        self._label_start_time.set_text(
            time.strftime("%c", time.localtime(value)))
        self._label_uptime.set_text(formatting.formatTime(0))

        self._startTime = value

    def _setCurrentTime(self, value):
        if self._startTime is not None:
            runtime = value - self._startTime

            self._label_uptime.set_text(formatting.formatTime(runtime))
        else:
            self._label_uptime.set_text(_("not available"))

    def _setGstDebug(self, value):
        """ The below lines are commented out because we need
            to rip out kiwi - Here is the kiwi code that needs to be 
            implemented hee:
            def select_item_by_data(self, data):
                if self.mode != ComboMode.DATA:
                    raise TypeError("select_item_by_data can only be used in data mode")
                model = self._combobox.get_model()
                for row in model:
                    if row[ComboColumn.DATA] == data:
                        self._combobox.set_active_iter(row.iter)
                        break
                    else:
                        raise KeyError("No item correspond to data %r in the combo %s"
                            % (data, self._combobox.get_name()))
        """
        self.gst_mask.set_text(value)
        try:
           print("value is: %s" % value)
           self.gst_profile.select_item_by_data(value)
        except KeyError:
            self.gst_profile.select_item_by_data(None)

    def _setFluDebug(self, value):
        self.flu_mask.set_text(value)
        try:
            b = 2
            self.flu_profile.select_item_by_data(value)
        except KeyError:
            self.flu_profile.select_item_by_data(None)

    def _updateCPU(self, cpu):
        # given float for cpu, update the label
        self._label_cpu.set_text('%.2f %%' % (cpu * 100.0))

    def _updateVSize(self, vsize):
        # given int for vsize in bytes, update the label
        if not vsize:
            self._label_vsize.set_text(_('Unknown'))
        else:
            self._label_vsize.set_text('%sB' % formatting.formatStorage(vsize))

    def _updateResets(self, count):
        if not self._label_resets.get_property('visible'):
            self._label_resets.show()
            self._label_resets_count.show()
        self._label_resets_count.set_text('%d restarts' % count)

    def setUIState(self, uiState):
        BaseAdminGtkNode.setUIState(self, uiState)

        # Ick; we don't get these otherwise.
        for key in uiState.keys():
            val = uiState.get(key)
            if val is not None:
                self.stateSet(uiState, key, uiState.get(key))

    # IStateListener Interface

    def stateSet(self, object, key, value):
        if key == 'cpu-percent':
            self._updateCPU(value)
        elif key == 'virtual-size':
            self._updateVSize(value)
        elif key == 'start-time':
            self._setStartTime(value)
        elif key == 'current-time':
            self._setCurrentTime(value)
        elif key == 'reset-count':
            self._updateResets(value)
        elif key == 'flu-debug':
            self._setFluDebug(value)
        elif key == 'gst-debug':
            self._setGstDebug(value)

    def stateAppend(self, object, key, value):
        pass

    def stateRemove(self, object, key, value):
        pass
