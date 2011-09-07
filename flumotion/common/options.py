# -*- Mode: Python; test-case-name: flumotion.test.test_options -*-
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

"""command-line parsing and options
"""

from flumotion.common import common
from flumotion.common import log

# Disable optionparser, it needs more upstream
# changes to work properly
from flumotion.common import boot

__version__ = "$Rev$"

boot.USE_GOPTION_PARSER = False


def OptparseOptionParserClass():
    from optparse import OptionParser as BaseOP

    class OptionParser(BaseOP):

        def __init__(self, usage, description, domain):
            self.domain = domain
            BaseOP.__init__(self, usage=usage, description=description)
    return OptionParser


def OptparseOptionGroupClass():
    from optparse import OptionGroup as BaseOG

    class OptionGroup(BaseOG):

        def __init__(self, parser, title, description=None, **kwargs):
            BaseOG.__init__(self, parser, title, description,
                            **kwargs)
    return OptionGroup


def GOptionOptionParserClass(use_gst):
    from gobject.option import OptionParser as BaseOP

    class OptionParser(BaseOP):

        def __init__(self, usage, description, domain):
            self.domain = domain
            BaseOP.__init__(self, usage=usage, description=description)
            if use_gst:
                try:
                    import pygst
                    pygst.require('0.10')
                    import gstoption
                    self.add_option_group(gstoption.get_group())
                except ImportError:
                    pass
    return OptionParser


def GOptionOptionGroupClass():
    from goption.option import OptionGroup as BaseOG

    class OptionGroup(BaseOG):

        def __init__(self, parser, title, description=None, **kwargs):
            if not description:
                description = title.capitalize() + " options"
            BaseOG.__init__(self, title, description,
                            option_list=[], **kwargs)
    return OptionGroup


def OptionParser(usage="", description="", domain=""):
    """I have two responsibilities:
    - provide a generic interface to OptionParser on top of the optparse
      implementation and the GOption variant.
    - abstract the common command line arguments used by all flumotion
      binaries
    """
    from flumotion.common.boot import USE_GOPTION_PARSER, USE_GST
    if USE_GOPTION_PARSER:
        OptionParser = GOptionOptionParserClass(USE_GST)
    else:
        OptionParser = OptparseOptionParserClass()

    class FOptionParser(OptionParser):

        def __init__(self, usage, description, domain):
            OptionParser.__init__(self, usage, description, domain)
            self._add_common_options()

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

        def parse_args(self, args):
            options, args = OptionParser.parse_args(self, args)

            if options.verbose:
                log.setFluDebug("*:3")

            if options.version:
                print common.version(self.domain)
                import sys
                sys.exit(0)

            if options.debug:
                log.setFluDebug(options.debug)

            return options, args

    return FOptionParser(usage, description, domain)


def OptionGroup(parser, title, description=None, **kwargs):
    from flumotion.common.boot import USE_GOPTION_PARSER
    if USE_GOPTION_PARSER:
        OptionGroup = GOptionOptionGroupClass()
    else:
        OptionGroup = OptparseOptionGroupClass()

    class FOptionGroup(OptionGroup):
        pass
    return FOptionGroup(parser, title, description, **kwargs)
