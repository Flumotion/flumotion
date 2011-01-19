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

import tempfile
import os

from flumotion.common import testsuite
from flumotion.common import log
from flumotion.common.planet import moods
from flumotion.component.consumers.disker import disker

from flumotion.test import comptest

attr = testsuite.attr


class PluggableComponentTestCase(comptest.CompTestTestCase):

    def get_plugs(self, socket):
        """Return plug configs for the given socket."""
        return []

    def build_plugs(self, sockets=None):
        if sockets is None:
            sockets = ()
        plugs = dict([(s, self.get_plugs(s)) for s in sockets])
        return plugs


class TestConfig(PluggableComponentTestCase, log.Loggable):

    logCategory = 'disker-test'

    def tearDown(self):
        # we instantiate the component, and it doesn't clean after
        # itself correctly, so we need to manually clean the reactor
        comptest.cleanup_reactor()

    def get_config(self, properties):
        return {'feed': [],
                'name': 'disk-video',
                'parent': 'default',
                'eater': {'default':
                              [('default', 'video-source:video')]},
                'source': ['video-source:video'],
                'avatarId': '/default/disk-video',
                'clock-master': None,
                'plugs':
                    self.build_plugs(['flumotion.component.consumers.'
                                      'disker.disker_plug.DiskerPlug']),
                'type': 'disk-consumer',
                'properties': properties}

    @attr('slow')
    def test_config_minimal(self):
        properties = {'directory': '/tmp'}

        dc = comptest.ComponentWrapper('disk-consumer', disker.Disker,
                                       name='dc',
                                       cfg=self.get_config(properties))
        d = dc.instantiate()
        # actually wait for the component to start up and go hungry
        d.addCallback(lambda _: dc.wait_for_mood(moods.hungry))
        d.addCallback(lambda _: dc.stop())
        return d

    def test_config_rotate_invalid(self):
        properties = {'directory': '/tmp',
                      'rotate-type': 'invalid'}

        dc = comptest.ComponentWrapper('disk-consumer', disker.Disker,
                                       name='dc',
                                       cfg=self.get_config(properties))
        d = dc.instantiate()
        return self.failUnlessFailure(d, comptest.ComponentSad)

    def test_config_rotate_size_no_size(self):
        properties = {'directory': '/tmp',
                      'rotate-type': 'size'}

        dc = comptest.ComponentWrapper('disk-consumer', disker.Disker,
                                       name='dc',
                                       cfg=self.get_config(properties))
        d = dc.instantiate()
        return self.failUnlessFailure(d, comptest.ComponentSad)

    def test_config_rotate_time_no_time(self):
        properties = {'directory': '/tmp',
                      'rotate-type': 'time'}

        dc = comptest.ComponentWrapper('disk-consumer', disker.Disker,
                                       name='dc',
                                       cfg=self.get_config(properties))
        d = dc.instantiate()
        return self.failUnlessFailure(d, comptest.ComponentSad)

    def test_config_rotate_size(self):
        properties = {'directory': '/tmp',
                      'rotate-type': 'size',
                      'size': 16}

        dc = comptest.ComponentWrapper('disk-consumer', disker.Disker,
                                       name='dc',
                                       cfg=self.get_config(properties))
        d = dc.instantiate()
        # don't wait for it to go hungry, be happy with just
        # instantiating correctly
        return d

    def test_config_rotate_time(self):
        properties = {'directory': '/tmp',
                      'rotate-type': 'time',
                      'time': 10}

        dc = comptest.ComponentWrapper('disk-consumer', disker.Disker,
                                       name='dc',
                                       cfg=self.get_config(properties))
        d = dc.instantiate()
        # don't wait for it to go hungry, be happy with just
        # instantiating correctly
        return d


class TestFlow(PluggableComponentTestCase, log.Loggable):

    slow = True

    def setUp(self):
        self.tp = comptest.ComponentTestHelper()
        prod = ('videotestsrc is-live=true ! '
                'video/x-raw-rgb,framerate=(fraction)1/2,width=320,height=240')
        self.s = 'flumotion.component.consumers.disker.disker_plug.DiskerPlug'

        self.prod = comptest.pipeline_src(prod)

    def tearDown(self):
        comptest.cleanup_reactor()

    def test_size_disker_running_and_happy(self):
        properties = {'directory': '/tmp',
                      'rotate-type': 'size',
                      'size': 10,
                      'symlink-to-current-recording': 'current'}

        dc = comptest.ComponentWrapper('disk-consumer', disker.Disker,
                                       name='disk-video', props=properties,
                                       plugs=self.build_plugs([self.s]))

        self.tp.set_flow([self.prod, dc])

        d = self.tp.start_flow()

        # wait for the disker to go happy
        d.addCallback(lambda _: dc.wait_for_mood(moods.happy))
        # let it run for a few seconds
        d.addCallback(lambda _: comptest.delayed_d(30, _))
        # and finally stop the flow
        d.addCallback(lambda _: self.tp.stop_flow())
        return d

    def test_time_disker_running_and_happy(self):
        properties = {'directory': '/tmp',
                      'rotate-type': 'time',
                      'time': 10,
                      'symlink-to-current-recording': 'current'}

        dc = comptest.ComponentWrapper('disk-consumer', disker.Disker,
                                       name='disk-video', props=properties,
                                       plugs=self.build_plugs([self.s]))

        self.tp.set_flow([self.prod, dc])

        d = self.tp.start_flow()

        # wait for the disker to go happy
        d.addCallback(lambda _: dc.wait_for_mood(moods.happy))
        # let it run for a few seconds
        d.addCallback(lambda _: comptest.delayed_d(30, _))
        # and finally stop the flow
        d.addCallback(lambda _: self.tp.stop_flow())
        return d


