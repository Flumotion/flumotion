# -*- Mode: Python; test-case-name: flumotion.test.test_component_init -*-
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

from twisted.trial import unittest

from flumotion.common import testsuite
from flumotion.common import registry, log, reflectcall


class TestInit(testsuite.TestCase):

    def testInit(self):
        r = registry.getRegistry()
        components = [c.getType() for c in r.getComponents()]
        for type in components:
            # skip test components - see test_config.py
            if type.startswith('test-'):
                continue

            log.debug('test', 'testing component type %s' % type)
            defs = r.getComponent(type)
            try:
                entry = defs.getEntryByType('component')
            except KeyError, e:
                self.fail(
                    'KeyError while trying to get component entry for %s' %
                        type)
            moduleName = defs.getSource()
            methodName = entry.getFunction()
            # call __init__ without the config arg; this will load
            # modules, get the entry point, then fail with too-few
            # arguments. would be nice to __init__ with the right
            # config, but that is component-specific...
            self.assertRaises(TypeError,
                              reflectcall.reflectCall,
                              moduleName, methodName)

if __name__ == '__main__':
    unittest.main()
