# -*- Mode: Python; test-case-name: flumotion.test.test_admin_multi -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2004,2005,2006,2007,2008 Fluendo, S.L. (www.fluendo.com).
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

from flumotion.common import testsuite

import os
import shutil
from flumotion.configure import configure
from flumotion.common import connection, errors, xdg
from flumotion.admin.connections import getRecentConnections
from flumotion.admin.connections import parsePBConnectionInfoRecent


def _create_connection(f, port, host, use_insecure, user, passwd):
    f.write('''<connection>
                 <port>%s</port>
                 <host>%s</host>
                 <use_insecure>%s</use_insecure>
                 <user>%s</user>
                 <passwd>%s</passwd>
               </connection>''' % (port, host, use_insecure,
                                   user, passwd))


class AdminConnectiontionsTest(testsuite.TestCase):

    def setUp(self):
        # create a fake list of recent connection files
        self.old_registrydir = configure.registrydir
        self.new_registrydir = self.mktemp()
        os.mkdir(self.new_registrydir)
        configure.registrydir = self.new_registrydir

        rc1 = file(os.path.join(self.new_registrydir, 'fake.connection'), 'w')
        _create_connection(rc1, 1234, 'test.host.com',
                                  '1', 'testuser', 'testpasswd')
        rc1.close()
        rc2 = file(os.path.join(self.new_registrydir, 'fake2.connection'), 'w')
        _create_connection(rc2, 1235, 'test2.host.com',
                                  '0', 'test2user', 'test2passwd')
        rc2.close()

        # this should not be picked up as a recent connection file
        nrc = file(os.path.join(self.new_registrydir, 'fake3'), 'w')
        _create_connection(nrc, 1236, 'testx.host.com',
                                  '1', 'testxuser', 'testxpasswd')
        nrc.close()

        # create a fake default connections file
        self.old_xdg_config_home = os.environ.get('XDG_CONFIG_HOME')
        self.new_xdg_config_home = self.mktemp()
        os.mkdir(self.new_xdg_config_home)
        os.environ['XDG_CONFIG_HOME'] = self.new_xdg_config_home

        def1 = xdg.config_write_path('connections', 'w')
        def1.write('<connections>')
        _create_connection(def1, '2*', 'test3.host.com',
                                  '1', 'testdefuser', 'testdefpasswd')
        _create_connection(def1, '*', '*.host',
                                  '*', 'x', 'testxpasswd')
        def1.write('</connections>')
        def1.close()

    def tearDown(self):
        shutil.rmtree(self.new_registrydir)
        configure.registrydir = self.old_registrydir

        shutil.rmtree(self.new_xdg_config_home)
        if self.old_xdg_config_home is not None:
            os.environ['XDG_CONFIG_HOME'] = self.old_xdg_config_home
        else:
            del os.environ['XDG_CONFIG_HOME']

    def testGetRecentConnections(self):
        r = getRecentConnections()
        self.assertEquals(len(r), 2)

        # the recent connections are read in reverse lexicographical order
        ci2, ci1 = r[0].info, r[1].info
        self.assertEquals(ci1.port, 1234)
        self.assertEquals(ci1.host, 'test.host.com')
        self.assertEquals(ci1.use_ssl, False)
        self.assertEquals(ci1.authenticator.username, 'testuser')
        self.assertEquals(ci1.authenticator.password, 'testpasswd')
        self.assertEquals(ci2.port, 1235)
        self.assertEquals(ci2.host, 'test2.host.com')
        self.assertEquals(ci2.use_ssl, True)
        self.assertEquals(ci2.authenticator.username, 'test2user')
        self.assertEquals(ci2.authenticator.password, 'test2passwd')

    def testParsePBConnectionRecent(self):
        pPBCIR = parsePBConnectionInfoRecent

        info = pPBCIR('')
        # with an empty manager string we should get the last recent connection
        self.assertEquals(info.port, 1235)
        self.assertEquals(info.host, 'test2.host.com')
        self.assertEquals(info.use_ssl, True)
        self.assertEquals(info.authenticator.username, 'test2user')
        self.assertEquals(info.authenticator.password, 'test2passwd')

        info = pPBCIR('test2.host.com:1235')
        # there is a recent connection for this manager
        self.assertEquals(info.port, 1235)
        self.assertEquals(info.host, 'test2.host.com')
        self.assertEquals(info.use_ssl, True)
        self.assertEquals(info.authenticator.username, 'test2user')
        self.assertEquals(info.authenticator.password, 'test2passwd')

        info = pPBCIR('test.host.com:1234', use_ssl=False)
        self.assertEquals(info.port, 1234)
        self.assertEquals(info.host, 'test.host.com')
        self.assertEquals(info.use_ssl, False)
        self.assertEquals(info.authenticator.username, 'testuser')
        self.assertEquals(info.authenticator.password, 'testpasswd')

        info = pPBCIR('testuser@test.host.com:1234', use_ssl=False)
        self.assertEquals(info.port, 1234)
        self.assertEquals(info.host, 'test.host.com')
        self.assertEquals(info.use_ssl, False)
        self.assertEquals(info.authenticator.username, 'testuser')
        self.assertEquals(info.authenticator.password, 'testpasswd')

        # default connections
        info = pPBCIR('test3.host.com:2234', use_ssl=False)
        self.assertEquals(info.port, 2234)
        self.assertEquals(info.host, 'test3.host.com')
        self.assertEquals(info.use_ssl, False)
        self.assertEquals(info.authenticator.username, 'testdefuser')
        self.assertEquals(info.authenticator.password, 'testdefpasswd')

        info = pPBCIR('x@random.host:1234')
        self.assertEquals(info.port, 1234)
        self.assertEquals(info.host, 'random.host')
        self.assertEquals(info.use_ssl, True)
        self.assertEquals(info.authenticator.username, 'x')
        self.assertEquals(info.authenticator.password, 'testxpasswd')

        # incompatible port
        self.assertRaises(errors.OptionError, pPBCIR, 'test2.host.com:1234')
        self.assertRaises(errors.OptionError, pPBCIR, 'test3.host.com:1234')
        # incompatible SSL settings
        self.assertRaises(errors.OptionError, pPBCIR, 'test.host.com:1234')
        self.assertRaises(errors.OptionError, pPBCIR, 'test3.host.com:2234',
                          use_ssl=True)
        # incompatible user
        self.assertRaises(errors.OptionError, pPBCIR, 'y@test3.host.com:1234')
