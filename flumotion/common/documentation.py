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

"""creating links to online/installed documentation.
Integration with online and installed documentation for messages.
"""

__version__ = "$Rev: 6125 $"

from flumotion.common import common, errors
from flumotion.common.i18n import getLL
from flumotion.configure import configure


def getMessageWebLink(message):
    """
    Get the on-line documentation link target for this message, if any.

    @param message: the message
    @type message: L{flumotion.common.messages.Message}
    """
    if not message.description:
        return None

    from flumotion.project import project
    try:
        projectURL = project.get(message.project, 'docurl')
    except errors.NoProjectError:
        projectURL = None

    return getWebLink(section=message.section,
                      anchor=message.anchor,
                      version=message.version,
                      projectURL=projectURL)


def getWebLink(section, anchor, version=None, projectURL=None):
    """
    Get a documentation link based on the parameters.

    @param section: section, usually the name of the html file
    @type  section: string
    @param  anchor: name of the anchor, part of a section
    @type   anchor: string
    @param  version: optional, version to use. If this is not specified
                     the version from configure.version will be used
    @type   version: string
    @param  projectURL, url for the project this link belongs to.
    @type   projectURL: string
    @returns: the constructed documentation link
    @rtype: string
    """
    if version is None:
        version = configure.version

    # FIXME: if the version has a nano, do something sensible, like
    # drop the nano or always link to trunk version
    versionTuple = version.split('.')
    version = common.versionTupleToString(versionTuple[:3])

    if projectURL is None:
        projectURL = 'http://www.flumotion.net/doc/flumotion/manual'

    return '%s/%s/%s/html/%s.html#%s' % (
        projectURL, getLL(), version, section, anchor)
