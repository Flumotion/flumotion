# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2008 Fluendo, S.L. (www.fluendo.com).
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

"""Virtual File System API.
This module contains the API used to invoke the virtual file system.
The virtual file system is a simple way of listing files, directories
and their metadata.
It's designed to be used over twisted.spread and is thus using deferreds.
"""

from twisted.internet.defer import succeed

from flumotion.common import log

_backends = []


def listDirectory(path):
    """List the directory called path
    @returns: the directory
    @rtype: deferred that will fire an object implementing L{IDirectory}
    """
    global _backends
    if not _backends:
        _registerBackends()
    if not _backends:
        raise AssertionError(
            "there are no vfs backends available")
    backend = _backends[0]
    log.info('vfs', 'listing directory %s using %r' % (path, backend))
    return succeed(backend(path))


def _registerBackends():
    global _backends
    for backend, attributeName in [
        ('flumotion.common.vfsgio', 'GIODirectory'),
        ('flumotion.common.vfsgnome', 'GnomeVFSDirectory'),
        ]:
        try:
            module = __import__(backend, {}, {}, ' ')
        except ImportError:
            log.info('vfs', 'skipping backend %s, dependency missing' % (
                backend, ))
            continue

        log.info('vfs', 'adding backend %s' % (backend, ))
        backend = getattr(module, attributeName)
        try:
            backend('/')
        except ImportError:
            continue
        _backends.append(backend)

    registerVFSJelly()


def registerVFSJelly():
    """Register the jelly used by different backends
    """

    from flumotion.common.vfsgnome import registerGnomeVFSJelly
    registerGnomeVFSJelly()

    from flumotion.common.vfsgio import registerGIOJelly
    registerGIOJelly()

    log.info('jelly', 'VFS registered')
