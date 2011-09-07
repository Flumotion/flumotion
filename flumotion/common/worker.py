# -*- Mode: Python; test-case-name: flumotion.test.test_common_worker -*-
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

"""objects related to the state of workers.
"""

import os
import signal

from twisted.spread import pb
from twisted.internet import protocol

from flumotion.common import log, errors, messages
from flumotion.common.i18n import N_, gettexter
from flumotion.twisted import flavors

__version__ = "$Rev$"
T_ = gettexter()


class ProcessProtocol(protocol.ProcessProtocol):

    def __init__(self, loggable, avatarId, processType, where):
        self.loggable = loggable
        self.avatarId = avatarId
        self.processType = processType # e.g., 'component'
        self.where = where # e.g., 'worker 1'

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
        pid = None
        # if we have a pid, then set pid to string value of pid
        # otherwise set to "unknown"
        if self.pid:
            pid = str(self.pid)
        else:
            pid = "unknown"
        if status.value.exitCode is not None:
            obj.info("Reaped child with pid %s, exit value %d.",
                     pid, status.value.exitCode)
        signum = status.value.signal

        # SIGKILL is an explicit kill, and never generates a core dump.
        # For any other signal we want to see if there is a core dump,
        # and warn if not.
        if signum is not None:
            if signum == signal.SIGKILL:
                obj.warning("Child with pid %s killed.", pid)
                message = messages.Error(T_(N_("The %s was killed.\n"),
                                               self.processType))
            else:
                message = messages.Error(T_(N_("The %s crashed.\n"),
                                                self.processType),
                    debug='Terminated with signal number %d' % signum)

                # use some custom logging depending on signal
                if signum == signal.SIGSEGV:
                    obj.warning("Child with pid %s segfaulted.", pid)
                elif signum == signal.SIGTRAP:
                    # SIGTRAP occurs when registry is corrupt
                    obj.warning("Child with pid %s received a SIGTRAP.",
                                pid)
                else:
                    # if we find any of these, possibly special-case them too
                    obj.info("Reaped child with pid %s signaled by "
                             "signal %d.", pid, signum)

                if not os.WCOREDUMP(status.value.status):
                    obj.warning("No core dump generated. "
                                "Were core dumps enabled at the start ?")
                    message.add(T_(N_(
                        "However, no core dump was generated. "
                        "You may need to configure the environment "
                        "if you want to further debug this problem.")))
                    #message.description = T_(N_(
                    #    "Learn how to enable core dumps."))
                else:
                    obj.info("Core dumped.")
                    corepath = os.path.join(os.getcwd(), 'core.%s' % pid)
                    if os.path.exists(corepath):
                        obj.info("Core file is probably '%s'." % corepath)
                        message.add(T_(N_(
                            "The core dump is '%s' on the host running '%s'."),
                            corepath, self.where))
                        # FIXME: add an action that runs gdb and produces a
                        # backtrace; or produce it here and attach to the
                        # message as debug info.
                        message.description = T_(N_(
                            "Learn how to analyze core dumps."))
                        message.section = 'chapter-debug'
                        message.anchor = 'section-os-analyze-core-dumps'

        if message:
            obj.debug('sending message to manager/admin')
            self.sendMessage(message)

        self.setPid(None)


class PortSet(log.Loggable):
    """
    A list of ports that keeps track of which are available for use on a
    given machine.
    """
    # not very efficient mkay

    def __init__(self, logName, ports, randomPorts=False):
        self.logName = logName
        self.ports = ports
        self.used = [0] * len(ports)
        self.random = randomPorts

    def reservePorts(self, numPorts):
        ret = []
        while numPorts > 0:
            if self.random:
                ret.append(0)
                numPorts -= 1
                continue
            if not 0 in self.used:
                raise errors.ComponentStartError(
                    'could not allocate port on worker %s' % self.logName)
            i = self.used.index(0)
            ret.append(self.ports[i])
            self.used[i] = 1
            numPorts -= 1
        return ret

    def setPortsUsed(self, ports):
        for port in ports:
            try:
                i = self.ports.index(port)
            except ValueError:
                self.warning('portset does not include port %d', port)
            else:
                if self.used[i]:
                    self.warning('port %d already in use!', port)
                else:
                    self.used[i] = 1

    def releasePorts(self, ports):
        """
        @param ports: list of ports to release
        @type  ports: list of int
        """
        for p in ports:
            try:
                i = self.ports.index(p)
                if self.used[i]:
                    self.used[i] = 0
                else:
                    self.warning('releasing unallocated port: %d' % p)
            except ValueError:
                self.warning('releasing unknown port: %d' % p)

    def numFree(self):
        return len(self.ports) - self.numUsed()

    def numUsed(self):
        return len(filter(None, self.used))

# worker heaven state proxy objects


class ManagerWorkerHeavenState(flavors.StateCacheable):
    """
    I represent the state of the worker heaven on the manager.

    I have the following keys:

     - names   (list): list of worker names that we have state for
     - workers (list): list of L{ManagerWorkerState}
    """

    def __init__(self):
        flavors.StateCacheable.__init__(self)
        self.addListKey('names', [])
        self.addListKey('workers', []) # should be a dict

    def __repr__(self):
        return "%r" % self._dict


class AdminWorkerHeavenState(flavors.StateRemoteCache):
    """
    I represent the state of the worker heaven in the admin.
    See L{ManagerWorkerHeavenState}
    """
    pass

pb.setUnjellyableForClass(ManagerWorkerHeavenState, AdminWorkerHeavenState)


class ManagerWorkerState(flavors.StateCacheable):
    """
    I represent the state of a worker in the manager.

     - name: name of the worker
     - host: the IP address of the worker as seen by the manager
    """

    def __init__(self, **kwargs):
        flavors.StateCacheable.__init__(self)
        self.addKey('name')
        self.addKey('host')
        for k, v in kwargs.items():
            self.set(k, v)

    def __repr__(self):
        return ("<ManagerWorkerState for %s on %s>"
                % (self.get('name'), self.get('host')))


class AdminWorkerState(flavors.StateRemoteCache):
    """
    I represent the state of a worker in the admin.

    See L{ManagerWorkerState}
    """
    pass

pb.setUnjellyableForClass(ManagerWorkerState, AdminWorkerState)
