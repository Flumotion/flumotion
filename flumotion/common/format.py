# -*- Mode: Python -*-
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

# F0.10
# kept for compatibility in 0.8, but format is a builtin
# module renamed to formatting

# 0.8 code should use
# from flumotion.common import format as formatting
# since bundled code can be running against older 0.8 that does not have
# the formatting module yet

# When going to 0.10, remove this module completely and change all imports to
# from flumotion.common import formatting

from flumotion.common.formatting import *
