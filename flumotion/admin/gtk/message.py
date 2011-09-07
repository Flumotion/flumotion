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

"""a view display messages containing warnings, errors and information."""

import gettext
import os
import time

import pango
import gtk

from flumotion.common import log
from flumotion.common.documentation import getMessageWebLink
from flumotion.common.i18n import Translator
from flumotion.common.messages import ERROR, WARNING, INFO
from flumotion.configure import configure
from flumotion.common.pygobject import gsignal

_ = gettext.gettext
__version__ = "$Rev$"
_stock_icons = {
    ERROR: gtk.STOCK_DIALOG_ERROR,
    WARNING: gtk.STOCK_DIALOG_WARNING,
    INFO: gtk.STOCK_DIALOG_INFO,
    }
_headings = {
    ERROR: _('Error'),
    WARNING: _('Warning'),
    INFO: _('Note'),
    }


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
                         gtk.ICON_SIZE_MENU)
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
    gsignal('resize-event', bool)

    def __init__(self):
        gtk.VBox.__init__(self)

        self._disableTimestamps = False
        self.active_button = None

        self._createUI()
        self.clear()

        self._translator = Translator()
        localedir = os.path.join(configure.localedatadir, 'locale')
        # FIXME: add locales as messages from domains come in
        self._translator.addLocaleDir(configure.PACKAGE, localedir)

    def _createUI(self):
        h1 = gtk.HBox()
        self.pack_start(h1, False, False, 0)

        self.hline = gtk.HSeparator()
        h1.pack_start(self.hline, True, True, 3)
        # button box holding the message icons at the top right
        h2 = gtk.HBox()
        h1.pack_end(h2, False, False, 0)
        self.buttonbox = h2

        sw = gtk.ScrolledWindow()
        sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        sw.set_shadow_type(gtk.SHADOW_ETCHED_IN)
        self.pack_start(sw, True, True, 0)
        self.sw = sw

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
        # connect signals to act on the hyperlink
        tv.connect('event-after', self._after_textview__event)
        tv.connect('motion-notify-event',
                   self._on_textview___motion_notify_event)
        sw.add(tv)
        self.textview = tv

        self.show_all()

    def clear(self):
        """
        Remove all messages and hide myself.
        """
        for child in self.buttonbox.get_children():
            self.clearMessage(child.message.id)
        self.hide()

    def addMessage(self, m):
        """
        Add a message to me.
        @type  m: L{flumotion.common.messages.Message}
        """
        # clear all previously added messages with the same id.  This allows
        # us to replace for example a "probing" message with the
        # result message
        self.clearMessage(m.id)

        # add a message button to show this message
        b = MessageButton(m)
        b.sigid = b.connect('toggled', self._on_message_button__toggled, m)
        b.show()
        self.buttonbox.pack_start(b, False, False, 0)

        firstButton = self._sortMessages()

        self.show()
        if not self.active_button:
            b.set_active(True)
        elif b == firstButton:
            b.set_active(True)

    def clearMessage(self, id):
        """
        Clear all messages with the given id.
        Will bring the remaining most important message to the front,
        or hide the view completely if no messages are left.
        """
        for button in self.buttonbox.get_children():
            if button.message.id != id:
                continue

            self.buttonbox.remove(button)
            button.disconnect(button.sigid)
            button.sigid = 0
            if not self.buttonbox.get_children():
                self.active_button = None
                self.hide()
            elif self.active_button == button:
                self.active_button = self.buttonbox.get_children()[0]
                self.active_button.set_active(True)
            break

    def disableTimestamps(self):
        """Disable timestamps for this MessageView,
        it will make it easier to understand the error messages and
        make it suitable for end users.
        """
        self._disableTimestamps = True

    # Private

    def _addMessageToBuffer(self, message):
        # FIXME: it would be good to have a "Debug" button when
        # applicable, instead of always showing the text
        text = self._translator.translate(message)

        textbuffer = gtk.TextBuffer()
        textbuffer.set_text(text)
        self.textview.set_buffer(textbuffer)

        # if we have help information, add it to the end of the text view
        description = message.getDescription()
        if description:
            textbuffer.insert(textbuffer.get_end_iter(), ' ')
            titer = textbuffer.get_end_iter()
            # we set the 'link' data field on tags to identify them
            translated = self._translator.translateTranslatable(description)
            tag = textbuffer.create_tag(translated)
            tag.set_property('underline', pango.UNDERLINE_SINGLE)
            tag.set_property('foreground', 'blue')
            tag.set_data('link', getMessageWebLink(message))
            textbuffer.insert_with_tags_by_name(titer, translated,
                                                tag.get_property('name'))

        timestamp = message.getTimeStamp()
        if timestamp and not self._disableTimestamps:
            text = _("\nPosted on %s.\n") % time.strftime(
                "%c", time.localtime(timestamp))
            textbuffer.insert(textbuffer.get_end_iter(), text)

        if message.debug:
            text = "\n\n" + _("Debug information:\n") + message.debug + '\n'
            textbuffer.insert(textbuffer.get_end_iter(), text)

    def _sortMessages(self):
        # Sort all messages first by (reverse of) level, then priority
        children = [(-w.message.level, w.message.priority, w)
                    for w in self.buttonbox.get_children()]
        children.sort()
        children.reverse()
        children = [(i, children[i][2]) for i in range(len(children))]
        for child in children:
            self.buttonbox.reorder_child(child[1], child[0])

        # the first button, e.g. highest priority
        return children[0][1]

    # Callbacks

    def _on_message_button__toggled(self, button, message):
        # on toggling the button, show the message
        if not button.get_active():
            if self.active_button == button:
                self.sw.hide()
                self.hline.hide()
                button.set_active(False)
                self.active_button = None
                self.emit('resize-event', True)
            return
        old_active = self.active_button
        self.active_button = button
        if old_active and old_active != button:
            old_active.set_active(False)

        self._addMessageToBuffer(message)
        self.show_all()
        self.emit('resize-event', False)

    # when the mouse cursor moves, set the cursor image accordingly

    def _on_textview___motion_notify_event(self, textview, event):
        x, y = textview.window_to_buffer_coords(gtk.TEXT_WINDOW_WIDGET,
            int(event.x), int(event.y))
        tags = textview.get_iter_at_location(x, y).get_tags()
        # without this call, further motion notify events don't get
        # triggered
        textview.window.get_pointer()

        # if any of the tags is a link, show a hand
        cursor = None
        for tag in tags:
            if tag.get_data('link'):
                cursor = gtk.gdk.Cursor(gtk.gdk.HAND2)
                break
        textview.get_window(gtk.TEXT_WINDOW_TEXT).set_cursor(cursor)
        return False

    def _after_textview__event(self, textview, event):
        if event.type != gtk.gdk.BUTTON_RELEASE:
            return False
        if event.button != 1:
            return False

        textbuffer = textview.get_buffer()
        # we shouldn't follow a link if the user has selected something
        bounds = textbuffer.get_selection_bounds()
        if bounds:
            [start, end] = bounds
            if start.get_offset() != end.get_offset():
                return False

        x, y = textview.window_to_buffer_coords(gtk.TEXT_WINDOW_WIDGET,
            int(event.x), int(event.y))
        iter = textview.get_iter_at_location(x, y)

        for tag in iter.get_tags():
            link = tag.get_data('link')
            if link:
                import webbrowser
                log.debug('messageview', 'opening %s' % link)
                webbrowser.open(link)
                break

        return False
