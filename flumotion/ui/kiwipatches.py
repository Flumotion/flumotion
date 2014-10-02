# -*- Mode: Python -*-
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

import os

import glib
import atk
import gtk
import gettext
from gtk import glade


__version__ = "$Rev$"

_ = gettext.gettext

class FluLibgladeWidgetTree(glade.XML):

    def __init__(self, view, gladefile, toplevel_name, domain=None):
        self._view = view
        typeDict = getattr(view, 'gladeTypedict', {}) or {}
        glade.XML.__init__(self, gladefile, toplevel_name, domain,
                           typedict=typeDict)

        for widget in self.get_widget_prefix(''):
            setattr(self._view, widget.get_name(), widget)

    def get_widget(self, name):
        print("Just been asked for this widget: %s" % name)
        name = name.replace('.', '_')
        widget = glade.XML.get_widget(self, name)
        if widget is None:
            raise AttributeError(
                  "Widget %s not found in view %s" % (name, self._view))
        return widget

    def get_widgets(self):
        return self.get_widget_prefix('')

    def get_sizegroups(self):
        return []



# HIGAlertDialog, taken from KIWI: http://www.async.com.br/projects/kiwi/

_IMAGE_TYPES = {
    gtk.MESSAGE_INFO: gtk.STOCK_DIALOG_INFO,
    gtk.MESSAGE_WARNING: gtk.STOCK_DIALOG_WARNING,
    gtk.MESSAGE_QUESTION: gtk.STOCK_DIALOG_QUESTION,
    gtk.MESSAGE_ERROR: gtk.STOCK_DIALOG_ERROR,
}

_BUTTON_TYPES = {
    gtk.BUTTONS_NONE: (),
    gtk.BUTTONS_OK: (gtk.STOCK_OK, gtk.RESPONSE_OK,),
    gtk.BUTTONS_CLOSE: (gtk.STOCK_CLOSE, gtk.RESPONSE_CLOSE,),
    gtk.BUTTONS_CANCEL: (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,),
    gtk.BUTTONS_YES_NO: (gtk.STOCK_NO, gtk.RESPONSE_NO,
                         gtk.STOCK_YES, gtk.RESPONSE_YES),
    gtk.BUTTONS_OK_CANCEL: (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                            gtk.STOCK_OK, gtk.RESPONSE_OK)
}


class HIGAlertDialog(gtk.Dialog):
    def __init__(self, parent, flags,
                 type=gtk.MESSAGE_INFO, buttons=gtk.BUTTONS_NONE):
        if not type in _IMAGE_TYPES:
            raise TypeError(
                "type must be one of: %s", ', '.join(_IMAGE_TYPES.keys()))
        if not buttons in _BUTTON_TYPES:
            raise TypeError(
                "buttons be one of: %s", ', '.join(_BUTTON_TYPES.keys()))

        gtk.Dialog.__init__(self, '', parent, flags)
        self.set_deletable(False)
        self.set_border_width(5)
        self.set_resizable(False)
        # Some window managers (ION) displays a default title (???) if
        # the specified one is empty, workaround this by setting it
        # to a single space instead
        self.set_title(" ")
        self.set_skip_taskbar_hint(True)

        # It seems like get_accessible is not available on windows, go figure
        if hasattr(self, 'get_accessible'):
            self.get_accessible().set_role(atk.ROLE_ALERT)

        self._primary_label = gtk.Label()
        self._secondary_label = gtk.Label()
        self._details_label = gtk.Label()
        self._image = gtk.image_new_from_stock(_IMAGE_TYPES[type],
                                               gtk.ICON_SIZE_DIALOG)
        self._image.set_alignment(0.5, 0.0)

        self._primary_label.set_use_markup(True)
        for label in (self._primary_label, self._secondary_label,
                      self._details_label):
            label.set_line_wrap(True)
            label.set_selectable(True)
            label.set_alignment(0.0, 0.5)

        hbox = gtk.HBox(False, 12)
        hbox.set_border_width(5)
        hbox.pack_start(self._image, False, False)

        vbox = gtk.VBox(False, 0)
        hbox.pack_start(vbox, False, False)
        vbox.pack_start(self._primary_label, False, False)
        vbox.pack_start(self._secondary_label, False, False)
        self.main_vbox = vbox

        self._expander = gtk.expander_new_with_mnemonic(
            _("Show more _details"))
        self._expander.set_spacing(6)
        self._expander.add(self._details_label)
        vbox.pack_start(self._expander, False, False)
        self.get_content_area().pack_start(hbox, False, False)
        hbox.show_all()
        self._expander.hide()
        self.add_buttons(*_BUTTON_TYPES[buttons])
        self.label_vbox = vbox

    def set_primary(self, text, bold=True):
        if bold:
            text = "<span weight=\"bold\" size=\"larger\">%s</span>" % (
                glib.markup_escape_text(text))
        self._primary_label.set_markup(text)

    def set_secondary(self, text):
        self._secondary_label.set_markup(text)

    def set_details_label(self, label):
        self._expander.set_label(label)

    def set_details(self, text, use_markup=False):
        if use_markup:
            self._details_label.set_markup(glib.markup_escape_text(text))
        else:
            self._details_label.set_text(text)
        self._expander.show()

    def set_details_widget(self, widget):
        self._expander.remove(self._details_label)
        self._expander.add(widget)
        widget.show()
        self._expander.show()


# This code was adapted from the kiwi yesno helper dialog...simplified


def yesno(desc, parent=None, default=gtk.RESPONSE_YES,
          buttons=gtk.BUTTONS_YES_NO):

    if buttons in (gtk.BUTTONS_NONE, gtk.BUTTONS_OK, gtk.BUTTONS_CLOSE,
                       gtk.BUTTONS_CANCEL, gtk.BUTTONS_YES_NO,
                       gtk.BUTTONS_OK_CANCEL):
        dialog_buttons = buttons
        buttons = []
    else:
        if buttons is not None and type(buttons) != tuple:
            raise TypeError(
                "buttons must be a GtkButtonsTypes constant or a tuple")
        dialog_buttons = gtk.BUTTONS_NONE

    d = HIGAlertDialog(parent=parent, flags=gtk.DIALOG_MODAL,
                       type=gtk.MESSAGE_WARNING, buttons=dialog_buttons)
    if buttons:
        for text, response in buttons:
            d.add_buttons(text, response)
    d.set_primary(desc, bold=True)
    if default != -1:
        d.set_default_response(default)
    if parent:
        d.set_transient_for(parent)
        d.set_modal(True)
    response = d.run()
    d.destroy()
    return response
    
