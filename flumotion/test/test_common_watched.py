# -*- Mode: Python; test-case-name: flumotion.test.test_common -*-
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

from flumotion.common.testsuite import TestCase
from flumotion.common.watched import WatchedList, WatchedDict


class WatchedListTest(TestCase):

    def testAppend(self):

        def watcher(item):
            assert item == 'test'

        l = WatchedList()
        l.watch(watcher)
        l.append('test')

    def testInsert(self):

        def watcher(item):
            assert item == 'test'

        l = WatchedList()
        l.watch(watcher)
        l.insert(0, 'test')

    def testRemove(self):

        def watcher(item):
            assert item == 'test'

        l = WatchedList()
        l.append('test')
        l.append('test2')
        l.watch(watcher)
        len = l.__len__()
        l.remove('test')

    def testRemoveError(self):

        def watcher(item):
            return

        l = WatchedList()
        l.watch(watcher)
        self.assertRaises(ValueError, l.remove, 'test')

    def testPop(self):

        def watcher(item):
            assert item == 'test'

        l = WatchedList()
        l.append('test2')
        l.append('test3')
        l.insert(1, 'test')
        l.watch(watcher)
        l.pop(1)

    def testPopError(self):

        def watcher(item):
            return

        l = WatchedList()
        l.watch(watcher)
        self.assertRaises(ValueError, l.remove, 1)

    def testSort(self):

        def watcher(item):
            for i in range(item.__len__()-1):
                assert item[i] <= item[i+1]

        l = WatchedList()
        l.append(2)
        l.append(4)
        l.append(1)
        l.append(3)
        l.watch(watcher)
        l.sort()

    def testReverse(self):

        def watcher(item):
            assert l[2] == 1
            assert l[1] == 2
            assert l[0] == 3

        l = WatchedList()
        l.append(1)
        l.append(2)
        l.append(3)
        l.watch(watcher)
        l.reverse()

    def testUnwatch(self):

        def watcher(item):
            return

        l = WatchedList()
        watcher_proc_id = l.watch(watcher)
        l.unwatch(watcher_proc_id)
        assert watcher_proc_id not in l.watch_procs


class WatchedDictTest(TestCase):

    def testSetitem(self):

        def watcher(item):
            assert item == (1, 'test')

        l = WatchedDict()
        l.watch(watcher)
        l[1] = 'test'

    def testDelitems(self):

        def watcher(item):
            assert item == (1, 'test')

        l = WatchedDict()
        l[1] = 'test'
        l.watch(watcher)
        l.__delitem__(1)

    def testDeleteError(self):

        def watcher(item):
            return

        l = WatchedDict()
        l.watch(watcher)
        self.assertRaises(KeyError, l.__delitem__, 1)

    def testPop(self):

        def watcher(item):
            assert item == (1, 'test')

        l = WatchedDict()
        l[1] = 'test'
        l.watch(watcher)
        l.pop(1, 'test')

    def testPopError(self):

        def watcher(item):
            return

        l = WatchedDict()
        l.watch(watcher)
        self.assertRaises(KeyError, l.pop, 1)

    def testPopitem(self):

        def watcher(item):
            assert item == (1, 'test')

        l = WatchedDict()
        l[1] = 'test'
        l.watch(watcher)
        l.popitem()

    def testPopItemError(self):

        def watcher(item):
            return

        l = WatchedDict()
        l.watch(watcher)
        self.assertRaises(KeyError, l.popitem)

    def testUpdate(self):

        def watcher(item):
            assert l['a'] == 11
            assert l['d'] == 4
            assert l['e'] == 5

        l = WatchedDict()
        l['a'] = 1
        l['b'] = 2
        l['c'] = 3
        d = {'a': 11, 'd': 4}
        l.watch(watcher)
        l.update(d, e=5)

    def testUnwatch(self):

        def watcher(item):
            return

        l = WatchedDict()
        watcher_proc_id = l.watch(watcher)
        l.unwatch(watcher_proc_id)
        assert watcher_proc_id not in l.watch_procs
