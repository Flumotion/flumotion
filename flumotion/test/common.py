# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# flumotion/test/common.py: common stuff for tests
#
# Flumotion - a streaming media server
# Copyright (C) 2004 Fluendo, S.L. (www.fluendo.com). All rights reserved.

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

import os
import sys
import unittest

import flumotion.common.setup

sys.path.insert(1, os.path.abspath('..'))

import pygtk
pygtk.require('2.0')

gstdir = '/opt/gnome/lib/python2.3/site-packages'
if not gstdir in sys.path:
    sys.path.append(gstdir)

import gst
import gst.interfaces

ltihooks = sys.modules.get('gst.ltihooks')
if ltihooks:
    ltihooks.uninstall()

# logging
flumotion.common.setup.setup()
