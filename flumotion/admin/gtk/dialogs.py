# -*- Mode: Python; test-case-name: flumotion.test.test_dialogs -*-
# -*- coding: UTF-8 -*-
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

__version__ = "$Rev$"

from gettext import gettext as _
import os

import gtk
import gobject

from flumotion.configure import configure
from flumotion.common.pygobject import gsignal
from flumotion.common import pygobject


class ProgressDialog(gtk.Dialog):
    def __init__(self, title, message, parent = None):
        gtk.Dialog.__init__(self, title, parent,
                            gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT)


        self.label = gtk.Label(message)
        self.vbox.pack_start(self.label, True, True, 6)
        self.label.show()
        self.bar = gtk.ProgressBar()
        self.bar.show()
        self.vbox.pack_end(self.bar, True, True, 6)
        self.active = False
        self._timeout_id = None

        self.connect('destroy', self._destroy_cb)

    def start(self):
        "Show the dialog and start pulsating."
        self.active = True
        self.show()
        self.bar.pulse()
        self._timeout_id = gobject.timeout_add(200, self._pulse)

    def stop(self):
        "Remove the dialog and stop pulsating."
        self.active = False
        if self._timeout_id:
            gobject.source_remove(self._timeout_id)
            self._timeout_id = None

    def message(self, message):
        "Set the message on the dialog."
        self.label.set_text(message)

    def _pulse(self):
        if not self.active:
            # we were disabled, so stop pulsating
            return False
        self.bar.pulse()
        return True

    def _destroy_cb(self, widget):
        self.stop()

class ErrorDialog(gtk.MessageDialog):
    def __init__(self, message, parent=None, close_on_response=True,
                 secondary_text=None):
        gtk.MessageDialog.__init__(self, parent, gtk.DIALOG_MODAL,
            gtk.MESSAGE_ERROR, gtk.BUTTONS_OK, message)
        b = self.action_area.get_children()[0]
        b.set_name('ok_button')
        self.message = message
        if close_on_response:
            self.connect("response", lambda self, response: self.hide())

        # GTK 2.4 does not have format_secondary_text
        if not hasattr(self, 'format_secondary_text'):
            self.format_secondary_text = self._format_secondary_text_backport

        if secondary_text:
            self.format_secondary_text(secondary_text)

    def _format_secondary_text_backport(self, secondary_text):
        self.set_markup('<span weight="bold" size="larger">%s</span>'
                        '\n\n%s' % (self.message, secondary_text))

    def run(self):
        # can't run a recursive mainloop, because that mucks with
        # twisted's reactor.
        from twisted.internet import defer
        deferred = defer.Deferred()
        def callback(_, response, deferred):
            self.destroy()
            deferred.callback(None)
        self.connect('response', callback, deferred)
        self.show()
        return deferred

def connection_refused_message(host, parent=None):
    d = ErrorDialog('Connection refused', parent, True,
                    '"%s" refused your connection.\n'
                    'Check your user name and password and try again.'
                    % host)
    return d.run()

def connection_failed_message(info, debug, parent=None):
    message = (_("Connection to manager on %s failed (%s).")
               % (str(info), debug))
    d = ErrorDialog('Connection failed', parent, True, message)
    return d.run()

def already_connected_message(info, parent=None):
    d = ErrorDialog('Already connected to %s' % info, parent, True,
                    "Seek your satisfaction via existing routes.")
    return d.run()

class PropertyChangeDialog(gtk.Dialog):
    """
    I am a dialog to get and set GStreamer element properties on a component.
    """

    gsignal('set', str, str, object)
    gsignal('get', str, str)

    RESPONSE_FETCH = 0

    def __init__(self, name, parent):
        title = "Change element property on '%s'" % name
        gtk.Dialog.__init__(self, title, parent,
                            gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT)
        self.connect('response', self.response_cb)
        self._close = self.add_button('Close', gtk.RESPONSE_CLOSE)
        self._set = self.add_button('Set', gtk.RESPONSE_APPLY)
        self._fetch = self.add_button('Fetch current', self.RESPONSE_FETCH)

        hbox = gtk.HBox()
        hbox.show()

        label = gtk.Label('Element')
        label.show()
        hbox.pack_start(label, False, False)
        self.element_combo = gtk.ComboBox()
        self.element_entry = gtk.Entry()
        self.element_entry.show()
        hbox.pack_start(self.element_entry, False, False)

        label = gtk.Label('Property')
        label.show()
        hbox.pack_start(label, False, False)
        self.property_entry = gtk.Entry()
        self.property_entry.show()
        hbox.pack_start(self.property_entry, False, False)

        label = gtk.Label('Value')
        label.show()
        hbox.pack_start(label, False, False)
        self.value_entry = gtk.Entry()
        self.value_entry.show()
        hbox.pack_start(self.value_entry, False, False)

        self.vbox.pack_start(hbox)

    def response_cb(self, dialog, response):
        if response == gtk.RESPONSE_APPLY:
            self.emit('set', self.element_entry.get_text(),
                      self.property_entry.get_text(),
                      self.value_entry.get_text())
        elif response == self.RESPONSE_FETCH:
            self.emit('get', self.element_entry.get_text(),
                      self.property_entry.get_text())
        elif response == gtk.RESPONSE_CLOSE:
            dialog.hide()

    def update_value_entry(self, value):
        self.value_entry.set_text(str(value))

pygobject.type_register(PropertyChangeDialog)

class AboutDialog(gtk.Dialog):
    def __init__(self, parent=None):
        gtk.Dialog.__init__(self, _('About Flumotion'), parent,
                            gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
                            (gtk.STOCK_CLOSE, gtk.RESPONSE_CLOSE))
        self.set_has_separator(False)
        self.set_resizable(False)
        self.set_border_width(12)
        self.vbox.set_spacing(6)

        image = gtk.Image()
        self.vbox.pack_start(image)
        image.set_from_file(os.path.join(configure.imagedir, 'fluendo.png'))
        image.show()

        version = gtk.Label(
            '<span size="xx-large"><b>Flumotion %s</b></span>' %
                configure.version)
        version.set_selectable(True)
        self.vbox.pack_start(version)
        version.set_use_markup(True)
        version.show()

        text = _('Flumotion is a streaming media server.\n\n'
            '© 2004, 2005, 2006, 2007 Fluendo S.L.')
        authors = (
                   'Johan Dahlin',
                   'Arek Korbik',
                   'Zaheer Abbas Merali',
                   'Sébastien Merle',
                   'Mike Smith',
                   'Wim Taymans',
                   'Thomas Vander Stichele',
                   'Andy Wingo',
        )
        text += '\n\n<small>' + _('Authors') + ':\n'
        for author in authors:
            text += '  %s\n' % author
        text += '</small>'
        info = gtk.Label(text)
        self.vbox.pack_start(info)
        info.set_use_markup(True)
        info.set_selectable(True)
        info.set_justify(gtk.JUSTIFY_FILL)
        info.set_line_wrap(True)
        info.show()
