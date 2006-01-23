# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2004,2005,2006 Fluendo, S.L. (www.fluendo.com).
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
import time

import gtk

from gettext import gettext as _

from flumotion.common import errors

# FIXME: remove when we do a proper deferred
from twisted.internet import defer

from flumotion.component.base.admin_gtk import BaseAdminGtk, BaseAdminGtkNode

class StatisticsAdminGtkNode(BaseAdminGtkNode):
    glade_file = os.path.join('flumotion', 'component', 'consumers',
        'httpstreamer', 'http.glade')

    def __init__(self, *args, **kwargs):
        BaseAdminGtkNode.__init__(self, *args, **kwargs)
        self.shown = False
        self._stats = None

    def error_dialog(self, message):
        # FIXME: dialogize
        print 'ERROR:', message
        
    def cb_getMimeType(self, mime, label):
        label.set_text(_('Mime type:') + " %s" % mime)
        label.show()

    def setStats(self, stats):
        if not hasattr(self, 'statistics'):
            # widget tree not created yet
            self._stats = stats
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

        # changed in 0.1.9.1 to be int so we can localize time
        peakTime = state.get('clients-peak-time')
        if not isinstance(peakTime, str):
            peakTime = time.strftime ("%c", time.localtime(peakTime))
            
            self.debug('Converted peak time to %s' % peakTime)
        self.labels['clients-peak-time'].set_text(peakTime)
        
        for name in self.labels.keys():
            if name == 'clients-peak-time':
                continue
            text = state.get(name)
            if text == None:
                text = ''
            self.labels[name].set_text(text)
        
    def haveWidgetTree(self):
        self.labels = {}
        self.statistics = self.wtree.get_widget('statistics-widget')
        for type in ('uptime', 'mime', 'bitrate', 'totalbytes'):
            self.registerLabel('stream-' + type)
        for type in ('current', 'average', 'max', 'peak', 'peak-time'):
            self.registerLabel('clients-' + type)
        for type in ('bitrate', 'totalbytes'):
            self.registerLabel('consumption-' + type)

        if self._stats:
            self.shown = True
            self.updateLabels(self._stats)
            self.statistics.show_all()

        return self.statistics

class LogAdminGtkNode(BaseAdminGtkNode):
    logCategory = 'logadmin'

    def render(self):
        w = gtk.TextView()
        w.set_cursor_visible(False)
        w.set_wrap_mode(gtk.WRAP_WORD)
        self._buffer = w.get_buffer()
        return defer.succeed(w)

    def logMessage(self, message):
        self._buffer.insert_at_cursor(message)

class HTTPStreamerAdminGtk(BaseAdminGtk):
    def setup(self):
        statistics = StatisticsAdminGtkNode(self.state, self.admin, 
            _("Statistics"))
        self.nodes['Statistics'] = statistics
        log = LogAdminGtkNode(self.state, self.admin, _('Log'))
        self.nodes['Log'] = log

    def uiStateChanged(self, state):
        self.nodes['Statistics'].setStats(state)

    # FIXME: tie this to the statistics node better
    def component_statsChanged(self, stats):
        # FIXME: decide on state/stats/statistics
        self.nodes['Statistics'].setStats(stats)

    def component_logMessage(self, message):
        self.nodes['Log'].logMessage(message)
 
GUIClass = HTTPStreamerAdminGtk
