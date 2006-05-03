# -*- Mode: Python; test-case-name: flumotion.test.test_manager_worker -*-
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

from twisted.trial import unittest

from flumotion.manager import worker

class TestHeaven(unittest.TestCase):
    def testConstructor(self):
        h = worker.WorkerHeaven(None)
        assert isinstance(h, worker.WorkerHeaven)

    def testAdd(self):
        h = worker.WorkerHeaven(None)
        avatar = h.createAvatar('foo', None)

        assert 'foo' in [a.getName() for a in h.getAvatars()]
        assert isinstance(avatar, worker.WorkerAvatar)
        h.removeAvatar('foo')
        
        assert not 'foo' in [a.getName() for a in h.getAvatars()]

    def testError(self):
        h = worker.WorkerHeaven(None)

    def testAttached(self):
        h = worker.WorkerHeaven(None)
        avatar = h.createAvatar('foo', None)

        h.workerAttached(avatar)
