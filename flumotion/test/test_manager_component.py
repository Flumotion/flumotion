# -*- Mode: Python; test-case-name: flumotion.test.test_manager_component -*-
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


from StringIO import StringIO
from twisted.internet import defer

from flumotion.common import log, testsuite
from flumotion.common import common, identity
from flumotion.manager import component, manager


class _DictAttrClass(object):
    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)
def dac(**kw):
    return _DictAttrClass(**kw)

class FakeComponentAvatar(log.Loggable):
    _nextPort = 1024
    def __init__(self, parent, name, eaters=None, feeders=None, vfeeds=None,
                 clockMaster=False, worker='localhost', host='127.0.0.1',
                 fport=-1):
        self._parent = parent
        self._name = name
        self._host = host
        if fport == -1:
            fport = FakeComponentAvatar._nextPort
            FakeComponentAvatar._nextPort += 1
        self._fport = fport
        self._worker = worker

        self._eatlog = []
        self._feedlog = []

        if eaters is None:
            eaters = {}
        self._eaters = eaters
        if feeders is None:
            feeders = ['default']
        self._feeders = feeders
        if vfeeds is None:
            vfeeds = {}
        self._vfeeds = dict([(common.fullFeedId(self._parent, vcomp, vfeed),
                              (self, feed))
                             for vcomp, vfeed, feed in vfeeds])

        self.avatarId = common.componentId(parent, name)
        self.componentState = (None, 'componentState_%s' % name)
        self.jobState = (None, 'jobState_%s' % name)
        self._clockmaster = clockMaster

        gp = (lambda : dac(host=self._host))
        self.mind = dac(broker=dac(transport=dac(getPeer=gp)))

    def __repr__(self):
        return '<FakeComponentAvatar %r>' % self.avatarId

    def getClockMaster(self):
        if not self._clockmaster:
            return None
        return self.avatarId

    def getEaters(self):
        return self._eaters

    def getFeeders(self):
        return self._feeders

    def getFeedId(self, feedName):
        return common.feedId(self._name, feedName)

    def getFullFeedId(self, feedName):
        return common.fullFeedId(self._parent, self._name, feedName)

    def getVirtualFeeds(self):
        return self._vfeeds

    def getParentName(self):
        return self._parent

    def getClientAddress(self):
        return self._host

    def getFeedServerPort(self):
        return self._fport

    def eatFrom(self, eaterAlias, fullFeedId, host, port):
        self.debug('%r eatFrom: %r, %r, %r, %r', self, eaterAlias, fullFeedId,
                   host, port)
        self._eatlog.append((eaterAlias, fullFeedId, host, port))
        return defer.succeed(None)

    def feedTo(self, feederName, fullFeedId, host, port):
        self.debug('%r feedTo: %r, %r, %r, %r', self, feederName, fullFeedId,
                   host, port)
        self._feedlog.append((feederName, fullFeedId, host, port))
fca = FakeComponentAvatar

class FakeVishnu(log.Loggable):
    running = True

