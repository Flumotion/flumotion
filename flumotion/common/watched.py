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


def _make_watched(type, *mutators):

    class Watched(type):

        def __init__(self):
            type.__init__(self)
            self.watch_id = 0
            self.watch_procs = {} # id -> proc

        def watch(self, proc):
            self.watch_id += 1
            self.watch_procs[self.watch_id] = proc
            return self.watch_id

        def unwatch(self, id):
            del self.watch_procs[id]

        def notify_changed(self):
            for proc in self.watch_procs.values():
                proc(self)

    def mutate(method):

        def do_mutate(self, *args, **kwargs):
            method(self, *args, **kwargs)
            self.notify_changed()
        setattr(Watched, method.__name__, do_mutate)
    for i in mutators:
        mutate(getattr(type, i))

    return Watched

WatchedList = _make_watched(list, 'append', 'insert', 'remove', 'pop',
                            'sort', 'reverse')
WatchedDict = _make_watched(dict, '__setitem__', '__delitem__', 'pop',
                            'popitem', 'update')
