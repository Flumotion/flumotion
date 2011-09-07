# -*- Mode: Python; test-case-name: flumotion.test.test_common_planet -*-
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
