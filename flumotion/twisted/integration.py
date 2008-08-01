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

"""
Framework for writing automated integration tests.

This module provides a way of writing automated integration tests from
within Twisted's unit testing framework, trial. Test cases are
constructed as subclasses of the normal trial
L{twisted.trial.unittest.TestCase} class.

Integration tests look like normal test methods, except that they are
decorated with L{integration.test}, take an extra "plan" argument, and
do not return anything. For example::

  from twisted.trial import unittest
  from flumotion.twisted import integration

  class IntegrationTestExample(unittest.TestCase):
      @integration.test
      def testEchoFunctionality(self, plan):
          process = plan.spawn('echo', 'hello world')
          plan.wait(process, 0)

This example will spawn a process, as if you typed "echo 'hello world'"
at the shell prompt. It then waits for the process to exit, expecting
the exit status to be 0.

The example illustrates two of the fundamental plan operators, spawn and
wait. "spawn" spawns a process. "wait" waits for a process to finish.
The other operators are "spawnPar", which spawns a number of processes
in parallel, "waitPar", which waits for a number of processes in
parallel, and "kill", which kills one or more processes via SIGTERM and
then waits for them to exit.

It is evident that this framework is most appropriate for testing the
integration of multiple processes, and is not suitable for in-process
tests. The plan that is built up is only executed after the test method
exits, via the L{integration.test} decorator; the writer of the
integration test does not have access to the plan's state.

Note that all process exits must be anticipated. If at any point the
integration tester receives SIGCHLD, the next operation must be a wait
for that process. If this is not the case, the test is interpreted as
having failed.

Also note that while the test is running, the stdout and stderr of each
spawned process is redirected into log files in a subdirectory of where
the test is located. For example, in the previous example, the following
files will be created::

  $testdir/IntegrationTestExample-$date/testEchoFunctionality/echo.stdout
  $testdir/IntegrationTestExample-$date/testEchoFunctionality/echo.stderr

In the case that multiple echo commands are run in the same plan, the
subsequent commands will be named as echo-1, echo-2, and the like. Upon
successful completion of the test case, the log directory will be
deleted.
"""

import os
import signal

from twisted.python import failure
from twisted.internet import reactor, protocol, defer
from flumotion.common import log as flog

__version__ = "$Rev$"


# Twisted's reactor.iterate() is defined like this:
#
#     def iterate(self, delay=0):
#        """See twisted.internet.interfaces.IReactorCore.iterate.
#        """
#        self.runUntilCurrent()
#        self.doIteration(delay)
#
# runUntilCurrent runs all the procs on the threadCallQueue. So if
# something is added to the threadCallQueue between runUntilCurrent()
# and doIteration(), the reactor needs to have an fd ready for reading
# to shortcut the select(). This is done by callFromThread() calling
# reactor.wakeUp(), which will write on the wakeup FD.
#
# HOWEVER. For some reason reactor.wakeUp() only writes on the fd if it
# is being called from another thread. This is obviously borked in the
# signal-handling case, when a signal arrives between runUntilCurrent()
# and doIteration(), and is processed via reactor.callFromThread(), as
# is the case with SIGCHLD. So we monkeypatch the reactor to always wake
# the waker. This is twisted bug #1997.
reactor.wakeUp = lambda: reactor.waker and reactor.waker.wakeUp()

def log(format, *args):
    flog.doLog(flog.LOG, None, 'integration', format, args, -2)
def debug(format, *args):
    flog.doLog(flog.DEBUG, None, 'integration', format, args, -2)
def info(format, *args):
    flog.doLog(flog.INFO, None, 'integration', format, args, -2)
def warning(format, *args):
    flog.doLog(flog.WARN, None, 'integration', format, args, -2)
def error(format, *args):
    flog.doLog(flog.ERROR, None, 'integration', format, args, -2)

def _which(executable):
    if os.sep in executable:
        if os.access(os.path.abspath(executable), os.X_OK):
            return os.path.abspath(executable)
    elif os.getenv('PATH'):
        for path in os.getenv('PATH').split(os.pathsep):
            if os.access(os.path.join(path, executable), os.X_OK):
                return os.path.join(path, executable)
    raise CommandNotFoundException(executable)

class UnexpectedExitCodeException(Exception):
    def __init__(self, process, expectedCode, actualCode):
        Exception.__init__(self)
        self.process = process
        self.expected = expectedCode
        self.actual = actualCode
    def __str__(self):
        return ('Expected exit code %r from %r, but got %r'
                % (self.expected, self.process, self.actual))

class UnexpectedExitException(Exception):
    def __init__(self, process):
        Exception.__init__(self)
        self.process = process
    def __str__(self):
        return 'The process %r exited prematurely.' % self.process

class CommandNotFoundException(Exception):
    def __init__(self, command):
        Exception.__init__(self)
        self.command = command
    def __str__(self):
        return 'Command %r not found in the PATH.' % self.command

