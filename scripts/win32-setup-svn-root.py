# -*- Mode: Python -*-
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


import os
import sys

VERSION = '0.5.2'


def process_template(input, output=None, vardict={}):
    if output is None and input.endswith('.in'):
        output = input[:-3]
    data = open(input).read()
    for key, value in vardict.items():
        data = data.replace(key, value)
    open(output, 'w').write(data)

scriptdir = os.path.dirname(__file__)
svnroot = os.path.abspath(os.path.join(scriptdir, '..'))

vardict = {
     '@LIBDIR@': os.path.join(svnroot),
     '@VERSION@': VERSION,
     }

process_template(os.path.join(svnroot, 'bin', 'flumotion-admin.in'),
                 os.path.join(svnroot, 'bin', 'flumotion-admin.py'),
                 vardict=vardict)
process_template(os.path.join(svnroot, 'flumotion',
                              'configure', 'uninstalled.py.in'),
                 vardict=vardict)
