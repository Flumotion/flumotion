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

from gettext import gettext as _

import os
import gst
from flumotion.common import errors

from flumotion.component.base.admin_gtk import BaseAdminGtk, BaseAdminGtkNode
from twisted.internet import defer

from flumotion.ui.glade import GladeWidget

def time_to_string(value):
    sec = value / gst.SECOND
    mins = sec / 60
    sec = sec % 60
    hours = mins / 60
    mins = mins % 60
    return "%02d:%02d:%02d" % (hours, mins, sec)
    

class FileInfo(GladeWidget):
    glade_file = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              'flufileinfo.glade')
    duration = 0

    def set_information(self, information):
        """Set the file information"""
        self.locationlabel.set_text(information["location"])
        self.duration = information["duration"]
        self.timelabel.set_text(time_to_string(self.duration))
        if information.has_key("audio"):
            self.audiolabel.set_text(information["audio"])
        else:
            self.audiolabel.set_text("<i>No audio</i>")
        if information.has_key("video"):
            self.videolabel.set_text(information["video"])
        else:
            self.videolabel.set_text("<i>No video</i>")

class LooperNode(BaseAdminGtkNode):
    logCategory = 'looper'
    
    def render(self):
        self.debug('rendering looper UI')
        gladeFile = os.path.join('flumotion', 'component',
                                 'producers', 'looper',
                                 'looper.glade')
        d = self.loadGladeFile(gladeFile)
        d.addCallback(self._loadGladeFileCallback)
        return d

    def _loadGladeFileCallback(self, widgetTree):
        self.wtree = widgetTree
        self.widget = self.wtree.get_widget('looper-widget')
        self.fileinfowidget = self.wtree.get_widget('fileinfowidget')
        self.numiterlabel = self.wtree.get_widget('iterationslabel')
        self.curposlabel = self.wtree.get_widget('curposlabel')
        self.positionbar = self.wtree.get_widget('positionbar')
        self.restartbutton = self.wtree.get_widget('restartbutton')
        self.restartbutton.set_sensitive(False)
        
        d = self.callRemote("getNbIterations")
        d.addCallback(self.numberIterationsChanged)

        d = self.callRemote("getFileInformation")
        d.addCallback(self.haveFileInformation)
        
        return defer.succeed(self.widget)

    def _restart_callback(self, result):
        pass

    def _restart_failed(self, failure):
        self.warning("Failure %s getting pattern: %s" % (
            failure.type, failure.getErrorMessage()))
        return None

    def _reset_button_clicked(self, button):
        d = self.callRemote("gimme5", "ooooh yeah")
        d.addCallback(self._restart_callback)
        d.addErrback(self._restart_failed)

    def haveFileInformation(self, fileinformation):
        self.debug("got new information : %s" % fileinformation)
        if fileinformation:
            self.fileinfowidget.set_information(fileinformation)
        
    def haveUpdatedPosition(self, newposition):
        self.log("got new position : %d" % newposition)
        if self.fileinfowidget.duration:
            percent = float(newposition % self.fileinfowidget.duration) / float(self.fileinfowidget.duration)
            self.positionbar.set_fraction(percent)
            self.positionbar.set_text(time_to_string(newposition % self.fileinfowidget.duration))

    def numberIterationsChanged(self, nbiterations):
        self.numiterlabel.set_text(str(nbiterations))

class LooperAdminGtk(BaseAdminGtk):
    def setup(self):
        looper = LooperNode(self.state, self.admin, title=_("Looper"))
        self.nodes['Looper'] = looper

    def component_propertyChanged(self, name, value):
        self.nodes['Looper'].propertyChanged(name, value)

    def component_haveFileInformation(self, information):
        if information:
            self.nodes['Looper'].haveFileInformation(information)

    def component_numberIterationsChanged(self, nbiterations):
        self.nodes['Looper'].numberIterationsChanged(nbiterations)

    def component_haveUpdatedPosition(self, newposition):
        self.nodes['Looper'].haveUpdatedPosition(newposition)

GUIClass = LooperAdminGtk
