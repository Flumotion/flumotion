# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# flumotion/component/producers/videotest/admin_gtk.py
# admin client-side code for videotest
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

import os
import gtk

from flumotion.common import errors

from flumotion.component.base.admin_gtk import BaseAdminGtk, BaseAdminGtkNode

class FilenameNode(BaseAdminGtkNode):
    def render(self):
        gladeFile = os.path.join('flumotion', 'component', 'consumers',
            'disker', 'disker.glade')
        d = self.loadGladeFile(gladeFile)
        d.addCallback(self._loadGladeFileCallback)
        return d

    def _loadGladeFileCallback(self, widgetTree):
        self.wtree = widgetTree
        self.labels = {}
        self.filenameWidget = self.wtree.get_widget('filename-widget')
        self.currentFilenameLabel = self.wtree.get_widget('label-current')
        button = self.wtree.get_widget('button-new')
        button.connect('clicked',self.cb_button_clicked)

        self.callRemote('notifyState')
        self.shown = False
        return self.filenameWidget

    def cb_button_clicked(self, button):
        d = self.callRemote("changeFilename")
        d.addErrback(self.changeFilenameErrback)

    def changeFilenameErrback(self,failure):
        self.warning("Failure %s changing filename: %s" % (failure.type, failure.getErrorMessage()))
        return None

    def filenameChanged(self, filename):
        self.currentFilenameLabel.set_text(filename)
    
    



class DiskerAdminGtk(BaseAdminGtk):
    def setup(self):
        filename = FilenameNode(self.name, self.admin, self.view)
        self._nodes = {'Filename' : filename}

    def getNodes(self):
        return self._nodes

    def component_filenameChanged(self, filename):
        self._nodes['Filename'].filenameChanged(filename)

GUIClass = DiskerAdminGtk
