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

import os
import gtk

from gettext import gettext as _

from flumotion.component.base.admin_gtk import BaseAdminGtk, BaseAdminGtkNode

class StatisticsAdminGtkNode(BaseAdminGtkNode):
    glade_file = os.path.join('flumotion', 'component', 'misc',
        'httpfile', 'httpfile.glade')

    def __init__(self, *args, **kwargs):
        BaseAdminGtkNode.__init__(self, *args, **kwargs)
        self.shown = False
        self._stats = None

    def setStats(self, stats):
        # Set _stats regardless of if condition
        # Used to be a race where _stats was
        # not set if widget tree was gotten before
        # ui state
        self._stats = stats
        if not hasattr(self, 'statistics'):
            # widget tree not created yet
            return

        self.updateLabels(stats)

        if not self.shown:
            # widget tree created but not yet shown
            self.shown = True
            self.statistics.show_all()
       
    def registerLabel(self, name):
        #widgetname = name.replace('-', '_')
        #FIXME: make object member directly
        widget = self.wtree.get_widget('label-' + name)
        if widget:
            self.labels[name] = widget
        else:
            print "FIXME: no widget %s" % name

    def hideLabels(self):
        for name in self.labels.keys():
            self.labels[name].hide()

    def updateLabels(self, state):
        if not hasattr(self, 'labels'):
            return
        
        for name in self.labels.keys():
            text = state.get(name)
            if text == None:
                text = ''
            else:
                self.labels[name].set_text(str(text))
        
    def haveWidgetTree(self):
        self.labels = {}
        self.statistics = self.wtree.get_widget('statistics-widget')
        self.widget = self.statistics
        for type in ('bytes-transferred', 'connected-clients'):
            self.registerLabel(type)

        if self._stats:
            self.shown = True
            self.updateLabels(self._stats)
            self.statistics.show_all()

        return self.statistics

class HTTPFileAdminGtk(BaseAdminGtk):
    def setup(self):
        statistics = StatisticsAdminGtkNode(self.state, self.admin)
        self.nodes['Statistics'] = statistics
        # FIXME: maybe make a protocol instead of overriding
        return BaseAdminGtk.setup(self)

    def uiStateChanged(self, state):
        self.nodes['Statistics'].setStats(state)

GUIClass = HTTPFileAdminGtk
