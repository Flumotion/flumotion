# -*- Mode: Python; test-case-name: flumotion.test.test_common_planet -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2008 Fluendo, S.L. (www.fluendo.com).
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

import errno
import os

from flumotion.common.interfaces import IDirectory
from flumotion.common.testsuite import TestCase
from flumotion.common.vfs import listDirectory


class VFSTest(TestCase):
    def setUp(self):
        self.path = os.path.dirname(__file__)

    def testListDirectory(self):
        try:
            d = listDirectory(self.path)
        except AssertionError:
            # missing backends
            return

        def done(directory):
            self.failUnless(IDirectory.providedBy(directory))
            self.assertEqual(directory.filename,
                             os.path.basename(self.path))
            self.assertEqual(directory.getPath(), self.path)
            self.failUnless(directory.iconNames)
        d.addCallback(done)
        return d
