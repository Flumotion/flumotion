# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2004,2005 Fluendo, S.L. (www.fluendo.com). All rights reserved.

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


import gtk


ERROR = 1
WARNING = 2
INFO = 3

_stock_icons = {ERROR: gtk.STOCK_DIALOG_ERROR,
                WARNING: gtk.STOCK_DIALOG_WARNING,
                INFO: gtk.STOCK_DIALOG_INFO}

_headings = {ERROR: 'Error',
             WARNING: 'Warning',
             INFO: 'Note'}

class Message:
    def __init__(self, level=WARNING, priority=50, id=None, msg=None,
                 details=None):
        self.level = level
        self.id = id
        self.sigid = 0
        self.priority = priority
        self.msg = msg
        self.details = details

    def __repr__(self):
        return '<Message %s at %d>' % (self.id, id(self))

class MessageButton(gtk.ToggleButton):
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

class MessageView(gtk.VBox):
    def __init__(self):
        gtk.VBox.__init__(self)

        h1 = gtk.HBox()
        self.pack_start(h1, False, False, 0)
        self.label = gtk.Label()
        self.label.show()
        h1.pack_start(self.label, False, False, 12)
        h2 = gtk.HBox()
        h1.pack_end(h2, False, False, 12)
        s = gtk.HSeparator()
        self.pack_start(s, False, False, 3)
        sw = gtk.ScrolledWindow()
        sw.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
        sw.set_shadow_type(gtk.SHADOW_NONE)
        self.pack_start(sw, True, True, 0)
        tv = gtk.TextView()
        tv.set_left_margin(12)
        tv.set_right_margin(12)
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

    def clear(self):
        for i in self.buttonbox.get_children():
            self.clear_message(i.message.id)
        self.hide()

    def add_message(self, m):
        def on_toggled(b):
            if not b.get_active():
                if self.active_button == b:
                    b.set_active(True)
                return
            old_active = self.active_button
            self.active_button = b
            if old_active and old_active != b:
                old_active.set_active(False)
            buf = gtk.TextBuffer()
            buf.set_text(b.message.msg)
            self.textview.set_buffer(buf)
            self.label.set_markup('<b>%s</b>'
                                  % _headings.get(m.level, 'Message'))

        self.clear_message(m.id)

        b = MessageButton(m)
        b.sigid = b.connect('toggled', on_toggled)
        b.show()
        self.buttonbox.pack_start(b, False, False, 0)

        kids = [(w.message.priority, w) for w in self.buttonbox.get_children()]
        kids.sort(reverse=True)
        kids = [(i, kids[i][1]) for i in range(len(kids))]
        for x in kids:
            self.buttonbox.reorder_child(x[1], x[0])

        if not self.active_button:
            b.set_active(True)
        elif b == kids[0][1]: # the first button, e.g. highest priority
            b.set_active(True)
        self.show()

    def clear_message(self, id):
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