class TestComponentHeaven(log.Loggable, testsuite.TestCase):
    def setUp(self):
        self.vishnu = v = FakeVishnu()
        self.heaven = component.ComponentHeaven(v)
        FakeComponentAvatar._nextPort = 1024

    def attach(self, comp):
        assert comp.avatarId not in self.heaven.avatars
        self.heaven.avatars[comp.avatarId] = comp
        self.heaven.componentAttached(comp)

    def detach(self, comp):
        assert comp.avatarId in self.heaven.avatars
        del self.heaven.avatars[comp.avatarId]
        self.heaven.componentDetached(comp)

    def resetEatFeed(self, *cs):
        for c in cs:
            c._eatlog = []
            c._feedlog = []

    def assertNoEatFeed(self, *idles):
        for c in idles:
            if c._eatlog:
                self.fail('Non-empty eatlog: %r - %r' % (c, c._eatlog))
            elif c._feedlog:
                self.fail('Non-empty feedlog: %r - %r' % (c, c._feedlog))

    def assertEatFeed(self, acts, *idles):
        for c, eats, feeds in acts:
            # actions can occur in arbitrary order - so sorting for
            # stable results
            if eats is not None:
                _eats, _eatlog = eats[:], c._eatlog[:]
                _eats.sort()
                _eatlog.sort()
                if _eatlog != _eats:
                    self.fail('Eat actions do not match for %r: %r != %r' %
                              (c, c._eatlog, eats))
            if feeds is not None:
                _feeds, _feedlog = feeds[:], c._feedlog[:]
                _feeds.sort()
                _feedlog.sort()
                if _feedlog != _feeds:
                    self.fail('Feed actions do not match for %r: %r != %r' %
                              (c, c._feedlog, feeds))
        self.assertNoEatFeed(*idles)

    def testAttachDetachLinear(self):
        # create 4 component flow, chained: c1 -> c2 -> c3 -> c4
        c1 = fca('a', 'comp1', clockMaster=False)
        c2 = fca('a', 'comp2',
                 eaters={'default': [('comp1:default', 'default-prime')]})

        c3 = fca('a', 'comp3',
                 eaters={'default': [('comp2:default', 'default-prime')]})

        c4 = fca('a', 'comp4',
                 eaters={'default': [('comp3:default', 'default-prime')]})

        all = (c1, c2, c3, c4)
        self.assertNoEatFeed(*all)

        self.attach(c1)
        self.assertNoEatFeed(*all)

        self.attach(c2)
        self.assertEatFeed([(c2, [('default-prime', '/a/comp1:default',
                                   '127.0.0.1', 1024)], [])], c1, c3, c4)
        self.resetEatFeed(c2)

        self.attach(c3)
        self.assertEatFeed([(c3, [('default-prime', '/a/comp2:default',
                                   '127.0.0.1', 1025)], [])], c1, c2, c4)
        self.resetEatFeed(c3)

        self.attach(c4)
        self.assertEatFeed([(c4, [('default-prime', '/a/comp3:default',
                                   '127.0.0.1', 1026)], [])], c1, c2, c3)
        self.resetEatFeed(c4)

        self.detach(c2)
        self.assertNoEatFeed(*all)

        self.attach(c2)
        self.assertEatFeed([(c2, [('default-prime', '/a/comp1:default',
                                   '127.0.0.1', 1024)], []),
                            (c3, [('default-prime', '/a/comp2:default',
                                   '127.0.0.1', 1025)], [])], c1, c4)

        self.detach(c1)
        self.assertNoEatFeed(*all)

        self.attach(c1)
        self.assertEatFeed([(c2, [('default-prime', '/a/comp1:default',
                                   '127.0.0.1', 1024)], [])], c1, c3, c4)
    testAttachDetachLinear.todo = 'Arek will fix this soon.'

    def testAttachDetachMultipleEaters(self):
        # create 6 component flow, tee'ed at c2:
        # c1 -> c2 -> c3 -> c4
        #         \-> c5 -> c6
        c1 = fca('a', 'comp1', clockMaster=False)
        c2 = fca('a', 'comp2',
                 eaters={'default': [('comp1:default', 'default-prime')]})

        c3 = fca('a', 'comp3',
                 eaters={'default': [('comp2:default', 'default-prime')]})

        c4 = fca('a', 'comp4',
                 eaters={'default': [('comp3:default', 'default-prime')]})

        c5 = fca('a', 'comp5',
                 eaters={'default': [('comp2:default', 'default-prime')]})

        c6 = fca('a', 'comp6',
                 eaters={'default': [('comp5:default', 'default-prime')]})

        all = (c1, c2, c3, c4, c5, c6)
        self.assertNoEatFeed(*all)

        self.attach(c1)
        self.assertNoEatFeed(*all)

        self.attach(c2)
        self.assertEatFeed([(c2, [('default-prime', '/a/comp1:default',
                                   '127.0.0.1', 1024)], [])],
                           c1, c3, c4, c5, c6)
        self.resetEatFeed(c2)

        self.attach(c3)
        self.assertEatFeed([(c3, [('default-prime', '/a/comp2:default',
                                   '127.0.0.1', 1025)], [])],
                           c1, c2, c4, c5, c6)
        self.resetEatFeed(c3)

        self.attach(c4)
        self.assertEatFeed([(c4, [('default-prime', '/a/comp3:default',
                                   '127.0.0.1', 1026)], [])],
                           c1, c2, c3, c5, c6)
        self.resetEatFeed(c4)

        self.attach(c5)
        self.assertEatFeed([(c5, [('default-prime', '/a/comp2:default',
                                   '127.0.0.1', 1025)], [])],
                           c1, c2, c3, c4, c6)
        self.resetEatFeed(c5)

        self.attach(c6)
        self.assertEatFeed([(c6, [('default-prime', '/a/comp5:default',
                                   '127.0.0.1', 1028)], [])],
                           c1, c2, c3, c4, c5)
        self.resetEatFeed(c6)

        self.detach(c2)
        self.assertNoEatFeed(*all)

        self.attach(c2)
        self.assertEatFeed([(c2, [('default-prime', '/a/comp1:default',
                                   '127.0.0.1', 1024)], []),
                            (c3, [('default-prime', '/a/comp2:default',
                                   '127.0.0.1', 1025)], []),
                            (c5, [('default-prime', '/a/comp2:default',
                                   '127.0.0.1', 1025)], [])],
                           c1, c4, c6)
        self.resetEatFeed(c2, c3, c5)

        self.detach(c1)
        self.assertNoEatFeed(*all)

        self.attach(c1)
        self.assertEatFeed([(c2, [('default-prime', '/a/comp1:default',
                                   '127.0.0.1', 1024)], [])],
                           c1, c3, c4, c5, c6)
        self.resetEatFeed(c2)
    testAttachDetachMultipleEaters.todo = 'Arek will fix this soon.'

    def testAttachDetachMultipleFeedersSimple(self):
        # create 7 component flow, muxed(/switched/etc) at c5:
        # c1 -> c2 (a) -> c5 -> c6 -> c7
        # c3 -> c4 (v) /
        c1 = fca('a', 'comp1', clockMaster=False)
        c2 = fca('a', 'comp2',
                 eaters={'default': [('comp1:default', 'default-prime')]})
        c3 = fca('a', 'comp3')
        c4 = fca('a', 'comp4',
                 eaters={'default': [('comp3:default', 'default-prime')]})
        c5 = fca('a', 'comp5',
                 eaters={'audio': [('comp2:default', 'audio-prime')],
                         'video': [('comp4:default', 'video-prime')]})
        c6 = fca('a', 'comp6',
                 eaters={'default': [('comp5:default', 'default-prime')]})
        c7 = fca('a', 'comp7',
                 eaters={'default': [('comp6:default', 'default-prime')]})

        all = (c1, c2, c3, c4, c5, c6, c7)
        self.assertNoEatFeed(*all)

        self.attach(c1)
        self.assertNoEatFeed(*all)

        self.attach(c2)
        self.assertEatFeed([(c2, [('default-prime', '/a/comp1:default',
                                   '127.0.0.1', 1024)], [])],
                           c1, c3, c4, c5, c6, c7)
        self.resetEatFeed(c2)

        self.attach(c3)
        self.assertNoEatFeed(*all)

        self.attach(c4)
        self.assertEatFeed([(c4, [('default-prime', '/a/comp3:default',
                                   '127.0.0.1', 1026)], [])],
                           c1, c2, c3, c5, c6, c7)
        self.resetEatFeed(c4)

        self.attach(c5)
        self.assertEatFeed([(c5, [('audio-prime', '/a/comp2:default',
                                   '127.0.0.1', 1025),
                                  ('video-prime', '/a/comp4:default',
                                   '127.0.0.1', 1027)], [])],
                           c1, c2, c3, c4, c6, c7)
        self.resetEatFeed(c5)

        self.attach(c6)
        self.assertEatFeed([(c6, [('default-prime', '/a/comp5:default',
                                   '127.0.0.1', 1028)], [])],
                           c1, c2, c3, c4, c5, c7)
        self.resetEatFeed(c6)

        self.attach(c7)
        self.assertEatFeed([(c7, [('default-prime', '/a/comp6:default',
                                   '127.0.0.1', 1029)], [])],
                           c1, c2, c3, c4, c5, c6)
        self.resetEatFeed(c7)

        self.detach(c2)
        self.assertNoEatFeed(*all)

        self.attach(c2)
        self.assertEatFeed([(c2, [('default-prime', '/a/comp1:default',
                                   '127.0.0.1', 1024)], []),
                            (c5, [('audio-prime', '/a/comp2:default',
                                   '127.0.0.1', 1025)], [])],
                           c1, c3, c4, c6, c7)
        self.resetEatFeed(c2, c5)

        self.detach(c1)
        self.assertNoEatFeed(*all)

        self.attach(c1)
        self.assertEatFeed([(c2, [('default-prime', '/a/comp1:default',
                                   '127.0.0.1', 1024)], [])],
                           c1, c3, c4, c5, c6, c7)
        self.resetEatFeed(c2)

        self.detach(c5)
        self.assertNoEatFeed(*all)

        self.attach(c5)
        self.assertEatFeed([(c5, [('audio-prime', '/a/comp2:default',
                                   '127.0.0.1', 1025),
                                  ('video-prime', '/a/comp4:default',
                                   '127.0.0.1', 1027)], []),
                            (c6, [('default-prime', '/a/comp5:default',
                                   '127.0.0.1', 1028)], [])],
                           c1, c2, c3, c4, c7)
        self.resetEatFeed(c5, c6)
    testAttachDetachMultipleFeedersSimple.todo = 'Arek will fix this soon.'

    def testAttachDetachMultipleFeedersVirtual(self):
        # create 7 component flow, with c5 eating a virtual feed c2/c4:
        # c1 -> c2 ... -> c5 -> c6 -> c7
        # c3 -> c4 ... /
        c1 = fca('a', 'comp1', clockMaster=False)
        c2 = fca('a', 'comp2',
                 eaters={'default': [('comp1:default', 'default-prime')]},
                 vfeeds=[('vcomp', 'vfeed', 'default')])
        c3 = fca('a', 'comp3')
        c4 = fca('a', 'comp4',
                 eaters={'default': [('comp3:default', 'default-prime')]},
                 vfeeds=[('vcomp', 'vfeed', 'default')])
        c5 = fca('a', 'comp5',
                 eaters={'default': [('vcomp:vfeed', 'default-prime')]})
        c6 = fca('a', 'comp6',
                 eaters={'default': [('comp5:default', 'default-prime')]})
        c7 = fca('a', 'comp7',
                 eaters={'default': [('comp6:default', 'default-prime')]})

        all = (c1, c2, c3, c4, c5, c6, c7)
        self.assertNoEatFeed(*all)

        self.attach(c1)
        self.assertNoEatFeed(*all)

        self.attach(c2)
        self.assertEatFeed([(c2, [('default-prime', '/a/comp1:default',
                                   '127.0.0.1', 1024)], [])],
                           c1, c3, c4, c5, c6, c7)
        self.resetEatFeed(c2)

        self.attach(c3)
        self.assertNoEatFeed(*all)

        # connect c5 before c4 so we're sure c2 will get selected
        # without any assumptions...
        self.attach(c5)
        self.assertEatFeed([(c5, [('default-prime', '/a/comp2:default',
                                   '127.0.0.1', 1025)], [])],
                           c1, c2, c3, c4, c6, c7)
        self.resetEatFeed(c5)

        # attach the second component providing vcomp:vfeed, now that
        # c5 is already connected
        self.attach(c4)
        self.assertEatFeed([(c4, [('default-prime', '/a/comp3:default',
                                   '127.0.0.1', 1026)], [])],
                           c1, c2, c3, c5, c6, c7)
        self.resetEatFeed(c4)

        self.attach(c6)
        self.assertEatFeed([(c6, [('default-prime', '/a/comp5:default',
                                   '127.0.0.1', 1028)], [])],
                           c1, c2, c3, c4, c5, c7)
        self.resetEatFeed(c6)

        self.attach(c7)
        self.assertEatFeed([(c7, [('default-prime', '/a/comp6:default',
                                   '127.0.0.1', 1029)], [])],
                           c1, c2, c3, c4, c5, c6)
        self.resetEatFeed(c7)

        self.detach(c2)
        self.assertEatFeed([(c5, [('default-prime', '/a/comp4:default',
                                   '127.0.0.1', 1027)], [])],
                           c1, c2, c3, c4, c6, c7)
        self.resetEatFeed(c5)

        self.attach(c2)
        self.assertEatFeed([(c2, [('default-prime', '/a/comp1:default',
                                   '127.0.0.1', 1024)], [])],
                           c1, c3, c4, c5, c6, c7)
        self.resetEatFeed(c2)

        self.detach(c1)
        self.assertNoEatFeed(*all)

        self.attach(c1)
        self.assertEatFeed([(c2, [('default-prime', '/a/comp1:default',
                                   '127.0.0.1', 1024)], [])],
                           c1, c3, c4, c5, c6, c7)
        self.resetEatFeed(c2)

        self.detach(c5)
        self.assertNoEatFeed(*all)

        # FIXME: don't rely on the order of components attaching for
        # selection of virtual feed provider?
        self.attach(c5)
        self.assertEatFeed([(c5, [('default-prime', '/a/comp4:default',
                                   '127.0.0.1', 1027)], []),
                            (c6, [('default-prime', '/a/comp5:default',
                                   '127.0.0.1', 1028)], [])],
                           c1, c2, c3, c4, c7)
        self.resetEatFeed(c5, c6)
    testAttachDetachMultipleFeedersVirtual.todo = 'Arek will fix this soon.'
