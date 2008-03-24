# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2004,2005,2006,2007,2008 Fluendo, S.L. (www.fluendo.com).
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
Integration with online and installed documentation for messages.
"""

__version__ = "$Rev: 6125 $"

from flumotion.common import common, errors

def getMessageWebLink(message, LL=None):
    """
    Get the on-line documentation link target for this message, if any.

    @param LL: language code
    """
    if not message.description:
        return None

    if not LL:
        LL = common.getLL()

    from flumotion.project import project
    docURL = 'http://www.flumotion.net/doc/flumotion/manual'
    try:
        docURL = project.get(message.project, 'docurl')
    except errors.NoProjectError:
        pass

    # FIXME: if the version has a nano, do something sensible, like
    # drop the nano or always link to trunk version
    versionTuple = message.version.split('.')
    version = common.versionTupleToString(versionTuple[:3])
    
    url = '%s/%s/%s/html/%s.html#%s' % (
        docURL, LL, version, message.chapter, message.anchor)

    return url
