# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# flumotion/test/common.py: common stuff for tests
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

ltihooks = sys.modules.get('gst.ltihooks')
if ltihooks:
    ltihooks.uninstall()

# logging
flumotion.common.setup.setup()
