# -*- Mode: Python; test-case-name: flumotion.test.test_worker_heaven -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# flumotion/test/test_worker_heaven.py: unittest for worker heaven
#
# Flumotion - a streaming media server
# Copyright (C) 2004 Fluendo (www.fluendo.com)

# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
# See "LICENSE.GPL" in the source distribution for more information.

# This program is also licensed under the Flumotion license.
# See "LICENSE.Flumotion" in the source distribution for more information.

from twisted.trial import unittest

from flumotion.manager import worker

class TestHeaven(unittest.TestCase):
    def testConstructor(self):
        h = worker.WorkerHeaven(None)
        assert isinstance(h, worker.WorkerHeaven)

    def testAdd(self):
        h = worker.WorkerHeaven(None)
        avatar = h.createAvatar('foo')

        assert 'foo' in h.avatars
        assert isinstance(avatar, worker.WorkerAvatar)
        h.removeAvatar('foo')
        
        assert not 'foo' in h.avatars

    def testError(self):
        h = worker.WorkerHeaven(None)
        self.assertRaises(KeyError, h.removeAvatar, 'unexistent')

    def testAttached(self):
        h = worker.WorkerHeaven(None)
        avatar = h.createAvatar('foo')

        h.workerAttached(avatar)

    def testGetEntries(self):
        h = worker.WorkerHeaven(None)
        avatar = h.createAvatar('foo')
        assert h.getEntries(avatar) == []
