# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2004,2005,2006 Fluendo, S.L. (www.fluendo.com).
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

import flumotion.common.setup
# logging
flumotion.common.setup.setup()

from flumotion.common import log
log.logTwisted()

# make sure we have the right gst-python version
from flumotion.common import boot
boot.init_gobject()
boot.init_gst()

import os

# fdpass is a built module,  so it lives in builddir, while the package
# __init__ is in srcdir.  Append to its __path__ to make the tests work 
i = os.getcwd().find('_build')
if i > -1:
    top_builddir = os.path.join(os.getcwd()[:i], '_build')
    from flumotion.extern import fdpass
    fdpass.__path__.append(os.path.join(top_builddir, 'flumotion', 'extern',
        'fdpass'))

from twisted.trial import unittest
if type(unittest.TestCase) != type:
    # FIXME: T1.3
    def deferred_result(proc):
        def test(self):
            d = proc(self)
            return unittest.deferredResult(d)
        try:
            test.__name__ = proc.__name__
        except Exception:
            # can only set procedure names in python >= 2.4
            pass
        return test
else:
    deferred_result = lambda proc: proc
