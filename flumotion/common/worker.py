# -*- Mode: Python; test-case-name: flumotion.test.test_common_worker -*-
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

"""
Objects related to the state of workers.
"""

import os
import signal

from twisted.spread import pb
from twisted.internet import protocol

from flumotion.twisted import flavors
from flumotion.common import log, errors, messages

from flumotion.common.messages import N_
T_ = messages.gettexter('flumotion')

class ProcessProtocol(protocol.ProcessProtocol):
    def __init__(self, loggable, avatarId, processType, machine):
        self.loggable = loggable
        self.avatarId = avatarId
        self.processType = processType # e.g., 'component'
        self.machine = machine # e.g., 'worker 1'

        self.setPid(None)

    def setPid(self, pid):
        self.pid = pid

    def sendMessage(self, message):
        raise NotImplementedError

    def processEnded(self, status):
        # vmethod implementation
        # status is an instance of failure.Failure
        # status.value is a twisted.internet.error.ProcessTerminated
        # status.value.status is the os.WAIT-like status value
        message = None
        obj = self.loggable
        if status.value.exitCode is not None:
            obj.info("Reaped child with pid %d, exit value %d.",
                     self.pid, status.value.exitCode)
        signum = status.value.signal

        # SIGKILL is an explicit kill, and never generates a core dump.
        # For any other signal we want to see if there is a core dump,
        # and warn if not.
        if signum is not None:
            if signum == signal.SIGKILL:
                obj.warning("Child with pid %d killed.", self.pid)
                message = messages.Error(T_(N_("The %s was killed.\n"
                                               % self.processType)))
            else:
                message = messages.Error(T_(N_("The %s crashed.\n"
                                                % self.processType)),
                    debug='Terminated with signal number %d' % signum)

                # use some custom logging depending on signal
                if signum == signal.SIGSEGV:
                    obj.warning("Child with pid %d segfaulted.", self.pid)
                elif signum == signal.SIGTRAP:
                    # SIGTRAP occurs when registry is corrupt
                    obj.warning("Child with pid %d received a SIGTRAP.",
                                self.pid)
                else:
                    # if we find any of these, possibly special-case them too
                    obj.info("Reaped child with pid %d signaled by "
                             "signal %d.", self.pid, signum)
                    
                if not os.WCOREDUMP(status.value.status):
                    obj.warning("No core dump generated. "
                                "Were core dumps enabled at the start ?")
                    message.add(T_(N_(
                        "However, no core dump was generated. "
                        "You may need to configure the environment "
                        "if you want to further debug this problem.")))
                else:
                    obj.info("Core dumped.")
                    corepath = os.path.join(os.getcwd(), 'core.%d' % self.pid)
                    if os.path.exists(corepath):
                        obj.info("Core file is probably '%s'." % corepath)
                        message.add(T_(N_(
                            "The core dump is '%s' on machine '%s'."),
                            corepath, self.machine))
                        # FIXME: add an action that runs gdb and produces a
                        # backtrace; or produce it here and attach to the
                        # message as debug info.

        if message:
            obj.debug('sending message to manager/admin')
            self.sendMessage(message)

        self.setPid(None)

class PortSet(log.Loggable):
    """
    A list of ports that keeps track of which are available for use on a
    given machine.
    """
    def __init__(self, logName, ports):
        self.logName = logName
        self.ports = ports
        self.used = [False] * len(ports)

    def reservePorts(self, numPorts):
        ret = []
        while numPorts > 0:
            if not False in self.used:
                raise errors.ComponentStartError(
                    'could not allocate port on worker %s' % self.logName)
            i = self.used.index(False)
            ret.append(self.ports[i])
            self.used[i] = True
            numPorts -= 1
        return ret

    def releasePorts(self, ports):
        for p in ports:
            try:
                i = self.ports.index(p)
                if self.used[i]:
                    self.used[i] = False
                else:
                    self.warning('releasing unallocated port: %d' % p)
            except ValueError:
                self.warning('releasing unknown port: %d' % p)

    def numFree(self):
        return len(filter(lambda x: not x, self.used))
    
# worker heaven state proxy objects
class ManagerWorkerHeavenState(flavors.StateCacheable):
    """
    I represent the state of the worker heaven on the manager.
    """
    def __init__(self):
        flavors.StateCacheable.__init__(self)
        # FIXME: later on we would want a dict of names -> cacheables ?
        self.addListKey('names', [])

    def __repr__(self):
        return "%r" % self._dict

class AdminWorkerHeavenState(flavors.StateRemoteCache):
    """
    I represent the state of the worker heaven in the admin.
    """
    pass

pb.setUnjellyableForClass(ManagerWorkerHeavenState, AdminWorkerHeavenState)
