# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# flumotion/admin/gtk/progressdialog.py: a pulsating progress dialog
# 
# Flumotion - a streaming media server
# Copyright (C) 2004 Fluendo (www.fluendo.com)

# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
# See "LICENSE.GPL" in the source distribution for more information.

# This program is also licensed under the Flumotion license.
# See "LICENSE.Flumotion" in the source distribution for more information.

import gtk
import gobject

class ProgressDialog(gtk.Dialog):
    def __init__(self, title, message, parent = None):
        gtk.Dialog.__init__(self, title, parent,
                            gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT)

                                                                               
        self.label = gtk.Label(message)
        self.vbox.pack_start(self.label, True, True)
        self.bar = gtk.ProgressBar()
        self.vbox.pack_end(self.bar, True, True)
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

def test():
    window = gtk.Window()
    dialog = ProgressDialog("I am busy", 'Doing lots of complicated stuff', window)
    dialog.start()

    def stop(dialog):
        dialog.stop()
        gtk.main_quit()
        
    gobject.timeout_add(1000, lambda dialog: dialog.message('Step 1'), dialog)
    gobject.timeout_add(2000, lambda dialog: dialog.message('Step 2 but with a lot longer text so we test shrinking'), dialog)
    gobject.timeout_add(3000, lambda dialog: dialog.message('Step 3'), dialog)
    gobject.timeout_add(5000, stop, dialog)
    gtk.main()

if __name__ == '__main__':
    test()
