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

import glob
import os
import sys
import unittest

# testsuite srcdir
srcdir = os.path.join(os.path.split(os.path.abspath(__file__))[0], 'tests')

def gettestnames(dir):
    files = glob.glob(os.path.join(dir, '*.py'))
    fullnames = map(lambda x: x[:-3], files)
    names = map(lambda x: os.path.split(x)[1], fullnames)
    return names
        
suite = unittest.TestSuite()
loader = unittest.TestLoader()

try:
    import gst.ltihooks
    gst.ltihooks.uninstall()
except:
    pass

names = gettestnames(srcdir)

for name in names:
    suite.addTest(loader.loadTestsFromName(name))
    
testRunner = unittest.TextTestRunner()
result = testRunner.run(suite)
if not result.wasSuccessful():
   sys.exit(1)
