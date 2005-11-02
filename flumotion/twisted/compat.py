# -*- Mode: Python; test-case-name: flumotion.test.test_compat -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2004,2005 Fluendo, S.L. (www.fluendo.com). All rights reserved.

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
Flumotion Twisted compatibility assistance
"""

import warnings

def filterWarnings(namespace, category):
    """
    Filter the given warnings category from the given namespace if it exists.

    @type  category: string
    """
    if not hasattr(namespace, category):
        return
    c = getattr(namespace, category)
    warnings.filterwarnings('ignore', category=c)

def install_reactor(gtk=False):
    from twisted.copyright import version
    if version[0] >= '2':
        from twisted.internet import gtk2reactor as Reactor
    else:
        from flumotion.twisted import gtk2reactor as Reactor

    Reactor.install(useGtk=gtk)

    # this monkeypatched var exists to let reconnecting factories know
    # when they should warn about a connection being closed, and when
    # they shouldn't because the system is shutting down.
    # 
    # there is no race condition here -- the reactor doesn't handle
    # signals until it is run().
    from twisted.internet import reactor
    reactor.killed = False
    def setkilled(killed):
        reactor.killed = killed
    reactor.addSystemEventTrigger('before', 'startup', setkilled, False)
    reactor.addSystemEventTrigger('before', 'shutdown', setkilled, True)

    if version[0] >= '2':
        from twisted.names import client
        # avoid spawning threads -- the normal resolver spawns threads
        reactor.installResolver(client.createResolver())