class FakeComponent:

    def warning(self, a, b, c):
        pass

    def addMessage(self, a):
        pass


def warning(*args):
    if len(args) == 0:
        message = ''
    elif len(args) == 1:
        message = args[0]
    if len(args) > 1:
        message = args[0] % args[1:]
    raise Exception(message)


class TestIndex(testsuite.TestCase):

    INDEX = '''\
%s
CHK POS LEN TS DUR KF %s TDUR
0 0 1 10 10 True 110 10
1 1 1 20 10 True%s 10
2 2 -1 30 -1 True 130 -1'''

    def setUp(self):
        self.component = FakeComponent()
        self.index = disker.Index()
        self.index.warning = warning

    def failUnlessRaisesWithMessage(self, message, call, *args):
        try:
            call(*args)
        except Exception, e:
            self.failIf(not str(e).startswith(message))
            return
        self.fail()

    def checkEntry(self, entry, offset, timestamp):
        self.assertEquals(entry['offset'], offset)
        self.assertEquals(entry['timestamp'], timestamp)

    def fillIndex(self):
        self.index.addEntry(0, 10, 1, 110)
        self.index.addEntry(1, 20, 1, 120)
        self.index.addEntry(2, 30, 1, 130)

    def fillBigIndex(self):
        for i in range(100):
            self.index.addEntry(i, i*10, 1, 0)

    def testAddIndexEntry(self):
        self.index.addEntry(0, 10, 1, 0)
        self.checkEntry(self.index._index[0], 0, 10)

    def testAddMultipleEntries(self):
        self.fillIndex()
        self.checkEntry(self.index._index[0], 0, 10)
        self.checkEntry(self.index._index[1], 1, 20)
        self.checkEntry(self.index._index[2], 2, 30)

    def testAddNonIncreasingEntry(self):
        self.index.addEntry(0, 10, 1, 10)
        self.index.addEntry(1, 20, 1, 20)
        self.failUnlessRaisesWithMessage("Could not add entries with a "
            "decreasing timestamp", self.index.addEntry, 2, 10, 1, 30)

    def testClearIndex(self):
        self.fillIndex()
        self.index.clear()
        self.assertEquals(len(self.index._index), 0)

    def testUpdateStart(self):
        self.fillIndex()
        self.index.updateStart(11)
        self.assertEquals(len(self.index._index), 2)
        self.checkEntry(self.index._index[0], 1, 20)
        self.checkEntry(self.index._index[1], 2, 30)

    def testSave(self):
        self.fillIndex()
        fd, path = tempfile.mkstemp()
        self.index.setLocation(path)
        ret = self.index.save(0)
        self.assertEquals(ret, True)
        file = open(path, 'r')
        lines = file.readlines()
        self.assertEquals(lines,
            ['FLUIDX1 #Flumotion\n',
            'CHK POS LEN TS DUR KF TDT TDUR\n',
            '0 0 1 10 10 1 110 10\n',
            '1 1 1 20 10 1 120 10\n',
            '2 2 -1 30 -1 1 130 -1\n'])
        file.close()
        os.remove(path)

    def testSaveWithHeaders(self):
        self.fillIndex()
        self.index.setHeadersSize(10)
        fd, path = tempfile.mkstemp()
        self.index.setLocation(path)
        ret =self.index.save(0)
        self.assertEquals(ret, True)
        file = open(path, 'r')
        lines = file.readlines()
        self.assertEquals(lines,
            ['FLUIDX1 #Flumotion\n',
            'CHK POS LEN TS DUR KF TDT TDUR\n',
            '0 10 1 10 10 1 110 10\n',
            '1 11 1 20 10 1 120 10\n',
            '2 12 -1 30 -1 1 130 -1\n'])
        file.close()
        os.remove(path)

    def testSaveVoidIndex(self):
        fd, path = tempfile.mkstemp()
        self.index.setLocation(path)
        ret = self.index.save()
        self.assertEquals(ret, True)
        file = open(path, 'r')
        lines = file.readlines()
        self.assertEquals(lines,
            ['FLUIDX1 #Flumotion\n',
            'CHK POS LEN TS DUR KF TDT TDUR\n',
            ])
        file.close()
        os.remove(path)

    def testSaveBadFile(self):
        self.fillIndex()
        self.index.setLocation('/')
        self.failUnlessRaisesWithMessage("Failed to open output file ",
            self.index.save)

    def testLoadIndex(self):
        fd, path = tempfile.mkstemp(suffix='.index')
        tmpFile = open(path, 'w')
        tmpFile.write(self.INDEX % ('FLUIDX1 #Flumotion', 'TDT', ' 120'))
        tmpFile.flush()
        self.index.loadIndexFile(path)
        self.assertEquals(len(self.index._index), 3)
        os.remove(path)

    def testLoadIndexWithBadExtension(self):
        fd, path = tempfile.mkstemp()
        self.failUnlessRaisesWithMessage("This file is not a valid index: "
            "the extension of this file is not",
            self.index.loadIndexFile, path)
        os.remove(path)

    def testLoadIndexWithBadPath(self):
        self.failUnlessRaisesWithMessage("This file is not a valid index: "
            "error reading index file",
            self.index.loadIndexFile, "/bad/bad.index")

    def testLoadIndexWithEmptyFile(self):
        fd, path = tempfile.mkstemp(suffix='.index')
        self.failUnlessRaisesWithMessage("This file is not a valid index: "
            "the file is empty",
            self.index.loadIndexFile, path)
        os.remove(path)

    def testLoadIndexWithBadHeaders(self):
        fd, path = tempfile.mkstemp(suffix='.index')
        tmpFile = open(path, 'w')
        tmpFile.write(self.INDEX % ('FLIDX1 #Flumotion', 'TDT', ' 120'))
        tmpFile.flush()
        self.failUnlessRaisesWithMessage("This file is not a valid index: "
            "header is not",
            self.index.loadIndexFile, tmpFile.name)
        tmpFile.close()
        os.remove(path)

    def testLoadIndexWithBadKeys(self):
        fd, path = tempfile.mkstemp(suffix='.index')
        tmpFile = open(path, 'w')
        tmpFile.write(self.INDEX % ('FLUIDX1 #Flumotion', 'TD', ' 120'))
        tmpFile.flush()
        self.failUnlessRaisesWithMessage("This file is not a valid index: "
            "keys definition is not",
            self.index.loadIndexFile, tmpFile.name)
        tmpFile.close()
        os.remove(path)

    def testLoadIndexWithBadEntry(self):
        fd, path = tempfile.mkstemp(suffix='.index')
        tmpFile = open(path, 'w')
        tmpFile.write(self.INDEX % ('FLUIDX1 #Flumotion', 'TDT',
                                    ' NotAParsableNumber'))
        tmpFile.flush()
        self.failUnlessRaisesWithMessage("This file is not a valid index: "
            "could not parse one of the entries",
            self.index.loadIndexFile, tmpFile.name)
        tmpFile.close()
        os.remove(path)

    def testLoadIndexWithMissingEntry(self):
        fd, path = tempfile.mkstemp(suffix='.index')
        tmpFile = open(path, 'w')
        tmpFile.write(self.INDEX % ('FLUIDX1 #Flumotion', 'TDT',
                                    ''))
        tmpFile.flush()
        self.failUnlessRaisesWithMessage("This file is not a valid index: "
            "one of the entries doesn't have enough",
            self.index.loadIndexFile, tmpFile.name)
        tmpFile.close()
        os.remove(path)

    def testClipTimestamp(self):

        def checkClipResults(entries, length, start, stop):
            self.assertEquals(len(entries), length)
            self.assertEquals(entries[0]['timestamp'], start)
            self.assertEquals(entries[-1]['timestamp'], stop)

        self.fillBigIndex()
        # test lower boundary
        entries = self.index.clipTimestamp(0, 195)
        checkClipResults(entries, 20, 0, 190)
        # test higher boundary
        entries = self.index.clipTimestamp(1, 200)
        checkClipResults(entries, 21, 0, 200)
        # test inside boundaries
        entries = self.index.clipTimestamp(10, 195)
        checkClipResults(entries, 19, 10, 190)
        # test start outside lower boundary
        entries = self.index.clipTimestamp(-10, 195)
        checkClipResults(entries, 20, 0, 190)
        # test stop outside highest boundary
        entries = self.index.clipTimestamp(900, 1001)
        checkClipResults(entries, 9, 900, 980)
        self.assertEquals(len(entries), 9)
        # test all outside lower boundary
        entries = self.index.clipTimestamp(-10, -12)
        self.assertEquals(entries, None)
        # test all outside highest boundary
        entries = self.index.clipTimestamp(1001, 1100)
        self.assertEquals(entries, None)
