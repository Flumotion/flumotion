# -*- Mode: Python; test-case-name: flumotion.test.test_configure -*-
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

from twisted.trial import unittest

from flumotion.configure import configure
from flumotion.common import testsuite


class TestConfig(testsuite.TestCase):

    def testVariables(self):
        assert hasattr(configure, 'configdir')
        assert isinstance(configure.configdir, str)
        assert hasattr(configure, 'gladedir')
        assert isinstance(configure.gladedir, str)
        assert hasattr(configure, 'imagedir')
        assert isinstance(configure.imagedir, str)
        assert hasattr(configure, 'logdir')
        assert isinstance(configure.logdir, str)
        assert hasattr(configure, 'pythondir')
        assert isinstance(configure.pythondir, str)
        assert hasattr(configure, 'registrydir')
        assert isinstance(configure.registrydir, str)
        assert hasattr(configure, 'version')
        assert isinstance(configure.version, str)

    def testUninstalled(self):
        assert configure.isinstalled == False

if __name__ == '__main__':
    unittest.main()
