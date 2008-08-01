# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2004,2005,2006,2007 Fluendo, S.L. (www.fluendo.com).
# All rights reserved.

# Licensees having purchased or holding a valid Flumotion Advanced
# Streaming Server license may use this file in accordance with the
# Flumotion Advanced Streaming Server Commercial License Agreement.
# See "LICENSE.Flumotion" in the source distribution for more information.

# Headers in this file shall remain intact.

from twisted.internet import reactor
from twisted.trial import unittest

import os
import string
import random

from flumotion.common import boot
boot.init_gobject()
boot.init_gst()

parts = [os.path.sep, ] + string.split(__file__, os.path.sep)[:-3]
top_src_dir = os.path.join(*parts)

import flumotion.common.setup
# logging
flumotion.common.setup.setup()

from flumotion.common import log
log.debug('integration', 'top_src_dir is %s' % top_src_dir)

# munge the path to include builddir/bin/ and scripts/; also add
# FLU_PROJECT_PATH to the env so that spawned processes pick it up


def mungeEnv():
    from flumotion.configure import configure
    os.environ['PATH'] = os.path.join(top_src_dir, 'scripts') + ':' \
        + os.environ['PATH']
    os.environ['PATH'] = configure.bindir + ':' + os.environ['PATH']
mungeEnv()
log.debug('integration', 'PATH is %s' % os.environ['PATH'])


managerXML = """<!-- -*- Mode: XML -*- -->
<planet>
  <manager name="planet">
    <!-- <host></host> -->
    <debug>4</debug>
    <port>%d</port>
    <component name="manager-bouncer" type="htpasswdcrypt-bouncer">
      <property name="data"><![CDATA[
user:PSfNpHTkpTx1M
]]></property>
    </component>
  </manager>
</planet>
"""

workerXML = """
<worker name="default">
  <manager>
    <host>127.0.0.1</host>
    <port>%d</port>
    <transport>ssl</transport>
  </manager>

  <authentication type="plaintext">
    <username>user</username>
    <password>test</password>
  </authentication>

  <feederports>%d-%d</feederports>
</worker>
"""


class FlumotionManagerWorkerTest(unittest.TestCase):

    def makeFile(self, name, content):
        f = open(name, 'w')
        f.write(content)
        f.close()
        self.__cleanfiles.append(name)

    def loadConfiguration(self, plan, filename):
        c = plan.spawn('flumotion-command', '-m', 'user:test@localhost:%d' %
            self.managerPort, 'loadconfiguration', filename)
        plan.wait(c, 0)

    def stopAll(self, plan):
        # flumotion-command stop will wait for all components it stops
        # to go sleeping before it exits
        c = plan.spawn('flumotion-command', '-m', 'user:test@localhost:%d' %
            self.managerPort, 'stop', '/')
        plan.wait(c, 0)

    def startAll(self, plan):
        # flumotion-command start will wait for all components it starts
        # to go happy or sad before it exits
        c = plan.spawn('flumotion-command', '-m', 'user:test@localhost:%d' %
            self.managerPort, 'start', '/')
        plan.wait(c, 0)

    def waitForHappyComponent(self, plan, componentName):
        happy = plan.spawn('wait-for-component-mood',
            'user:test@localhost:%d' % self.managerPort,
            componentName, 'happy')
        plan.wait(happy, 0)

    def setUp(self):
        self.__cleanfiles = []
        self.managerPort = random.randrange(12530, 12550)
        self.startWorkerPort = random.randrange(12000, 12529)
        self.makeFile('planet.xml', managerXML % self.managerPort)
        self.makeFile('worker.xml', workerXML % (self.managerPort,
            self.startWorkerPort, self.startWorkerPort+2))

    def spawnAndWaitManagerWorker(self, plan):
        m = plan.spawn('flumotion-manager', 'planet.xml')
        p = plan.spawn('wait-for-show-planet',
                       'user:test@localhost:%d' % self.managerPort)
        plan.wait(p, 0)
        w = plan.spawn('flumotion-worker', 'worker.xml')
        wfw = plan.spawn('wait-for-worker',
                         'user:test@localhost:%d' % self.managerPort,
                         'default')
        plan.wait(wfw, 0)
        return m, w

    def tearDown(self):
        for f in self.__cleanfiles:
            os.remove(f)
        self.__cleanfiles = []