class ProcessesStillRunningException(Exception):
    def __init__(self, processes):
        Exception.__init__(self)
        self.processes = processes
    def __str__(self):
        return ('Processes still running at end of test: %r'
                % (self.processes, ))

class TimeoutException(Exception):
    def __init__(self, process, status):
        self.process = process
        self.status = status

    def __str__(self):
        return ('Timed out waiting for %r to exit with status %r'
                % (self.process, self.status))

class ProcessProtocol(protocol.ProcessProtocol):
    def __init__(self):
        self.exitDeferred = defer.Deferred()
        self.timedOut = False

    def getDeferred(self):
        return self.exitDeferred

    def timeout(self, process, status):
        info('forcing timeout for process protocol %r', self)
        self.timedOut = True
        self.exitDeferred.errback(TimeoutException(process, status))

    def processEnded(self, status):
        info('process ended with status %r, exit code %r',
             status, status.value.exitCode)
        if self.timedOut:
            warning('already timed out??')
            print 'already timed out quoi?'
        else:
            info('process ended with status %r, exit code %r',
                 status, status.value.exitCode)
            self.exitDeferred.callback(status.value.exitCode)


class Process:
    NOT_STARTED, STARTED, STOPPED = 'NOT-STARTED', 'STARTED', 'STOPPED'

    def __init__(self, name, argv, testDir):
        self.name = name
        self.argv = (_which(argv[0]), ) + argv[1:]
        self.testDir = testDir

        self.pid = None
        self.protocol = None
        self.state = self.NOT_STARTED
        self._timeoutDC = None

        log('created process object %r', self)

    def start(self):
        assert self.state == self.NOT_STARTED

        self.protocol = ProcessProtocol()

        stdout = open(os.path.join(self.testDir, self.name + '.stdout'), 'w')
        stderr = open(os.path.join(self.testDir, self.name + '.stderr'), 'w')
        # don't give it a stdin, output to log files
        childFDs = {1: stdout.fileno(), 2: stderr.fileno()}
        # There's a race condition in twisted.internet.process, whereby
        # signals received between the fork() and exec() in the child
        # are handled with the twisted handlers, i.e. postponed, but
        # they never get called because of the exec(). The end is they
        # are ignored.
        #
        # So, work around that by resetting the sigterm handler to the
        # default so if we self.kill() immediately after self.start(),
        # that the subprocess won't ignore the signal. This is a window
        # in the parent in which SIGTERM will cause immediate
        # termination instead of the twisted nice termination, but
        # that's better than the kid missing the signal.
        info('spawning process %r, argv=%r', self, self.argv)
        termHandler = signal.signal(signal.SIGTERM, signal.SIG_DFL)
        env = dict(os.environ)
        env['FLU_DEBUG'] = '5'
        process = reactor.spawnProcess(self.protocol, self.argv[0],
                                       env=env, args=self.argv,
                                       childFDs=childFDs)
        signal.signal(signal.SIGTERM, termHandler)
        # close our handles on the log files
        stdout.close()
        stderr.close()

        # it's possible the process *already* exited, from within the
        # spawnProcess itself. So set our state to STARTED, *then*
        # attach the callback.
        self.pid = process.pid
        self.state = self.STARTED

        def got_exit(res):
            self.state = self.STOPPED
            info('process %r has stopped', self)
            return res
        self.protocol.getDeferred().addCallback(got_exit)

    def kill(self, sig=signal.SIGTERM):
        assert self.state == self.STARTED
        info('killing process %r, signal %d', self, sig)
        os.kill(self.pid, sig)

    def wait(self, status, timeout=20):
        assert self.state != self.NOT_STARTED
        info('waiting for process %r to exit', self)
        d = self.protocol.getDeferred()
        def got_exit(res):
            debug('process %r exited with status %r', self, res)
            if res != status:
                warning('expected exit code %r for process %r, but got %r',
                        status, self, res)
                raise UnexpectedExitCodeException(self, status, res)
        d.addCallback(got_exit)
        if self.state == self.STARTED:
            self._timeoutDC = reactor.callLater(timeout,
                                                self.protocol.timeout,
                                                self,
                                                status)
            def cancel_timeout(res):
                debug('cancelling timeout for %r', self)
                if self._timeoutDC.active():
                    self._timeoutDC.cancel()
                return res
            d.addCallbacks(cancel_timeout, cancel_timeout)
        return d

    def __repr__(self):
        return '<Process %s in state %s>' % (self.name, self.state)

