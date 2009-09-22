# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2008 Fluendo, S.L. (www.fluendo.com).
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

"""Ondemand Browser widget

The widget is in concept similar to the FileSelector but displaying full urls
for the files and adding a context menu for copying or opening the link.
"""

import gettext
import gtk
import urlparse
import os

from kiwi.ui.widgets.contextmenu import ContextMenu, ContextMenuItem
from flumotion.ui.fileselector import FileSelector
from flumotion.common.interfaces import IDirectory

__version__ = "$Rev$"
_ = gettext.gettext


class _FileUri(object):

    def __init__(self, fileInfo, icon):
        self.original = fileInfo
        self.filename = fileInfo.filename
        self.icon = icon

    def getPath(self):
        return self.original.getPath()


class OnDemandBrowser(FileSelector):

    def __init__(self, parent, adminModel):
        FileSelector.__init__(self, parent, adminModel)
        self._base_uri = None
        self._root = None
        self._popupmenu = self._create_popup_menu()
        self.set_context_menu(self._popupmenu)

    def setBaseUri(self, base_uri):
        self._base_uri = base_uri

    def setRoot(self, path):
        self._root = os.path.normpath(path)
        self.setDirectory(self._root)

    def _create_popup_menu(self):
        popupmenu = ContextMenu()
        item = ContextMenuItem('_Open Link', gtk.STOCK_JUMP_TO)
        item.connect('activate', self._on_open_link_activate)
        popupmenu.add(item)
        popupmenu.append_separator()
        item = ContextMenuItem('_Copy Link', gtk.STOCK_COPY)
        item.connect('activate', self._on_copy_link_activate)
        popupmenu.add(item)
        popupmenu.show_all()
        return popupmenu

    def _populateList(self, vfsFiles):
        self.clear()
        for vfsFile in vfsFiles:
            if not IDirectory.providedBy(vfsFile) and self._onlyDirectories:
                continue
            path = vfsFile.getPath()
            if path in self._root and path != self._root:
                continue
            icon = self._renderIcon(vfsFile.iconNames)
            rel_path = path.replace(self._root, '')
            if self._base_uri and vfsFile.filename != '..':
                vfsFile.filename = urlparse.urljoin(self._base_uri, rel_path)
            self.append(_FileUri(vfsFile, icon))

    def _on_open_link_activate(self, widget):
        # signal handler for open link menu item activation
        self.emit('selected', self.get_selected())

    def _on_copy_link_activate(self, widget):
        # signal handler for copy link menu item activation
        clipboard = gtk.Clipboard()
        clipboard.set_text(self.get_selected().filename)
