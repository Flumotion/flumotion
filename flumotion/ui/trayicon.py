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

_DEFAULT_ICON = os.path.join(configure.imagedir, 'flumotion.png')


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

        self._components = None
        self._window = window
        self._tray_image = None
        self._tray_icon = self._create_trayicon()
        self._set_icon_from_filename(_DEFAULT_ICON)

    # Public methods

    def update(self, components):
        """
        Update the components list

        @param components: dictionary of name ->
                           L{flumotion.common.component.AdminComponentState}
        """
        if not self._tray_icon:
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
            if self._tray_icon and hasattr(self._tray_icon, 'send_message'):
                self._tray_icon.send_message(1000, value)

    def set_tooltip(self, tooltip):
        """
        @param tooltip: Text to show when the mouse is over the tray icon.
        @type  tooltip: str
        """
        if self._tray_icon:
            self._tray_icon.set_tooltip(tooltip)

    # Private methods

    def _create_trayicon(self):
        """
        Create the icon
        """
        if hasattr(gtk, 'StatusIcon'):
            icon = gtk.StatusIcon()
            icon.connect('popup-menu', self._on_trayicon__popup_menu)
            icon.connect('activate', self._on_trayicon__activated)
        else:
            try:
                from flumotion.extern import pytrayicon
                icon = pytrayicon.TrayIcon("Flumotion")
            except ImportError:
                self.debug('No pytrayicon module found,'
                           ' no trayicon will be shown')
                return
            except AttributeError:
                self.debug('No pytrayicon installed,'
                           'no trayicon will be shown')
                return

            event_box = gtk.EventBox()
            self._tray_image = gtk.Image()
            event_box.add(self._tray_image)
            event_box.connect('button-press-event', self._on_trayicon__clicked)
            icon.add(event_box)
            icon.show_all()

        return icon

    def _set_icon_from_filename(self, filename):
        if not self._tray_icon:
            return

        if self._tray_image:
            pixbuf = gtk.gdk.pixbuf_new_from_file(filename)
            scaled_buf = pixbuf.scale_simple(24, 24, gtk.gdk.INTERP_BILINEAR)
            self._tray_image.set_from_pixbuf(scaled_buf)
        else:
            self._tray_icon.set_from_file(filename)

    # FIXME: looks like cutnpaste from a similar function, squash duplication

    def _update_mood(self):
        """
        This method goes through all the components to
        determine and set the overall mood.
        """
        # get a dictionary of components
        names = self._components.keys()

        if names:
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
            filename = os.path.join(configure.imagedir,
                                    'mood-%s.png' % moodname)
            self._set_icon_from_filename(filename)
        else:
            # if no components, show fluendo logo
            self._set_icon_from_filename(_DEFAULT_ICON)

    # Callbacks

    def _on_trayicon__clicked(self, widget, event):
        """
        @param widget: the trayicon eventbox that was clicked
        @param event: the event object
        """
        # left click triggers window visibility
        if event.button == 1:
            self._on_trayicon__activated()
        elif event.button == 3:
            self._on_trayicon__popup_menu()

    def _on_trayicon__popup_menu(self, *p):
        """
        Called when we click the tray icon with the second mouse's button.
        Shows a popup menu with the quit option.
        """
        menu = gtk.Menu()
        quit = gtk.ImageMenuItem(gtk.STOCK_QUIT)
        quit.connect('activate', self._on_quit__activate)
        menu.add(quit)
        menu.popup(None, None, None, 3, gtk.get_current_event_time())
        menu.show_all()

    def _on_trayicon__activated(self, *p):
        """
        Called when we click the tray icon with the first mouse's button.
        Shows or hides the main window.
        """
        if self._window.get_property('visible'):
            self._window.hide()
        else:
            self._window.show()

    def _on_quit__activate(self, menu):
        """
        Called when we click the quit  option on the popup menu.
        """
        self.emit('quit')

type_register(FluTrayIcon)
