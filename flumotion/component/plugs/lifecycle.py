# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2006 Fluendo, S.L. (www.fluendo.com).
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

from flumotion.component.plugs import base

__version__ = "$Rev$"


class ManagerLifecycle(base.ManagerPlug):
    """
    Base class for plugs that are started when the manager is started,
    and stopped when the manager is shut down. ManagerLifecycle plugs
    have no special methods; they are expected to do their interesting
    actions in response to the ManagerPlug start() and stop() methods.
    """


class ManagerLifecyclePrinter(ManagerLifecycle):
    """
    Example implementation of the ManagerLifecyle socket, just prints
    things on the console. Pretty stupid!
    """

    def start(self, vishnu):
        info = vishnu.connectionInfo
        print ('started manager running on %s:%d (%s)'
               % (info['host'], info['port'],
                  info['using_ssl'] and 'with ssl' or 'without ssl'))

    def stop(self, vishnu):
        info = vishnu.connectionInfo
        print ('stopped manager running on %s:%d (%s)'
               % (info['host'], info['port'],
                  info['using_ssl'] and 'with ssl' or 'without ssl'))


class ComponentLifecycle(base.ComponentPlug):
    """
    Base class for plugs that are started when a component is started,
    and stopped when the component is stopped. ComponentLifecycle plugs
    have no special methods; they are expected to do their interesting
    actions in response to the ComponentPlug start() and stop() methods.
    """


class ComponentLifecyclePrinter(ComponentLifecycle):
    """
    Example implementation of the ComponentLifecyle socket, just prints
    things on the console. Pretty stupid!
    """

    def start(self, component):
        print 'Component has been started'

    def stop(self, component):
        print 'Component is stopping'
