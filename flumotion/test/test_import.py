# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2004--2009 Fluendo, S.L. (www.fluendo.com).
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

import os.path

import flumotion
from flumotion.common import testsuite
from twisted.trial import unittest


def find_modules(pkg_name, pkg_path, pkg_exclude=[]):
    if pkg_name in pkg_exclude:
        return

    for name in sorted(os.listdir(pkg_path)):
        path = os.path.join(pkg_path, name)
        if os.path.isdir(path):
            if os.path.isfile(os.path.join(path, '__init__.py')):
                pkg = pkg_name + '.' + name
                for module in find_modules(pkg, path, pkg_exclude):
                    yield module
        else:
            name, ext = os.path.splitext(name)
            if ext == '.py' and name != '__init__':
                yield pkg_name + '.' + name


class TestImport(testsuite.TestCase):

    def testImportAllModules(self):
        pkg_exclude = ['flumotion.test']

        try:
            import rrdtool
        except ImportError:
            pkg_exclude.append('flumotion.admin.rrdmon')

        for path in flumotion.__path__:
            for module in find_modules('flumotion', path, pkg_exclude):
                __import__(module, globals(), locals())

if __name__ == '__main__':
    unittest.main()
