# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4

# Flumotion - a video streaming server
# Copyright (C) 2004 Fluendo
#
# admin/gtk/progressdialog.py: a pulsating progress dialog
# 
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Street #330, Boston, MA 02111-1307, USA.

import gtk
import gobject

class ProgressDialog(gtk.Dialog):
    def __init__(self, title, message, parent = None):
        gtk.Dialog.__init__(self, title, parent,
                            gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT)

                                                                               
        box = gtk.VBox()
        self.action_area.add(box)
        self.label = gtk.Label(message)
        box.add(self.label)
        self.bar = gtk.ProgressBar()
        box.add(self.bar)
        self.active = False

    def start(self):
        "Show the dialog and start pulsating."
        self.active = True
        self.show_all()
        self.bar.pulse()
        self.timeout_cb = gobject.timeout_add(200, self._pulse)

    def stop(self):
        "Remove the dialog and stop pulsating."
        self.active = False

    def message(self, message):
        "Set the message on the dialog."
        self.label.set_text(message)

    def _pulse(self):
        if not self.active:
            # we were disabled, so stop pulsating
            return False
        self.bar.pulse()
        return True

if __name__ == '__main__':
    window = gtk.Window()
    dialog = ProgressDialog("I am busy", 'Doing lots of complicated stuff', window)
    dialog.start()

    def stop(dialog):
        dialog.stop()
        gtk.main_quit()
        
    gobject.timeout_add(1000, lambda dialog: dialog.message('Step 1'), dialog)
    gobject.timeout_add(2000, lambda dialog: dialog.message('Step 2'), dialog)
    gobject.timeout_add(4000, stop, dialog)
    gtk.main()
