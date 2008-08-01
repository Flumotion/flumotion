#!/usr/bin/python

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
