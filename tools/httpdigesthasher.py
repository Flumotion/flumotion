#!/usr/bin/python
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


import md5
import sys


def _calculateHA1MD5(username, realm, password):
    """
    Calculate H(A1) as from specification (RFC2617) section 3.2.2, for the
    MD5 algorithm.
    """
    m = md5.md5()
    m.update(username)
    m.update(':')
    m.update(realm)
    m.update(':')
    m.update(password)
    HA1 = m.digest()
    return HA1.encode('hex')

if len(sys.argv) != 3:
    print "Usage: httpdigesthasher.py username password"
else:
    username = sys.argv[1]
    realm = "Flumotion Windows Media Server Component"
    password = sys.argv[2]

    hash = _calculateHA1MD5(username, realm, password)
    print "%s:%s" % (username, hash)
