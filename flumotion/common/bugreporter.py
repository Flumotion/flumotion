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

"""system information collector and bug reporter"""

import urllib
import webbrowser

from flumotion.common.common import pathToModuleName
from flumotion.common.debug import getVersions
from flumotion.common.python import sorted as STUPID_PYCHECKER_sorted
from flumotion.configure import configure

_BUG_COMPONENT = 'flumotion'
_BUG_KEYWORDS = 'generated'
_BUG_TEMPLATE = """
Please describe what you were doing when the crash happened.

ADD YOUR TEXT HERE

Collected information from your system:

 * Flumotion version: '''%(version)s'''
 * Flumotion SVN revision: [source:flumotion/%(branch)s#%(revision)s r%(revision)s]
%(extra)s
Python Traceback:
{{{
%(traceback)s
}}}
"""
_TRAC_URL = 'https://code.fluendo.com/flumotion/trac'


class BugReporter(object):
    """I am a class that collects information about the system
    and reports the information to the Flumotion bug report system.
    """
    def __init__(self):
        self._baseURL = _TRAC_URL
        self._component = _BUG_COMPONENT
        self._keywords = [_BUG_KEYWORDS]
        self._versions = getVersions()

    def _collectFilenames(self, filenames):
        retval = {}
        for filename in filenames:
            moduleName = pathToModuleName(filename)
            if not moduleName in self._versions:
                continue
            retval[filename] = self._versions[moduleName]
        return retval

    def _processFilenames(self, filenames):
        filenames = self._collectFilenames(filenames)

        extra = ' * Filename revisions:\n'
        for filename in STUPID_PYCHECKER_sorted(filenames.keys()):
            rev = filenames[filename]
            link = '[source:flumotion/%s/%s#%s r%s]' % (
                configure.branchName, filename, rev, rev)
            extra += "   - %s: %s\n" % (filename, link)
        return extra

    def _processTemplate(self, filenames, traceback):
        description = _BUG_TEMPLATE % (
            dict(extra=self._processFilenames(filenames),
                 branch=configure.branchName,
                 revision=max(self._versions.values()),
                 traceback=traceback,
                 version=configure.version))
        return description

    # Public API

    def submit(self, filenames, description, summary):
        """Submits a bug report to trac by opening
        a web browser
        @param filenames: filenames visible in traceback
        @type filenames: list of strings
        @param description: description of the traceback
        @type description: string
        @param summary: summary of the bug report
        @type summary: string
        """
        description = self._processTemplate(filenames, description)
        params = dict(summary=summary,
                      description=description)
        if self._keywords:
            params['keywords'] = ','.join(self._keywords)
        if self._component:
            params['component'] = self._component,

        data = urllib.urlencode(params)
        reportURL = "%s/newticket?%s" % (self._baseURL, data,)
        webbrowser.open_new(reportURL)
