# -*- Mode: Python; test-case-name: flumotion.test.test_flumotion_config -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# flumotion/test/test_flumotion_config.py: test for flumotion.config
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

import flumotion.config

class TestConfig(unittest.TestCase):
    def testVariables(self):
        assert hasattr(flumotion.config, 'datadir')
        assert isinstance(flumotion.config.datadir, str)
        assert hasattr(flumotion.config, 'gladedir')
        assert isinstance(flumotion.config.gladedir, str)

    def testUninstalled(self):
        assert flumotion.config.isinstalled == 0

if __name__ == '__main__':
     unittest.main()
