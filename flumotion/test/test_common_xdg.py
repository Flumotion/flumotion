# -*- Mode: Python; test-case-name: flumotion.test.test_admin_multi -*-
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

from flumotion.common import testsuite

import os
import shutil
from flumotion.common import xdg


class TestXDGConfig(testsuite.TestCase):

    def setUp(self):
        self.old_home = os.environ.get('HOME')
        self.old_xdg_config_home = os.environ.get('XDG_CONFIG_HOME')
        self.old_xdg_config_dirs = os.environ.get('XDG_CONFIG_DIRS')

        self.home = self.mktemp()
        os.mkdir(self.home)
        os.environ['HOME'] = self.home

        self.xdg_config_home = self.mktemp()
        os.mkdir(self.xdg_config_home)
        os.mkdir(os.path.join(self.xdg_config_home, xdg.APPLICATION))
        self.xdg_config_dir1 = self.mktemp()
        os.mkdir(self.xdg_config_dir1)
        os.mkdir(os.path.join(self.xdg_config_dir1, xdg.APPLICATION))
        self.xdg_config_dir2 = self.mktemp()
        os.mkdir(self.xdg_config_dir2)
        os.mkdir(os.path.join(self.xdg_config_dir2, xdg.APPLICATION))
        os.environ['XDG_CONFIG_HOME'] = self.xdg_config_home
        os.environ['XDG_CONFIG_DIRS'] = ':'.join((self.xdg_config_dir1,
                                                  self.xdg_config_dir2))

    def tearDown(self):
        shutil.rmtree(self.home)
        shutil.rmtree(self.xdg_config_home, True)
        shutil.rmtree(self.xdg_config_dir1, True)
        shutil.rmtree(self.xdg_config_dir2, True)
        if self.old_home is not None:
            os.environ['HOME'] = self.old_home
        else:
            del os.environ['HOME']
        if self.old_xdg_config_home is not None:
            os.environ['XDG_CONFIG_HOME'] = self.old_xdg_config_home
        else:
            del os.environ['XDG_CONFIG_HOME']
        if self.old_xdg_config_dirs is not None:
            os.environ['XDG_CONFIG_DIRS'] = self.old_xdg_config_dirs
        else:
            del os.environ['XDG_CONFIG_DIRS']

    def testConfigReadPath(self):
        app = xdg.APPLICATION

        # no such config file exists
        self.assertIdentical(xdg.config_read_path('test'), None)

        # create a config file in the first XDG config dir
        path = os.path.join(self.xdg_config_dir1, app, 'test')
        file(path, 'w').close()
        # should now be found
        self.assertEquals(xdg.config_read_path('test'), path)

        # create a config file in the second XDG config dir, should not change
        # the order
        path2 = os.path.join(self.xdg_config_dir2, app, 'test')
        file(path2, 'w').close()
        self.assertEquals(xdg.config_read_path('test'), path)

        # remove the file from the first XDG config dir, the second one should
        # be found
        os.remove(path)
        self.assertEquals(xdg.config_read_path('test'), path2)

        # create a config file in the XDG home dir, should come first
        path_home = os.path.join(self.xdg_config_home, app, 'test')
        file(path_home, 'w').close()
        self.assertEquals(xdg.config_read_path('test'), path_home)

        # chmod that file 000, should be skipped
        old_perms = os.stat(path_home).st_mode
        os.chmod(path_home, 0000)
        self.assertEquals(xdg.config_read_path('test'), path2)
        os.chmod(path_home, old_perms)

    def testConfigWritePath(self):
        app = xdg.APPLICATION

        # the file should be created
        path = os.path.join(self.xdg_config_home, app, 'write')

        f = xdg.config_write_path('write', 'wb')
        self.assertEquals(f.name, path)
        self.assertEquals(f.mode, 'wb')

        # the subdir should be created
        path = os.path.join(self.xdg_config_home, app, 'subdir', 'write')
        f = xdg.config_write_path('subdir/write')
        self.assertEquals(os.path.isdir(os.path.join(
                    self.xdg_config_home, app, 'subdir')), True)
        self.assertEquals(f.name, path)
        # default mode is 'w'
        self.assertEquals(f.mode, 'w')

        f.write('abc')
        f.close()
        f = xdg.config_write_path('subdir/write', 'a')
        f.write('def')
        f.close()

        self.assertEquals(file(path).read(), 'abcdef')

    def testUnsetHomedir(self):
        app = xdg.APPLICATION

        del os.environ['XDG_CONFIG_HOME']

        # with unset $XDG_CONFIG_HOME, $HOME/.config should be used
        f = xdg.config_write_path('unset', 'w')
        self.assertEquals(f.name, os.path.join(self.home, '.config',
                                               app, 'unset'))
        os.environ['XDG_CONFIG_HOME'] = self.xdg_config_home

    def testNotWritable(self):
        # errors in writing should be reported
        old_perms = os.stat(self.xdg_config_home).st_mode
        os.chmod(self.xdg_config_home, 0000)
        self.assertRaises(OSError, xdg.config_write_path, 'error', 'w')
        os.chmod(self.xdg_config_home, old_perms)
