# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2004,2005,2006 Fluendo, S.L. (www.fluendo.com).
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
import signal
import tempfile
from twisted.internet import defer, error, reactor
from twisted.trial import unittest
from flumotion.twisted import integration


def _call_in_reactor(proc):
    # Because twisted doesn't have its signal handlers installed until
    # the reactor is running, we have to wrap the low-level tests in a
    # callLater.
    def test(self):
        d = defer.Deferred()
        d.addCallback(lambda _: proc(self))
        reactor.callLater(0, d.callback, True)
        return d
    test.__name__ = proc.__name__
    return test

class IntegrationProcessTest(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.mkdtemp()

    def tearDown(self):
        for root, dirs, files in os.walk(self.tempdir, topdown=False):
            for name in files:
                os.remove(os.path.join(root, name))
            for name in dirs:
                os.rmdir(os.path.join(root, name))
        os.rmdir(self.tempdir)

    @_call_in_reactor
    def testTransientProcess(self):
        p = integration.Process('echo', ('echo', 'hello world'),
                                self.tempdir)
        assert p.state == p.NOT_STARTED
        p.start()
        assert p.state == p.STARTED
        return p.wait(0)

    @_call_in_reactor
    def testTimeOut(self):
        p = integration.Process('cat', ('cat', '/dev/random'),
                                self.tempdir)
        assert p.state == p.NOT_STARTED
        p.start()
        assert p.state == p.STARTED
        d = p.wait(0, timeout=2)
        self.failUnlessFailure(d, integration.TimeoutException)

        def cleanup(_):
            d = defer.Deferred()
            def processEnded(res):
                d.callback(res)
            # bypass the already-timed-out check
            p.protocol.processEnded = processEnded
            os.kill(p.pid, signal.SIGTERM)
            return d
        d.addCallback(cleanup)
        self.failUnlessFailure(d, error.ProcessTerminated)
        return d
        
    @_call_in_reactor
    def testKill(self):
        p = integration.Process('cat', ('cat', '/dev/random'),
                                self.tempdir)
        assert p.state == p.NOT_STARTED
        p.start()
        assert p.state == p.STARTED
        p.kill()
        d = p.wait(None)
        return d


class IntegrationPlanGenerationTest(unittest.TestCase):
    def assertPlansEqual(self, expected, got):
        if got != expected:
            # pretty-print first
            print 'Got unexpected op plan!'
            print 'Expected:'
            for op in expected:
                print op
            print 'Got:'
            for op in got:
                print op
            self.fail()
        
    def testTransientProcess(self):
        plan = integration.Plan('IntegrationPlanGenerationTest',
                                'testTransientProcess')
        process = plan.spawn('echo', 'hello world')
        plan.wait(process, 0)
        self.assertPlansEqual(plan.ops, [(plan.vm.checkExits, ()),
                                         (plan.vm.spawn, process),
                                         (plan.vm.checkExits, (process,)),
                                         (plan.vm.wait, process, 0)])
        plan._cleanOutputDir()

    def testKill(self):
        plan = integration.Plan('IntegrationPlanGenerationTest',
                                'testKill')
        process = plan.spawn('cat', '/dev/random')
        plan.kill(process)
        self.assertPlansEqual(plan.ops, [(plan.vm.checkExits, ()),
                                         (plan.vm.spawn, process),
                                         (plan.vm.checkExits, ()),
                                         (plan.vm.kill, process),
                                         (plan.vm.wait, process, None)])
        plan._cleanOutputDir()

class IntegrationPlanExecuteTest(unittest.TestCase):
    def testTransientProcess(self):
        plan = integration.Plan('IntegrationPlanExecuteTest',
                                'testTransientProcess')
        process = plan.spawn('echo', 'hello world')
        plan.wait(process, 0)
        return plan.execute()

    def testKill(self):
        plan = integration.Plan('IntegrationPlanExecuteTest',
                                'testKill')
        process = plan.spawn('cat', '/dev/random')
        plan.kill(process)
        return plan.execute()

    def testUnexpectedProcessExit(self):
        plan = integration.Plan('IntegrationPlanExecuteTest',
                                'testUnexpectedProcessExit')
        processes = []
        processes.append(plan.spawn('echo', 'foo'))
        processes.append(plan.spawn('sleep', '5'))
        plan.wait(processes[-1], 0)
        processes.append(plan.spawn('sleep', '5'))
        d = plan.execute()
        self.failUnlessFailure(d, integration.UnexpectedExitException)
        d.addCallback(lambda _: plan._cleanOutputDir())
        return d

    def testUnexpectedExitCode(self):
        plan = integration.Plan('IntegrationPlanExecuteTest',
                                'testUnexpectedExitCode')
        processes = []
        p = plan.spawn('false')
        plan.wait(p, 0)
        d = plan.execute()
        self.failUnlessFailure(d, integration.UnexpectedExitCodeException)
        d.addCallback(lambda _: plan._cleanOutputDir())
        return d

    def testProcessesStillRunning(self):
        plan = integration.Plan('IntegrationPlanExecuteTest',
                                'testProcessesStillRunning')
        p = plan.spawn('sleep', '5')
        d = plan.execute()
        self.failUnlessFailure(d, integration.ProcessesStillRunningException)
        d.addCallback(lambda _: plan._cleanOutputDir())
        return d

class IntegrationTestDecoratorTest(unittest.TestCase):
    @integration.test
    def testTransientProcess(self, plan):
        p = plan.spawn('echo', 'foo')
        plan.wait(p, 0)

    @integration.test
    def testParallelWait(self, plan):
        p1, p2 = plan.spawnPar(('echo', 'foo'),
                               ('echo', 'bar'))
        plan.waitPar((p1, 0),
                     (p2, 0))

    @integration.test
    def testFalse(self, plan):
        p = plan.spawn('false')
        plan.wait(p, 1)

    @integration.test
    def testKill(self, plan):
        p = plan.spawn('cat', '/dev/random')
        plan.kill(p)

    @integration.test
    def testParallelStartAndKill(self, plan):
        p1, p2 = plan.spawnPar(('cat', '/dev/random'),
                               ('cat', '/dev/random'))
        plan.kill(p1, p2)
