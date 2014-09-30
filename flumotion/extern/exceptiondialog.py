# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4

# Copyright (C) 2005,2006,2007 by Async Open Source and Sicem S.L.
# Copyright (C) 2008,2009 Fluendo, S.L.
# Copyright (C) 2010,2011 Flumotion Services, S.A.
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU Lesser General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA 02111-1307, USA.

# Contains portions originally written by Lorenzo Gil Sanchez and Johan Dahlin

# Headers in this file shall remain intact.

import gettext
import linecache
import os
import sys
import traceback

import pango
import gtk
import glib
import atk

_ = gettext.gettext

# FIXME: Get colors from the Gtk+ theme or use tango colors
FILENAME_COLOR = 'gray20'
NAME_COLOR = '#000055'
EXCEPTION_COLOR = '#880000'

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


class TracebackViewer(gtk.ScrolledWindow):

    def __init__(self, excTuple):
        exctype, value, tb = excTuple
        self._exctype = exctype
        self._tb = tb
        self._value = value

        gtk.ScrolledWindow.__init__(self)
        self.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        self.set_shadow_type(gtk.SHADOW_ETCHED_IN)
        self._createUI()
        self._showException()

    def _createUI(self):
        self._buffer = gtk.TextBuffer()
        self._buffer.create_tag('filename', style=pango.STYLE_ITALIC,
                                foreground=FILENAME_COLOR)
        self._buffer.create_tag('name', foreground=NAME_COLOR)
        self._buffer.create_tag('lineno', weight=pango.WEIGHT_BOLD)
        self._buffer.create_tag('exc', foreground=EXCEPTION_COLOR,
                                weight=pango.WEIGHT_BOLD)

        textView = gtk.TextView(self._buffer)
        self.add(textView)
        textView.show()

    def _print(self, line):
        self._buffer.insert_at_cursor(line + '\n')

    def _printFile(self, filename, lineno, name):
        self._insertText('  File ')
        self._insertText(filename, 'filename')
        self._insertText(', line ')
        self._insertText(str(lineno), 'lineno')
        self._insertText(', in ')
        self._insertText(name, 'name')
        self._insertText('\n')

    def _insertText(self, text, tagName=None):
        end_iter = self._buffer.get_end_iter()
        if tagName:
            self._buffer.insert_with_tags_by_name(end_iter, text, tagName)
        else:
            self._buffer.insert(end_iter, text)

    def _printTraceback(self):
        """Print up to 'limit' stack trace entries from the traceback 'tb'.

        If 'limit' is omitted or None, all entries are printed.  If 'file'
        is omitted or None, the output goes to sys.stderr; otherwise
        'file' should be an open file or file-like object with a write()
        method.
        """

        for tb in self._getTracebacks():
            co = tb.tb_frame.f_code
            self._printFile(co.co_filename, tb.tb_lineno, co.co_name)
            line = linecache.getline(co.co_filename, tb.tb_lineno)
            if line:
                self._print('    ' + line.strip())

    def _showException(self):
        widget = gtk.grab_get_current()
        if widget is not None:
            widget.grab_remove()

        self._printTraceback()
        msg = traceback.format_exception_only(self._exctype, self._value)[0]
        result = msg.split(' ', 1)
        if len(result) == 1:
            msg = result[0]
            arguments = ''
        else:
            msg, arguments = result
        self._insertText(msg, 'exc')
        self._insertText(' ' + arguments)

        # scroll to end
        vadj = self.get_vadjustment()
        vadj.set_value(vadj.upper)

    def _getTracebacks(self, limit=None):
        if limit is None:
            limit = getattr(sys, 'tracebacklimit', None)

        n = 0
        tb = self._tb
        while tb is not None:
            if limit is not None and n >= limit:
                break
            n += 1

            yield tb
            tb = tb.tb_next

    # Public API

    def getSummary(self):
        lastFilename = list(self.getFilenames())[-1]
        filename = os.path.basename(lastFilename)
        text = self.getDescription()
        for lastline in text.split('\n')[::-1]:
            if lastline != '':
                break
        return '%s:%d %s' % (filename, self._tb.tb_lineno, lastline)

    def getDescription(self):
        return self._buffer.get_text(*self._buffer.get_bounds())

    def getFilenames(self):
        cwd = os.getcwd()
        for tb in self._getTracebacks():
            filename = tb.tb_frame.f_code.co_filename
            if filename.startswith(cwd):
                filename = filename.replace(cwd, '')[1:]
            yield filename


class ExceptionDialog(HIGAlertDialog):
    """I am a dialog that can display a python exception
    and code to report a bug.
    """
    RESPONSE_BUG = 1

    def __init__(self, excTuple):
        """
        @param excTuple:
        @type excTuple:
        """
        toplevels = gtk.window_list_toplevels()
        if toplevels:
            # FIXME: how do we find the topmost one?
            parent = toplevels[0]
        else:
            parent = None
        HIGAlertDialog.__init__(self,
                                parent=parent,
                                flags=gtk.DIALOG_MODAL,
                                type=gtk.MESSAGE_ERROR,
                                buttons=gtk.BUTTONS_NONE)
        self.set_primary(_("A programming error occurred."))
        self.add_button(_("Report a bug"), ExceptionDialog.RESPONSE_BUG)
        self.add_button(gtk.STOCK_CLOSE, gtk.RESPONSE_CLOSE)
        self.set_default_response(gtk.RESPONSE_CLOSE)

        self._dw = self._createTracebackViewer(excTuple)
        self.set_details_widget(self._dw)

        # FIXME: Add a kiwi API to set the detail label
        expander = self._dw.get_parent()
        expander.set_label(_("Show debug information"))

    def _createTracebackViewer(self, excTuple):
        dw = TracebackViewer(excTuple)
        # How can we make it resize itself sanely depending on the number
        # of lines it has
        dw.set_size_request(500, 200)
        dw.show()
        return dw

    def getSummary(self):
        return self._dw.getSummary()

    def getDescription(self):
        return self._dw.getDescription()

    def getFilenames(self):
        return self._dw.getFilenames()
