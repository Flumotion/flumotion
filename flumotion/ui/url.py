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
# Streaming Server license may use this file in accordance with th
# Flumotion Advanced Streaming Server Commercial License Agreement.
# See "LICENSE.Flumotion" in the source distribution for more information.

# Headers in this file shall remain intact.


import os
import gtk

class ClickyURL(gtk.EventBox):
    def __init__(self, url, mime_type='application/ogg'):
        gtk.EventBox.__init__(self)

        self.url = url
        self.mime_type = mime_type

        try:
            import gnomevfs
            self.gnomevfs = gnomevfs
        except ImportError:
            self.gnomevfs = None

        # set http url with nice pango markup if gnomevfs present
        # if not it should be black...so ppl dont click on it
        label = gtk.Label()
        if self.gnomevfs:
            text = '<span foreground="blue">%s</span>' % self.url
            label.set_markup(text)
        else:
            label.set_text(text)
        label.show()
        self.add(label)

        if self.gnomevfs:
            self.set_visible_window(False)
            self.connect('button-press-event', self._streamurl_clicked)
            self.connect('enter-notify-event', self._streamurl_enter)
            self.connect('leave-notify-event', self._streamurl_leave)
            self._streamurl_popupmenu = gtk.Menu()
            item = gtk.ImageMenuItem('_Open Link')
            image = gtk.Image()
            image.set_from_stock(gtk.STOCK_JUMP_TO, gtk.ICON_SIZE_MENU)
            item.set_image(image)
            item.show()
            item.connect('activate', self._streamurl_openlink)
            self._streamurl_popupmenu.add(item)
            item = gtk.ImageMenuItem('Copy _Link Address')
            image = gtk.Image()
            image.set_from_stock(gtk.STOCK_COPY, gtk.ICON_SIZE_MENU)
            item.set_image(image)
            item.show()
            item.connect('activate', self._streamurl_copylink)
            self._streamurl_popupmenu.add(item)

    def open_url(self):
        app = self.gnomevfs.mime_get_default_application(self.mime_type)
        if app:
            # FIXME: this is not secure dude
            os.system("%s %s &" % (app[2], self.url))

    # signal handler for button press on stream url
    def _streamurl_clicked(self, widget, event):
        if event.button == 1:
            self.open_url()
        elif event.button == 3:
            self._streamurl_popupmenu.popup(None, None, None,
                                            event.button, event.time)

    # signal handler for open link menu item activation
    def _streamurl_openlink(self, widget):
        self.open_url()

    # signal handler for copy link menu item activation
    def _streamurl_copylink(self, widget):
        gtk.Clipboard().set_text(self.url)

    # motion event handles
    def _streamurl_enter(self, widget, event):
        cursor = gtk.gdk.Cursor(widget.get_display(), gtk.gdk.HAND2)
        window = widget.window
        window.set_cursor(cursor)

    def _streamurl_leave(self, widget, event):
        window = widget.window
        window.set_cursor(None)
