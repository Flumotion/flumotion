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

from flumotion.ui.kiwipatches import HIGAlertDialog

_ = gettext.gettext

# FIXME: Get colors from the Gtk+ theme or use tango colors
FILENAME_COLOR = 'gray20'
NAME_COLOR = '#000055'
EXCEPTION_COLOR = '#880000'


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
