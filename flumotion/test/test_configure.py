# -*- Mode: Python; test-case-name: flumotion.test.test_configure -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# flumotion/test/test_configure.py: test for flumotion.configure.configure
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

from flumotion.configure import configure

class TestConfig(unittest.TestCase):
    def testVariables(self):
        assert hasattr(configure, 'configdir')
        assert isinstance(configure.configdir, str)
        assert hasattr(configure, 'gladedir')
        assert isinstance(configure.gladedir, str)
        assert hasattr(configure, 'imagedir')
        assert isinstance(configure.imagedir, str)
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
