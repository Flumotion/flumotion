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

import os
import gtk

from flumotion.common import errors

from flumotion.component.base.admin_gtk import BaseAdminGtk
from flumotion.component.base.baseadminnode import BaseAdminGtkNode

__version__ = "$Rev$"


class FilenameNode(BaseAdminGtkNode):
    gladeFile = os.path.join('flumotion', 'component', 'consumers',
                              'disker', 'disker.glade')

    currentFilenameLabel = None
    currentFilenamePendingText = None
    stopbutton = None
    hasIcal = False

    def haveWidgetTree(self):
        self.labels = {}
        self.widget = self.wtree.get_widget('filename-widget')
        self.currentFilenameLabel = self.wtree.get_widget('label-current')
        if self.currentFilenamePendingText:
            self.currentFilenameLabel.set_text(self.currentFilenamePendingText)
        newbutton = self.wtree.get_widget('button-new')
        newbutton.connect('clicked', self.cb_changefile_button_clicked)
        self.stopbutton = self.wtree.get_widget('button-stop')
        self.stopbutton.connect('clicked', self.cb_stop_button_clicked)
        if self.hasIcal:
            self.addScheduleWidget()

    def cb_changefile_button_clicked(self, button):
        d = self.callRemote("changeFilename")
        d.addErrback(self.changeFilenameErrback)

    def changeFilenameErrback(self, failure):
        self.warning("Failure %s changing filename: %s" % (
            failure.type, failure.getErrorMessage()))
        return None

    def cb_stop_button_clicked(self, button):
        d = self.callRemote("stopRecording")
        d.addErrback(self.stopRecordingErrback)

    def stopRecordingErrback(self, failure):
        self.warning("Failure %s stopping recording: %s" % (
            failure.type, failure.getErrorMessage()))
        return None

    def setUIState(self, state):
        BaseAdminGtkNode.setUIState(self, state)
        self.stateSet(state, 'filename', state.get('filename'))
        self.stateSet(state, 'recording', state.get('recording'))
        self.stateSet(state, 'can-schedule', state.get('can-schedule'))

    def stateSet(self, state, key, value):
        if key == 'filename':
            if self.currentFilenameLabel:
                self.currentFilenameLabel.set_text(value or '<waiting>')
            else:
                self.currentFilenamePendingText = value
        if key == 'recording':
            if not value:
                if self.currentFilenameLabel:
                    self.currentFilenameLabel.set_text('None')
                else:
                    self.currentFilenamePendingText = "None"
            if self.stopbutton:
                self.stopbutton.set_sensitive(value)
        if key == 'can-schedule' and value:
            self.hasIcal = True
            if self.widget:
                self.addScheduleWidget()

    def addScheduleWidget(self):
        self.filechooser = gtk.FileChooserButton("Upload a schedule")
        self.filechooser.set_local_only(True)
        self.filechooser.set_action(gtk.FILE_CHOOSER_ACTION_OPEN)
        filefilter = gtk.FileFilter()
        filefilter.add_pattern("*.ics")
        filefilter.set_name("vCalendar files")
        self.filechooser.add_filter(filefilter)
        self.filechooser.show()
        scheduleButton = gtk.Button("Schedule recordings")
        scheduleButton.show()
        scheduleButton.connect("clicked", self.cb_schedule_recordings)
        self.widget.attach(scheduleButton, 0, 1, 1, 2,
            xoptions=0, yoptions=0, xpadding=6, ypadding=6)
        self.widget.attach(self.filechooser, 1, 2, 1, 2,
            xoptions = gtk.EXPAND|gtk.FILL, yoptions=0, xpadding=6, ypadding=6)

    def cb_schedule_recordings(self, widget):
        filename = self.filechooser.get_filename()
        self.debug("filename is %r, uri %r, %r", filename,
                   self.filechooser.get_uri(), self.filechooser)
        if filename:
            icsStr = open(filename, "rb").read()
            d = self.callRemote("scheduleRecordings", icsStr)
            d.addErrback(self.scheduleRecordingsErrback)
        else:
            self.warning("No filename selected")

    def scheduleRecordingsErrback(self, failure):
        self.warning("Failure %s scheduling recordings: %s" % (
            failure.type, failure.getErrorMessage()))
        return None


class DiskerAdminGtk(BaseAdminGtk):

    def setup(self):
        filename = FilenameNode(self.state, self.admin, "Filename")
        self.nodes['Filename'] = filename
        return BaseAdminGtk.setup(self)

GUIClass = DiskerAdminGtk
