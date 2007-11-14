# -*- Mode: Python; test-case-name: flumotion.test.test_config -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2004,2005,2006,2007 Fluendo, S.L. (www.fluendo.com).
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

"""
forward compatibility with future python versions
"""

import sys

__pychecker__ = 'no-shadowbuiltin'

# sorted() was introduced in 2.4
if sys.version_info[:2] < (2, 4):
    def sorted(seq, reverse=False):
        seq = seq[:]
        seq.sort()
        if reversed:
            seq = seq[::-1]
        return seq

# any() was introduced in 2.5
if sys.version_info[:2] < (2, 5):
    def any(seq):
        for item in seq:
            if item:
                return True
        return False

