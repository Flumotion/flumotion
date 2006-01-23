# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2004,2005,2006 Fluendo, S.L. (www.fluendo.com).
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


class WalkableStack:
    def __init__(self):
        self.l = []
        self.height = -1
        self.pos = -1

    def __repr__(self):
        return '<stack %r>' % self.l

    def __len__(self):
        return len(self.l)

    def height(self):
        return len(self) - 1

    def push(self, x):
        if self.pos == self.height:
            self.height += 1
            self.pos += 1
            self.l.append(x)
            return True
        elif x == self.l[self.pos + 1]:
            self.pos += 1
            return True
        else:
            return False

    def current(self):
        return self.l[self.pos]

    def skip_to(self, key):
        for i in range(0, len(self.l)):
            if key(self.l[i]):
                self.pos = i
                return
        raise AssertionError()

    def back(self):
        assert self.pos > 0
        self.pos -= 1
        return self.l[self.pos]

    def pop(self):
        self.height -= 1
        if self.height < self.pos:
            self.pos = self.height
        return self.l.pop()
    

class KeyedList(list):
    def __init__(self, *args):
        list.__init__(self, *args)
        self.mappers = {} # type -> proc

    def add_key(self, type, proc):
        assert type is not int
        self.mappers[type] = proc

    def __getitem__(self, k):
        if isinstance(k, int):
            return list.__getitem__(self, k)
        proc = self.mappers[type(k)]
        for i in range(0, len(self)):
            x = self[i]
            if proc(x) == k:
                return x
        raise KeyError(k)

    def keys(self):
        return reduce(list.__add__,
                      [[p(x) for x in self] for p in self.mappers.values()],
                      [])

