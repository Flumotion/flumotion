# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4

# Flumotion - a video streaming server
# Copyright (C) 2004 Fluendo
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Street #330, Boston, MA 02111-1307, USA.

from common import unittest

import flumotion.config

class TestConfig(unittest.TestCase):
    def testVariables(self):
        assert hasattr(flumotion.config, 'datadir')
        assert isinstance(flumotion.config.datadir, str)
        assert hasattr(flumotion.config, 'gladedir')
        assert isinstance(flumotion.config.gladedir, str)

    def testUninstalled(self):
        assert flumotion.config.installed == 0

if __name__ == '__main__':
     unittest.main()
