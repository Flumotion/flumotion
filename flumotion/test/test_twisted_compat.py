# -*- Mode: Python; test-case-name: flumotion.test.test_twisted_compat -*-
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

import common

from twisted.trial import unittest

import warnings
from twisted.spread import pb
import exceptions

from flumotion.twisted import compat
from flumotion.twisted.compat import implements
from flumotion.common import common as fcommon

class TestComponentsWarning(unittest.TestCase):
    warned = False

    def setUp(self):
        warnings.resetwarnings()
        self.showwarning = warnings.showwarning

    def tearDown(self):
        warnings.showwarning = self.showwarning

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

class AnInterface(compat.Interface):
    pass

class AnotherInterface(compat.Interface):
    pass

class WowAnotherInterface(compat.Interface):
    pass

class AClass:
    implements(AnInterface)

class AnotherClass:
    implements(AnotherInterface)

class AnInheritedClass(AClass):
    pass

class AMultipleInheritedClass(AClass, AnotherClass):
    implements(WowAnotherInterface)

class ANewMultipleInheritedClass(AClass, AnotherClass):
    implements(fcommon.mergeImplements(AClass,AnotherClass) + (WowAnotherInterface,))

class TestImplements(unittest.TestCase):
    def testAClassObjectImplementsAnInterface(self):
        instance = AClass()
        self.failUnless(compat.implementsInterface(instance,AnInterface))

    def testAnInheritedClassObjectImplementsAnInterface(self):
        inheritedInstance = AnInheritedClass()
        self.failUnless(compat.implementsInterface(
            inheritedInstance,AnInterface))
    # These fail on twisted 1.3 so have commented out
    # Until we deprecate twisted 1.3, we will have to use mergeImplements
    # when doing multiple inheritance of interface implementing classes

    #def testAMultipleInheritedClassObjectImplementsAnInterface(self):
    #    multipleInheritedInstance = AMultipleInheritedClass()
    #    self.failUnless(compat.implementsInterface(
    #        multipleInheritedInstance, AnInterface))
    #
    #def testAMultipleInheritedClassObjectImplementsAnotherInterface(self):
    #    multipleInheritedInstance = AMultipleInheritedClass()
    #    self.failUnless(compat.implementsInterface(
    #        multipleInheritedInstance, AnotherInterface))
    #
    #def testAMultipleheritedClassObjectImplementsWowAnotherInterface(self):
    #    multipleInheritedInstance = AMultipleInheritedClass()
    #    self.failUnless(compat.implementsInterface(
    #        multipleInheritedInstance, WowAnotherInterface))
    #
    #def testANewMultipleInheritedClassObjectImplementsAnInterface(self):
    #    multipleInheritedInstance = ANewMultipleInheritedClass()
    #    self.failUnless(compat.implementsInterface(
    #        multipleInheritedInstance, AnInterface))
    
    def testANewMultipleInheritedClassObjectImplementsAnotherInterface(self):
        multipleInheritedInstance = ANewMultipleInheritedClass()
        self.failUnless(compat.implementsInterface(
            multipleInheritedInstance, AnotherInterface))

    def testANewMultipleheritedClassObjectImplementsWowAnotherInterface(self):
        multipleInheritedInstance = ANewMultipleInheritedClass()
        self.failUnless(compat.implementsInterface(
            multipleInheritedInstance, WowAnotherInterface))

