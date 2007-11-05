# -*- Mode: Python; test-case-name: flumotion.test.test_options -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2007 Fluendo, S.L. (www.fluendo.com).
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

"""Command-line options
"""

import sys

from flumotion.common import common
from flumotion.common import log
from flumotion.common.boot import init_gobject
init_gobject()

import gobject

# We should only use GOption if we can find a recent enough
# version of pygobject on our system. There were bugs in
# the GOption parsing until pygobject 2.15.0, so just
# revert to optparse if our pygobject is too old
USE_GOPTION = (getattr(gobject, 'pygobject_version', ()) >= (2, 15, 0))
if USE_GOPTION:
    from gobject.option import (OptionParser as BaseOP,
                                OptionGroup as BaseOG)
else:
    from optparse import (OptionParser as BaseOP,
                          OptionGroup as BaseOG)


class OptionParser(BaseOP):
    """I have two responsibilities:
    - provide a generic interface to OptionParser on top of the optparse
      implementation and the GOption variant.
    - abstract the common command line arguments used by all flumotion
      binaries
    """
    def __init__(self, usage="", description="", domain=""):
        self.domain = domain
        BaseOP.__init__(self, usage=usage, description=description)
        self._add_common_options()
        self._add_gst_options()

    def _add_common_options(self):
        self.add_option('-d', '--debug',
                        action="store", type="string", dest="debug",
                        help="set debug levels")
        self.add_option('-v', '--verbose',
                        action="store_true", dest="verbose",
                        help="be verbose")
        self.add_option('', '--version',
                        action="store_true", dest="version",
                        default=False,
                        help="show version information")

    def _add_gst_options(self):
        if not USE_GOPTION:
            return
        try:
            import pygst
            pygst.require('0.10')
            import gstoption
        except ImportError:
            return

        self.add_option_group(gstoption.get_group())

    def parse_args(self, args):
        options, args = BaseOP.parse_args(self, args)

        if options.verbose:
            log.setFluDebug("*:3")

        if options.version:
            print common.version(self.domain)
            sys.exit(0)

        if options.debug:
            log.setFluDebug(options.debug)

        return options, args


class OptionGroup(BaseOG):
    def __init__(self, parser, title, description=None, **kwargs):
        if USE_GOPTION:
            if not description:
                description = title.capitalize() + " options"
            BaseOG.__init__(self, title, description, option_list=[], **kwargs)
        else:
            BaseOG.__init__(self, parser, title, description, **kwargs)
# -*- Mode: Python; test-case-name: flumotion.test.test_options -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2007 Fluendo, S.L. (www.fluendo.com).
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

"""Command-line options
"""

import sys

from flumotion.common import common
from flumotion.common import log
from flumotion.common.boot import init_gobject
init_gobject()

import gobject

# We should only use GOption if we can find a recent enough
# version of pygobject on our system. There were bugs in
# the GOption parsing until pygobject 2.15.0, so just
# revert to optparse if our pygobject is too old
USE_GOPTION = (gobject.pygobject_version >= (2, 15, 0))
if USE_GOPTION:
    from gobject.option import (OptionParser as BaseOP,
                                OptionGroup as BaseOG)
else:
    from optparse import (OptionParser as BaseOP,
                          OptionGroup as BaseOG)


class OptionParser(BaseOP):
    """I have two responsibilities:
    - provide a generic interface to OptionParser on top of the optparse
      implementation and the GOption variant.
    - abstract the common command line arguments used by all flumotion
      binaries
    """
    def __init__(self, usage="", description="", domain=""):
        self.domain = domain
        BaseOP.__init__(self, usage=usage, description=description)
        self._add_common_options()
        self._add_gst_options()

    def _add_common_options(self):
        self.add_option('-d', '--debug',
                        action="store", type="string", dest="debug",
                        help="set debug levels")
        self.add_option('-v', '--verbose',
                        action="store_true", dest="verbose",
                        help="be verbose")
        self.add_option('', '--version',
                        action="store_true", dest="version",
                        default=False,
                        help="show version information")

    def _add_gst_options(self):
        if not USE_GOPTION:
            return
        try:
            import pygst
            pygst.require('0.10')
            import gstoption
        except ImportError:
            return

        self.add_option_group(gstoption.get_group())

    def parse_args(self, args):
        options, args = BaseOP.parse_args(self, args)

        if options.verbose:
            log.setFluDebug("*:3")

        if options.version:
            print common.version(self.domain)
            sys.exit(0)

        if options.debug:
            log.setFluDebug(options.debug)

        return options, args


class OptionGroup(BaseOG):
    def __init__(self, parser, title, description=None, **kwargs):
        if USE_GOPTION:
            if not description:
                description = title.capitalize() + " options"
            BaseOG.__init__(self, title, description, option_list=[], **kwargs)
        else:
            BaseOG.__init__(self, parser, title, description, **kwargs)
