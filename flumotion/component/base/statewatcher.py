# -*- Mode: Python; test-case-name: flumotion.test.test_feedcomponent010 -*-
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

# this class is a bit of an experiment
# editor's note: "experiment" is an excuse for undocumented and uncommented


class StateWatcher(object):

    def __init__(self, state, setters, appenders, removers,
            setitemers=None, delitemers=None):
        self.state = state
        self.setters = setters
        self.appenders = appenders
        self.removers = removers
        self.setitemers = setitemers
        self.delitemers = delitemers
        self.shown = False

        state.addListener(self, set_=self.onSet, append=self.onAppend,
                          remove=self.onRemove, setitem=self.onSetItem,
                          delitem=self.onDelItem)

        for k in appenders:
            for v in state.get(k):
                self.onAppend(state, k, v)

    def hide(self):
        if self.shown:
            for k in self.setters:
                self.onSet(self.state, k, None)
            self.shown = False

    def show(self):
        # "show" the watcher by triggering all the registered setters
        if not self.shown:
            self.shown = True
            for k in self.setters:
                self.onSet(self.state, k, self.state.get(k))

    def onSet(self, obj, k, v):
        if self.shown and k in self.setters:
            self.setters[k](self.state, v)

    def onAppend(self, obj, k, v):
        if k in self.appenders:
            self.appenders[k](self.state, v)

    def onRemove(self, obj, k, v):
        if k in self.removers:
            self.removers[k](self.state, v)

    def onSetItem(self, obj, k, sk, v):
        if self.shown and k in self.setitemers:
            self.setitemers[k](self.state, sk, v)

    def onDelItem(self, obj, k, sk, v):
        if self.shown and k in self.setitemers:
            self.setitemers[k](self.state, sk, v)

    def unwatch(self):
        if self.state:
            self.hide()
            for k in self.removers:
                for v in self.state.get(k):
                    self.onRemove(self.state, k, v)
            self.state.removeListener(self)
            self.state = None
