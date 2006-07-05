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

from flumotion.common import messages
from flumotion.configure import configure

from gettext import gettext as _

import os
import gtk

_stock_icons = {messages.ERROR: gtk.STOCK_DIALOG_ERROR,
                messages.WARNING: gtk.STOCK_DIALOG_WARNING,
                messages.INFO: gtk.STOCK_DIALOG_INFO}

_headings = {messages.ERROR: _('Error'),
             messages.WARNING: _('Warning'),
             messages.INFO: _('Note')}

class MessageButton(gtk.ToggleButton):
    """
    I am a button at the top right of the message view, representing a message.
    """
    def __init__(self, message):
        gtk.ToggleButton.__init__(self)

        self.message = message

        i = gtk.Image()
        i.set_from_stock(_stock_icons.get(message.level,
                                          gtk.STOCK_MISSING_IMAGE),
                         gtk.ICON_SIZE_BUTTON)
        i.show()
        self.add(i)
        self.set_focus_on_click(False)
        self.set_relief(gtk.RELIEF_NONE)

    def __repr__(self):
        return '<MessageButton for %s at %d>' % (self.message, id(self))

# instantiated through create_function in glade files
class MessagesView(gtk.VBox):
    """
    I am a widget that can show messages.
    """
    # I am a vbox with first row the label and icons,
    # second row a separator
    # and third row a text view
    def __init__(self):
        gtk.VBox.__init__(self)

        h1 = gtk.HBox()
        self.pack_start(h1, False, False, 0)
        self.label = gtk.Label()
        self.label.show()
        h1.pack_start(self.label, False, False, 6)

        # button box holding the message icons at the top right
        h2 = gtk.HBox()
        h1.pack_end(h2, False, False, 0)
        s = gtk.HSeparator()
        self.pack_start(s, False, False, 6)
        sw = gtk.ScrolledWindow()
        sw.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
        sw.set_shadow_type(gtk.SHADOW_NONE)
        self.pack_start(sw, True, True, 0)

        # text view shows the messages, plus debug information
        # FIXME: needs to be hyperlinkable in the future
        tv = gtk.TextView()
        tv.set_wrap_mode(gtk.WRAP_WORD)
        tv.set_left_margin(6)
        tv.set_right_margin(6)
        tv.set_accepts_tab(False)
        tv.set_cursor_visible(False)
        tv.set_editable(False)
        #tv.set_sensitive(False)
        sw.add(tv)

        self.active_button = None
        self.buttonbox = h2
        self.textview = tv

        self.show_all()
        self.clear()

        self._translator = messages.Translator()
        localedir = os.path.join(configure.localedatadir, 'locale')
        # FIXME: add locales as messages from domains come in
        self._translator.addLocaleDir('flumotion', localedir)

    def clear(self):
        """
        Remove all messages and hide myself.
        """
        for i in self.buttonbox.get_children():
            self.clear_message(i.message.id)
        self.hide()

    def add_message(self, m):
        """
        Add a message to me.
        @type  m: L{flumotion.common.messages.Message}
        """
        def on_toggled(b):
            # on toggling the button, show the message
            if not b.get_active():
                if self.active_button == b:
                    b.set_active(True)
                return
            old_active = self.active_button
            self.active_button = b
            if old_active and old_active != b:
                old_active.set_active(False)
            buf = gtk.TextBuffer()
            # FIXME: it would be good to have a "Debug" button when
            # applicable, instead of always showing the text
            text = self._translator.translate(m)
            if m.debug:
                text += "\n\n" + _("Debug information:\n") + m.debug
            buf.set_text(text)
            self.textview.set_buffer(buf)
            self.label.set_markup('<b>%s</b>'
                                  % _headings.get(m.level, _('Message')))

        # FIXME:this clears all messages with the same id as the new one.
        # effectively replacing.  Is this what we want ?
        self.clear_message(m.id)

        # add a message button to show this message
        b = MessageButton(m)
        b.sigid = b.connect('toggled', on_toggled)
        b.show()
        self.buttonbox.pack_start(b, False, False, 0)

        # Sort all messages first by (reverse of) level, then priority
        kids = [(-w.message.level, w.message.priority, w) for w in self.buttonbox.get_children()]
        kids.sort()
        kids.reverse()
        kids = [(i, kids[i][2]) for i in range(len(kids))]
        for x in kids:
            self.buttonbox.reorder_child(x[1], x[0])

        if not self.active_button:
            b.set_active(True)
        elif b == kids[0][1]: # the first button, e.g. highest priority
            b.set_active(True)
        self.show()

    def clear_message(self, id):
        """
        Clear all messages with the given id.
        Will bring the remaining most important message to the front,
        or hide the view completely if no messages are left.
        """
        for b in self.buttonbox.get_children():
            if b.message.id == id:
                self.buttonbox.remove(b)
                b.disconnect(b.sigid)
                b.sigid = 0
                if not self.buttonbox.get_children():
                    self.active_button = None
                    self.hide()
                elif self.active_button == b:
                    self.active_button = self.buttonbox.get_children()[0]
                    self.active_button.set_active(True)
                return
