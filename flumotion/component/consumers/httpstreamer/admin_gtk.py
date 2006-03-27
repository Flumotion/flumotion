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
        self._hasgnomevfs = False
        try:
            import gnomevfs
            self._hasgnomevfs = True
        except:
            pass

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
            # set http url with nice pango markup if gnomevfs present
            # if not it should be black...so ppl dont click on it
            if name == 'stream-url' and self._hasgnomevfs:
                text = '<span foreground="blue">%s</span>' % text
                self.labels[name].set_markup(text)
            else:
                self.labels[name].set_text(text)
        
    def haveWidgetTree(self):
        self.labels = {}
        self.statistics = self.wtree.get_widget('statistics-widget')
        for type in ('uptime', 'mime', 'bitrate', 'totalbytes', 'url'):
            self.registerLabel('stream-' + type)
        for type in ('current', 'average', 'max', 'peak', 'peak-time'):
            self.registerLabel('clients-' + type)
        for type in ('bitrate', 'totalbytes'):
            self.registerLabel('consumption-' + type)

        if self._stats:
            self.shown = True
            self.updateLabels(self._stats)
            self.statistics.show_all()

        # add signal handler for Stream URL only if we have gnomevfs
        # also signal handler to notify when mouse has gone over label
        # so cursor changes
        # add popup menu to let you open url or copy link location
        
        if self._hasgnomevfs:
            streamurl_widget_eventbox = self.wtree.get_widget('eventbox-stream-url')
            streamurl_widget_eventbox.connect('button-press-event', self._streamurl_clicked)
            streamurl_widget_eventbox.connect('enter-notify-event', self._streamurl_enter)
            streamurl_widget_eventbox.connect('leave-notify-event', self._streamurl_leave)
            self._streamurl_popupmenu = gtk.Menu()
            item = gtk.ImageMenuItem('_Open Link')
            image = gtk.Image()
            image.set_from_stock(gtk.STOCK_JUMP_TO, gtk.ICON_SIZE_MENU)
            item.set_image(image)
            item.show()
            item.connect('activate', self._streamurl_openlink, streamurl_widget_eventbox)
            self._streamurl_popupmenu.add(item)
            item = gtk.ImageMenuItem('Copy _Link Address')
            image = gtk.Image()
            image.set_from_stock(gtk.STOCK_COPY, gtk.ICON_SIZE_MENU)
            item.set_image(image)
            item.show()
            item.connect('activate', self._streamurl_copylink, streamurl_widget_eventbox)
            self._streamurl_popupmenu.add(item)
            
        return self.statistics

    # signal handler for button press on stream url
    def _streamurl_clicked(self, widget, event):
        # check if left click
        if event.button == 1:
            url = widget.get_children()[0].get_text()
            import gnomevfs
            app_to_run = gnomevfs.mime_get_default_application(self._stats.get('stream-mime'))
            if app_to_run:
                os.system("%s %s &" % (app_to_run[2],url))
        elif event.button == 3:
            self._streamurl_popupmenu.popup(None, None, None, event.button, event.time)
        
    # signal handler for open link menu item activation
    # eventbox is the eventbox that contains the label the url is in
    def _streamurl_openlink(self, widget, eventbox):
        url = eventbox.get_children()[0].get_text()
        import gnomevfs
        app_to_run = gnomevfs.mime_get_default_application(self._stats.get('stream-mime'))
        if app_to_run:
            os.system("%s %s &" % (app_to_run[2],url))

    # signal handler for copy link menu item activation
    # eventbox is the eventbox that contains the label the url is in
    def _streamurl_copylink(self, widget, eventbox):
        url = eventbox.get_children()[0].get_text()
        clipboard = gtk.Clipboard()
        clipboard.set_text(url)

    # motion event handles
    def _streamurl_enter(self, widget, event):
        cursor = gtk.gdk.Cursor(widget.get_display(), gtk.gdk.HAND2)
        window = widget.get_root_window()
        window.set_cursor(cursor)
            
    def _streamurl_leave(self, widget, event):
        window = widget.get_root_window()
        window.set_cursor(None)
            
    
    
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
        # FIXME: maybe make a protocol instead of overriding
        return BaseAdminGtk.setup(self)

    def uiStateChanged(self, state):
        self.nodes['Statistics'].setStats(state)

    # FIXME: tie this to the statistics node better
    def component_statsChanged(self, stats):
        # FIXME: decide on state/stats/statistics
        self.nodes['Statistics'].setStats(stats)

    def component_logMessage(self, message):
        self.nodes['Log'].logMessage(message)
 
GUIClass = HTTPStreamerAdminGtk
