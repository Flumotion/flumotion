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

"""
Flumotion tray icon widget.
"""

import os

import gobject
import gtk

from zope.interface import implements

from flumotion.common import log, planet
from flumotion.common.planet import moods
from flumotion.common.pygobject import gsignal, type_register
from flumotion.configure import configure
from flumotion.twisted import flavors

__version__ = "$Rev$"


class FluTrayIcon(log.Loggable, gobject.GObject):
    """
    I represent a tray icon in GNOME's notification area for the Admin UI.

    If I cannot create a tray icon, I will still be usable but not do anything.
    """

    implements(flavors.IStateListener)

    logCategory = 'trayui'

    gsignal("quit")

    def __init__(self, window):
        """
        @type window: L{flumotion.admin.gtk.client.Window}
        """
        gobject.GObject.__init__(self)

        self._tray_container = None
        self._components = None
        self._window = window

        self._create_trayicon()

    def _create_trayicon(self):
        # start off with just the fluendo logo
        try:
            from flumotion.extern import pytrayicon
        except ImportError:
            self.debug('No pytrayicon module found, no trayicon will be shown')
            return
        try:
            self._tray_container = pytrayicon.TrayIcon("Flumotion")
        except AttributeError:
            self.debug('No pytrayicon installed, no trayicon will be shown')
            return

        self._tray_event_box = gtk.EventBox()
        self._tray_image = gtk.Image()
        pixbuf = gtk.gdk.pixbuf_new_from_file(os.path.join(
            configure.imagedir, 'flumotion.png'))
        scaled_buf = pixbuf.scale_simple(24, 24, gtk.gdk.INTERP_BILINEAR)
        self._tray_image.set_from_pixbuf(scaled_buf)
        self._tray_event_box.add(self._tray_image)
        # make tray icon show/hide the main window when clicked
        self._tray_event_box.connect("button-press-event",
            self._trayicon_clicked)
        if self._tray_container:
            self._tray_container.add(self._tray_event_box)
            self._tray_container.show_all()

    def update(self, components):
        """
        Update the components list

        @param components: dictionary of name ->
                           L{flumotion.common.component.AdminComponentState}
        """
        if not self._tray_container:
            return

        self.debug('updating component in trayicon view')

        # get a dictionary of components
        self._components = components
        for component in components.values():
            try:
                component.addListener(self, set_=self.stateSet)
            except KeyError:
                pass

        self._update_mood()

    def _trayicon_clicked(self, widget, event):
        """
        @param widget: the trayicon eventbox that was clicked
        @param event: the event object
        """
        # left click triggers window visibility
        # TODO: implement right click for popup menu
        if event.button == 1:
            if self._window.get_property('visible'):
                self._window.hide()
            else:
                self._window.show()
        elif event.button == 3:
            self._show_popup_menu()

    # FIXME: looks like cutnpaste from a similar function, squash duplication
    def _update_mood(self):
        """
        This method goes through all the components to
        determine and set the overall mood.
        """
        # get a dictionary of components
        names = self._components.keys()
        # if no components, show fluendo logo
        if len(names) == 0:
            pixbuf = gtk.gdk.pixbuf_new_from_file(os.path.join(
                configure.imagedir, 'flumotion.png'))
            scaled_buf = pixbuf.scale_simple(24, 24, gtk.gdk.INTERP_BILINEAR)
            self._tray_image.set_from_pixbuf(scaled_buf)
        else:
            # get overall mood of components
            overallmood = moods.happy.value
            for compName in names:
                component = self._components[compName]
                mood = component.get('mood')
                self.debug("component %s has mood %d" % (compName, mood))
                if mood > overallmood:
                    overallmood = mood

            moodname = moods.get(overallmood).name
            self.debug("overall mood: %s %d" % (moodname, overallmood))
            pixbuf = gtk.gdk.pixbuf_new_from_file(os.path.join(
                configure.imagedir, 'mood-%s.png' % moodname))
            scaled_buf = pixbuf.scale_simple(24, 24, gtk.gdk.INTERP_BILINEAR)
            self._tray_image.set_from_pixbuf(scaled_buf)

    def stateSet(self, state, key, value):
        if not isinstance(state, planet.AdminComponentState):
            self.warning('Got state change for unknown object %r' % state)
            return

        if key == 'mood':
            # one of the components has changed mood
            self._update_mood()
        elif key == 'message':
            # one of the components has sent a message
            self.debug("message: %s" % value)
            if self._tray_container:
                self._tray_container.send_message(1000, value)

    def _quit_activate_cb(self, menu):
        self.emit('quit')

    def _show_popup_menu(self):
        self.popupMenu = gtk.Menu()
        self.popupMenuQuititem = gtk.ImageMenuItem(gtk.STOCK_QUIT)
        self.popupMenuQuititem.connect('activate', self._quit_activate_cb)
        self.popupMenu.add(self.popupMenuQuititem)
        self.popupMenu.popup(None, None, None, 3, gtk.get_current_event_time())
        self.popupMenu.show_all()

    def set_tooltip(self, tooltip):
        if self._tray_container:
            self._tray_container.set_tooltip(tooltip)

type_register(FluTrayIcon)
