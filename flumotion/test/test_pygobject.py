# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2004,2005 Fluendo, S.L. (www.fluendo.com). All rights reserved.

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

from twisted.trial import unittest

import pygtk
pygtk.require('2.0')
import gobject

from flumotion.common.pygobject import (gsignal, gproperty,
                                        with_construct_properties)


class TestPyGObject(unittest.TestCase):
    def testPyGObject(self):
        class Foo(gobject.GObject):
            gsignal('hcf', bool, str)
            gproperty(bool, 'burning', 'If the object is burning',
                      False, construct=True)

            def __init__(xself):
                gobject.GObject.__init__(xself)
                xself.connect('hcf', xself.on_hcf)
            __init__ = with_construct_properties (__init__)

            def on_hcf(xself, again_self, x, y):
                self.assert_(isinstance(x, bool))
                self.assert_(isinstance(y, str))
                xself.set_property('burning', True)
        gobject.type_register(Foo)

        o = Foo()

        self.assertEquals(False, o.get_property('burning'))
        o.emit('hcf', False, 'foogoober')
        self.assertEquals(True, o.get_property('burning'))
