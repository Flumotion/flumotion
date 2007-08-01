# -*- Mode: Python -*-
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

import os

import flumotion.common.setup
# logging
flumotion.common.setup.setup()

from flumotion.common import log

def useGtk2Reactor():
    var = 'FLU_TEST_GTK2_REACTOR'

    if var not in os.environ:
        return False
    else:
        return True
        
if useGtk2Reactor():
    log.info('check', 'using gtk2 reactor')
    from twisted.internet import gtk2reactor
    gtk2reactor.install()
else:
    log.info('check', 'using default reactor')

# have to choose the reactor before calling this method
log.logTwisted()

# FIXME: boot.py does this, but enabling this borks
# test_common_package.py. I have no idea what that code does, either.
# 
# # installing the reactor could override our packager's import hooks ...
# from twisted.internet import reactor
# # ... so we install them again here to be safe
# from flumotion.common import package
# package.getPackager().install()

# make sure we have the right gst-python version
from flumotion.common import boot
boot.init_gobject()
boot.init_gst()

# fdpass is a built module,  so it lives in builddir, while the package
# __init__ is in srcdir.  Append to its __path__ to make the tests work 
i = os.getcwd().find('_build')
if i > -1:
    top_builddir = os.path.join(os.getcwd()[:i], '_build')
    from flumotion.extern import fdpass
    fdpass.__path__.append(os.path.join(top_builddir, 'flumotion', 'extern',
        'fdpass'))


from twisted.trial import unittest


managerConf = """
<planet>
<manager name="planet">
    <host>localhost</host>
    <port>0</port>
    <transport>tcp</transport>
    <component name="manager-bouncer" type="htpasswdcrypt-bouncer">
      <property name="data"><![CDATA[
user:PSfNpHTkpTx1M
]]></property>
    </component>
  </manager>
</planet>
"""


# This bit about log flushing is repeated in various tests; would be
# good to see about making it unnecessary. Perhaps returning a pb.Error
# subclass instead of UnauthorizedLogin would do the trick.

def ignoreErrors(*types):
    log._getTheFluLogObserver().ignoreErrors(*types)

def flushErrors(testcase, *types):
    try:
        testcase.flushLoggedErrors(*types)
    except AttributeError:
        from twisted.python import log as tlog
        tlog.flushErrors(*types)
    log._getTheFluLogObserver().clearIgnores()


class TestCaseWithManager(unittest.TestCase):
    def setUp(self):
        from twisted.cred import error
        from flumotion.twisted import pb
        from flumotion.common import config, server, connection
        from flumotion.manager import manager
        from StringIO import StringIO

        # don't output Twisted tracebacks for PB errors we will trigger
        ignoreErrors(error.UnauthorizedLogin)

        conf = config.ManagerConfigParser(StringIO(managerConf)).manager
        self.vishnu = manager.Vishnu(conf.name,
                                     unsafeTracebacks=True)
        self.vishnu.loadManagerConfigurationXML(StringIO(managerConf))
        s = server.Server(self.vishnu)
        if conf.transport == "ssl":
            p = s.startSSL(conf.host, conf.port, conf.certificate,
                           configure.configdir) 
        elif conf.transport == "tcp":
            p = s.startTCP(conf.host, conf.port)
        self.tport = p
        self.port = p.getHost().port
        i = connection.PBConnectionInfo('localhost', self.port,
                                        conf.transport == 'ssl',
                                        pb.Authenticator(username='user',
                                                         password='test'))
        self.connectionInfo = i
        
    def tearDown(self):
        from twisted.cred import error

        flushErrors(self, error.UnauthorizedLogin)

        d = self.vishnu.shutdown()
        d.addCallback(lambda _: self.tport.stopListening())
        return d
