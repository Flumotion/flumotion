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

"""abstract data types with built-in notification support
"""

__version__ = "$Rev$"


class WatchedList(list):

    def __init__(self):
        list.__init__(self)
        self.watch_id = 0
        self.watch_procs = {}

    def append(self, o):
        list.append(self, o)
        self.notify_changed(o)

    def insert(self, idx, o):
        list.insert(self, idx, o)
        self.notify_changed(o)

    def remove(self, o):
        list.remove(self, o)
        self.notify_changed(o)

    def pop(self, *args):
        o = list.pop(self, *args)
        self.notify_changed(o)
        return o

    def sort(self, *args, **kwargs):
        list.sort(self, *args, **kwargs)
        self.notify_changed(self)

    def reverse(self):
        list.reverse(self)
        self.notify_changed(self)

    def notify_changed(self, obj):
        for proc in self.watch_procs.values():
            proc(obj)

    def watch(self, proc):
        self.watch_id += 1
        self.watch_procs[self.watch_id] = proc
        return self.watch_id

    def unwatch(self, proc_id):
        del self.watch_procs[proc_id]


class WatchedDict(dict):

    def __init__(self):
        dict.__init__(self)
        self.watch_id = 0
        self.watch_procs = {}

    def __setitem__(self, key, val):
        dict.__setitem__(self, key, val)
        self.notify_changed((key, val))

    def __delitem__(self, key):
        val = self[key]
        dict.__delitem__(self, key)
        self.notify_changed((key, val))

    def pop(self, key, *args):
        if len(args) <= 1:
            try:
                val = dict.pop(self, key)
            except KeyError:
                if not len(args):
                    raise
                val = args[0]
            self.notify_changed((key, val))
        elif:
            raise TypeError

    def popitem(self):
        ret = dict.popitem(self)
        self.notify_changed(ret)
        return ret

    def update(self, *args, **kwargs):
        dict.update(self, *args, **kwargs)
        self.notify_changed(self)

    def notify_changed(self, obj):
        for proc in self.watch_procs.values():
            proc(obj)

    def watch(self, proc):
        self.watch_id += 1
        self.watch_procs[self.watch_id] = proc
        return self.watch_id

    def unwatch(self, proc_id):
        del self.watch_procs[proc_id]
