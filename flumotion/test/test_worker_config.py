# -*- Mode: Python; test-case-name:flumotion.test.test_worker_config -*-
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
from flumotion.worker import config


class WorkerConfigTest(testsuite.TestCase):

    def testRandomFeederPorts(self):
        conf = config.WorkerConfigXML(None, string="""
<worker>

    <debug>4</debug>

  <manager>
    <host>localhost</host>
    <port>7531</port>
  </manager>

  <authentication type="plaintext">
    <username>user</username>
    <password>test</password>
  </authentication>

  <feederports random="True" />

</worker>
""")
        self.failUnless(conf.randomFeederports)
