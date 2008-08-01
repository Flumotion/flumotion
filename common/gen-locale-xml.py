# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2004,2005,2006,2007 Fluendo, S.L. (www.fluendo.com).
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

# this script generates a locale registry .xml file for flumotion
# languages are bundled by the two-letter code the locale identifier
# starts with

# usage:
# gen-locale-xml.py [gettext domain] [project name] [one or
#                                                    more language codes]

import os
import sys

def main(args):
    if len(sys.argv) < 2:
        sys.stderr.write('Please specify a gettext domain\n')
        sys.exit(1)
    if len(sys.argv) < 3:
        sys.stderr.write('Please specify a project name\n')
        sys.exit(1)
    if len(sys.argv) < 4:
        sys.stderr.write('Please specify one or more language codes\n')
        sys.exit(1)

    domain = sys.argv[1]
    project = sys.argv[2]
    codes = {} # 2-letter language -> full code
    for code in sys.argv[3:]:
        if len(code) < 2:
            sys.stderr.write('Locale code %s is not at least 2 characters\n'
                % code)
            sys.exit(1)
        lang = code[:2]
        if not lang in codes:
            codes[lang] = []
        codes[lang].append(code)

    print "<registry>"
    print
    print "  <bundles>"
    print

    for lang in codes.keys():
        print ("    <bundle name=\"%s-locale-%s\" "
               "under=\"localedatadir\" project=\"%s\">") % (
            domain, lang, project)
        print "      <directories>"
        print '        <directory name="locale">'
        for code in codes[lang]:
            print ("          <filename location"
                   "=\"%s/LC_MESSAGES/%s.mo\" />") % (
                code, domain)
        print "        </directory>"
        print "      </directories>"
        print "    </bundle>"
        print

    print "  </bundles>"
    print
    print "</registry>"

main(sys.argv)
