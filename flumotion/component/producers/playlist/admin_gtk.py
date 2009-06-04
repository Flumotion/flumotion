# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2004,2005,2006,2007,2008 Fluendo, S.L. (www.fluendo.com).
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
import gettext
import gtk
import gst
from flumotion.component.base.admin_gtk import BaseAdminGtk
from flumotion.component.base.baseadminnode import BaseAdminGtkNode

_ = gettext.gettext
(
    COLUMN_TITLE,
    COLUMN_DURATION,
    COLUMN_OFFSET,
    COLUMN_AUDIO,
    COLUMN_VIDEO,
    COLUMN_LOCATION,
) = range(6)


def time_to_string(value):
    sec = value / gst.SECOND
    mins = sec / 60
    sec = sec % 60
    hours = mins / 60
    mins = mins % 60
    return "%02d:%02d:%02d" % (hours, mins, sec)


class PlaylistAdminGtkNode(BaseAdminGtkNode):
    gladeFile = os.path.join("flumotion", "component", "producers",
                             "playlist", "playlist.glade")
    _iters = {}

    def haveWidgetTree(self):

        def getUIState_cb(state):
            self._populate(state, "playlist", state.get("playlist"))

        self._buildPlaylist()
        self.widget = self.getWidget("main_vbox")
        d = self.callRemote("getUIState")
        d.addCallback(getUIState_cb)

    def _buildPlaylist(self):
        self.store = gtk.ListStore(str, str, str, str, str, str)
        self.tree = self.wtree.get_widget("treeview-playlist")
        self.tree.append_column(gtk.TreeViewColumn("Title",
                                                   gtk.CellRendererText(),
                                                   text=COLUMN_TITLE))
        self.tree.append_column(gtk.TreeViewColumn("Duration",
                                                   gtk.CellRendererText(),
                                                   text=COLUMN_DURATION))
        self.tree.append_column(gtk.TreeViewColumn("Offset",
                                                   gtk.CellRendererText(),
                                                   text=COLUMN_OFFSET))
        self.tree.append_column(gtk.TreeViewColumn("Audio",
                                                   gtk.CellRendererText(),
                                                   text=COLUMN_AUDIO))
        self.tree.append_column(gtk.TreeViewColumn("Video",
                                                   gtk.CellRendererText(),
                                                   text=COLUMN_VIDEO))
        self.tree.append_column(gtk.TreeViewColumn("Location",
                                                   gtk.CellRendererText(),
                                                   text=COLUMN_LOCATION))
        self.tree.set_model(self.store)

    def _append(self, item):
        # playlist item order:
        #     [timestamp, uri, duration, offset, hasAudio, hasVideo]
        self._iters[item[0]] = self.store.append([os.path.basename(item[1]),
                                                  str(time_to_string(item[2])),
                                                  str(time_to_string(item[3])),
                                                  str(item[4]),
                                                  str(item[5]),
                                                  str(item[1])])

    def _remove(self, item):
        iter = self._iters[item[0]]
        if iter:
            self.store.remove(iter)
            self._iters.pop(iter)

    def _populate(self, state, key, value):
        if key == "playlist":
            self.store.clear()
            for item in value:
                self._append(item)

    def stateAppend(self, state, key, value):
        if key == "playlist":
            self._append(value)

    def stateRemove(self, state, key, value):
        if key == "playlist":
            self._remove(value)


class PlaylistAdminGtk(BaseAdminGtk):

    def setup(self):
        statistics = PlaylistAdminGtkNode(self.state,
                                          self.admin,
                                          _("Playlist"))
        self.nodes['Playlist'] = statistics
        return BaseAdminGtk.setup(self)

GUIClass = PlaylistAdminGtk
