# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2004,2005,2006 Fluendo, S.L. (www.fluendo.com).
# All rights reserved.

# Licensees having purchased or holding a valid Flumotion Advanced
# Streaming Server license may use this file in accordance with the
# Flumotion Advanced Streaming Server Commercial License Agreement.
# See "LICENSE.Flumotion" in the source distribution for more information.

# Headers in this file shall remain intact.


import common
import time

from twisted.trial import unittest
from flumotion.twisted import integration
httpFileXML = """<?xml version="1.0" ?>
<planet>
  <flow name="default">
    <component type="httpfile" name="httpfile" worker="default">
      <property name="port">12802</property>
      <property name="mount_point">/blah</property>
      <property name="path_to_file">%s</property>
      <property name="type">master</property>
    </component>
  </flow>
</planet>""" % __file__

class TestFlumotion(common.FlumotionManagerWorkerTest):
    def testManagerWorker(self, plan):
        m, w = self.spawnAndWaitManagerWorker(plan)
        plan.kill(w, 0)
        plan.kill(m, 0)
    testManagerWorker = integration.test(testManagerWorker)
    
    def testHttpFile(self, plan):
        m, w = self.spawnAndWaitManagerWorker(plan)
        self.makeFile('httpfile-config.xml', httpFileXML)
        c = plan.spawn('flumotion-command', '-m', 'user:test@localhost:12532',
            'loadconfiguration', 'httpfile-config.xml')
        plan.wait(c, 0)
        happy = plan.spawn('wait-for-component-mood', 
            'user:test@localhost:12532', '/default/httpfile', 'happy')
        plan.wait(happy, 0)
        # wait for httpfile
        h = plan.spawn('wait-for-http-port', 'http://localhost:12802/blah')
        plan.wait(h, 0)
        plan.kill(w, 0)
        plan.kill(m, 0)
    testHttpFile = integration.test(testHttpFile)
