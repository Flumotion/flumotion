# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# flumotion/component/consumer/httpstreamer/gtk.py
# admin client-side code for httpstreamer
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

import os
import gtk

from flumotion.common import errors

from flumotion.component.base.admin_gtk import BaseAdminGtk, BaseAdminGtkNode

class StatisticsAdminGtkNode(BaseAdminGtkNode):
    def error_dialog(self, message):
        # FIXME: dialogize
        print 'ERROR:', message
        
    def cb_getMimeType(self, mime, label):
        label.set_text('Mime type: %s' % mime)
        label.show()

    def setUIState(self, state):
        self.updateLabels(state)
        if not self.shown:
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
        for name in self.labels.keys():
            text = state[name]
            if text is None:
                text = ''
            self.labels[name].set_text(text)
        
    def render(self):
        gladeFile = os.path.join('flumotion', 'component', 'consumers',
            'httpstreamer', 'http.glade')
        d = self.loadGladeFile(gladeFile)
        d.addCallback(self._loadGladeFileCallback)
        return d

    def _loadGladeFileCallback(self, widgetTree):
        self.wtree = widgetTree
        self.labels = {}
        self.statistics = self.wtree.get_widget('statistics-widget')
        for type in ('uptime', 'mime', 'bitrate', 'totalbytes'):
            self.registerLabel('stream-' + type)
        for type in ('current', 'average', 'max', 'peak', 'peak-time'):
            self.registerLabel('clients-' + type)
        for type in ('bitrate', 'totalbytes'):
            self.registerLabel('consumption-' + type)

        self.callRemote('notifyState')
        self.shown = False
        return self.statistics

class HTTPStreamerAdminGtk(BaseAdminGtk):
    def setup(self):
        self._nodes = {}
        statistics = StatisticsAdminGtkNode(self.name, self.admin,
            self.view)
        self._nodes['statistics'] = statistics

    # FIXME: tie this to the statistics node better
    def setUIState(self, state):
        self._nodes['statistics'].setUIState(state)
 
    def getNodes(self):
        return self._nodes

GUIClass = HTTPStreamerAdminGtk
