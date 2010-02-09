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

"""A widget which can used open a link"""

import gtk

__version__ = "$Rev$"


class LinkWidgetOld(gtk.EventBox):

    def __init__(self, uri):
        gtk.EventBox.__init__(self)
        self.connect('button-press-event', self._on_button_press_event)
        self.connect('enter-notify-event', self._on_enter_notify_event)
        self.connect('leave-notify-event', self._on_leave_notify_event)
        self.set_visible_window(False)

        self._callback = None
        self._popupmenu = self._create_popup_menu()

        self._label = gtk.Label()
        self.add(self._label)
        self._label.show()

        self.set_uri(uri)

    # Public API

    def set_uri(self, url):
        self._label.set_markup(
            '<span foreground="blue">%s</span>' % url)

    def set_callback(self, callback):
        self._callback = callback

    # Private

    def _create_popup_menu(self):
        popupmenu = gtk.Menu()
        item = gtk.ImageMenuItem('_Open Link')
        image = gtk.Image()
        image.set_from_stock(gtk.STOCK_JUMP_TO, gtk.ICON_SIZE_MENU)
        item.set_image(image)
        item.show()
        item.connect('activate', self._on_open_link_activate)
        popupmenu.add(item)

        item = gtk.ImageMenuItem('Copy _Link Address')
        image = gtk.Image()
        image.set_from_stock(gtk.STOCK_COPY, gtk.ICON_SIZE_MENU)
        item.set_image(image)
        item.show()
        item.connect('activate', self._on_copy_link_activate)
        popupmenu.add(item)
        return popupmenu

    def _show_url(self, url):
        if self._callback:
            self._callback(url)

    # Callbacks

    def _on_button_press_event(self, widget, event):
        # signal handler for button press on stream url
        # check if left click
        if event.button == 1:
            url = self._label.get_text()
            self._show_url(url)
        elif event.button == 3:
            self._popupmenu.popup(None, None, None, event.button, event.time)

    def _on_enter_notify_event(self, widget, event):
        cursor = gtk.gdk.Cursor(widget.get_display(), gtk.gdk.HAND2)
        widget.window.set_cursor(cursor)

    def _on_leave_notify_event(self, widget, event):
        widget.window.set_cursor(None)

    def _on_open_link_activate(self, widget):
        # signal handler for open link menu item activation
        # eventbox is the eventbox that contains the label the url is in
        url = self._label.get_text()
        self._show_url(url)

    def _on_copy_link_activate(self, widget):
        # signal handler for copy link menu item activation
        # eventbox is the eventbox that contains the label the url is in
        clipboard = gtk.Clipboard()
        clipboard.set_text(self._label.get_text())


if hasattr(gtk, 'LinkButton'):

    class LinkWidget(gtk.LinkButton):

        def __init__(self, uri):
            gtk.LinkButton.__init__(self, uri, label=uri)
            self.set_property('can-focus', False)
            self._callback = None
            gtk.link_button_set_uri_hook(self.on_link_button_clicked)

        def set_callback(self, callback):
            self._callback = callback

        def on_link_button_clicked(self, widget, uri):
            if self._callback:
                self._callback(uri)
else:
    LinkWidget = LinkWidgetOld

if not hasattr(LinkWidget, 'set_tooltip_text'):
    LinkWidget.set_tooltip_text = lambda self, text: None
