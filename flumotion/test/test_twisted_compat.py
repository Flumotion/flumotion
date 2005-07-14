# -*- Mode: Python; test-case-name: flumotion.test.test_twisted_compat -*-
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

import common

from twisted.trial import unittest

import warnings
from twisted.python import components
from twisted.spread import pb
import exceptions

from flumotion.twisted import compat

class AnInterface(components.Interface):
    pass

class AClass:
    __implements__ = AnInterface

class TestComponentsWarning(unittest.TestCase):
    warned = False

    def setUp(self):
        warnings.resetwarnings()
        self.showwarning = warnings.showwarning

    def tearDown(self):
        warnings.showwarning = self.showwarning

    # test if Twisted 2.0 generates a warning for this interface code
    def test20HasComponentsWarning(self):
        def myshowwarning(message, category, filename, lineno, file=None):
            self.warned = True
            
        self.warned = False
        warnings.resetwarnings()
        warnings.showwarning = myshowwarning
        
        instance = AClass()
        self.failUnless(components.implements(instance, AnInterface))
        if hasattr(components, 'ComponentsDeprecationWarning'):
            self.failUnless(self.warned)
        else:
            self.failIf(self.warned)

    # test if our filter filters out this warning for 2.0
    def test20FilterComponentsWarning(self):
        def myshowwarning(message, category, filename, lineno, file=None):
            self.warned = True
            
        self.warned = False
        warnings.showwarning = myshowwarning

        compat.filterWarnings(components, 'ComponentsDeprecationWarning')

        instance = AClass()
        self.failUnless(components.implements(instance, AnInterface))
        self.failIf(self.warned)

    # test a known 1.3 Deprecation warning
    def test13PerspectiveBrokerFactoryWarning(self):
        def myshowwarning(message, category, filename, lineno, file=None):
            self.warned = True

        self.warned = False
        warnings.showwarning = myshowwarning

        p = pb.BrokerFactory('astring')
        self.failUnless(self.warned)
        self.warned = False

        compat.filterWarnings(exceptions, 'DeprecationWarning')
        
        p = pb.BrokerFactory('astring')
        self.failIf(self.warned)