class PlanExecutor:
    # both the vm and its ops

    def __init__(self):
        self.processes = []
        self.timeout = 20

    def spawn(self, process):
        assert process not in self.processes
        self.processes.append(process)
        process.start()
        return defer.succeed(True)

    def checkExits(self, expectedExits):
        for process in self.processes:
            if (process.state != process.STARTED
                and process not in expectedExits):
                raise UnexpectedExitException(process)

    def kill(self, process):
        assert process in self.processes
        process.kill()
        return defer.succeed(True)

    def wait(self, process, exitCode):
        assert process in self.processes
        def remove_from_processes_list(_):
            self.processes.remove(process)
        d = process.wait(exitCode, timeout=self.timeout)
        d.addCallback(remove_from_processes_list)
        return d

    def _checkProcesses(self, failure=None):
        if self.processes:
            warning('processes still running at end of test: %r',
                    self.processes)
            e = ProcessesStillRunningException(self.processes)
            dlist = []
            # reap all processes, and once we have them reaped, errback
            for p in self.processes:
                if p.state != p.STARTED:
                    continue
                d = defer.Deferred()
                dlist.append(d)
                def callbacker(d):
                    return lambda status: d.callback(status.value.exitCode)
                p.protocol.processEnded = callbacker(d)
                p.kill(sig=signal.SIGKILL)
            d = defer.DeferredList(dlist)
            def error(_):
                if failure:
                    return failure
                else:
                    raise e
            d.addCallback(error)
            return d
        return failure

    def run(self, ops, timeout=20):
        self.timeout = timeout
        d = defer.Deferred()
        def run_op(_, op):
            # print 'Last result: %r' % (_, )
            # print 'Now running: %s(%r)' % (op[0].__name__, op[1:])
            return op[0](*op[1:])
        for op in ops:
            d.addCallback(run_op, op)
        d.addCallbacks(lambda _: self._checkProcesses(failure=None),
                       lambda failure: self._checkProcesses(failure=failure))

        # We should only spawn processes when twisted has set up its
        # sighandlers. It does that *after* firing the reactor startup
        # event and before entering the reactor loop. So, make sure
        # twisted is ready for us by firing the plan in a callLater.
        reactor.callLater(0, d.callback, None)
        return d

class Plan:
    def __init__(self, testCase, testName):
        self.name = testName
        self.testCaseName = testCase.__class__.__name__
        self.processes = {}
        self.outputDir = self._makeOutputDir(os.getcwd())

        # put your boots on monterey jacks, cause this gravy just made a
        # virtual machine whose instructions are python methods
        self.vm = PlanExecutor()
        self.ops = []
        self.timeout = 20

    def _makeOutputDir(self, testDir):
        # ensure that testDir exists
        try:
            os.mkdir(testDir)
        except OSError:
            pass
        tail = '%s-%s' % (self.testCaseName, self.name)
        outputDir = os.path.join(testDir, tail)
        os.mkdir(outputDir)
        return outputDir

    def _cleanOutputDir(self):
        for root, dirs, files in os.walk(self.outputDir, topdown=False):
            for name in files:
                os.remove(os.path.join(root, name))
            for name in dirs:
                os.rmdir(os.path.join(root, name))
        os.rmdir(self.outputDir)
        self.outputDir = None

    def _allocProcess(self, args):
        command = args[0]
        name = command
        i = 0
        while name in self.processes:
            i += 1
            name = '%s-%d' % (command, i)
        process = Process(name, args, self.outputDir)
        self.processes[name] = process
        return process

    def _appendOp(self, *args):
        self.ops.append(args)

    def setTimeout(self, timeout):
        self.timeout = timeout

    def spawn(self, command, *args):
        allArgs = (command, ) + args
        process, = self.spawnPar(allArgs)
        return process

    def spawnPar(self, *argvs):
        processes = []
        self._appendOp(self.vm.checkExits, ())
        for argv in argvs:
            assert isinstance(argv, tuple), \
                   'all arguments to spawnPar must be tuples'
            for arg in argv:
                assert isinstance(arg, str), \
                       'all subarguments to spawnPar must be strings'
            processes.append(self._allocProcess(argv))
        for process in processes:
            self._appendOp(self.vm.spawn, process)
        return tuple(processes)

    def wait(self, process, status):
        self.waitPar((process, status))

    def waitPar(self, *processStatusPairs):
        processes = tuple([p for p, s in processStatusPairs])
        self._appendOp(self.vm.checkExits, processes)
        for process, status in processStatusPairs:
            self._appendOp(self.vm.wait, process, status)

    def kill(self, process, status=None):
        self._appendOp(self.vm.checkExits, ())
        self._appendOp(self.vm.kill, process)
        self._appendOp(self.vm.wait, process, status)

    def execute(self):
        d = self.vm.run(self.ops, timeout=self.timeout)
        d.addCallback(lambda _: self._cleanOutputDir())
        return d

def test(proc):
    testName = proc.__name__
    def wrappedtest(self):
        plan = Plan(self, testName)
        proc(self, plan)
        return plan.execute()
    try:
        wrappedtest.__name__ = testName
    except TypeError:
        # can only set procedure names in python >= 2.4
        pass
    # trial seems to require a timeout, at least in twisted 2.4, so give
    # it a nice one
    wrappedtest.timeout = 666
    return wrappedtest
