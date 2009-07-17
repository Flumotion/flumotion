# -*- Mode: Python; test-case-name: flumotion.test.test_config -*-
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

"""
forward compatibility with future python versions
"""

import sys

__version__ = "$Rev$"

# we're possibly redefining some builtins, so don't warn
__pychecker__ = 'no-shadowbuiltin'

# sorted() was introduced in 2.4
if sys.version_info[:2] < (2, 4):

    def sorted(seq, reverse=False):
        seq = seq[:]
        seq.sort()
        if reversed:
            seq = seq[::-1]
        return seq
else:
    sorted = sorted

# any() was introduced in 2.5
if sys.version_info[:2] < (2, 5):

    def any(seq):
        for item in seq:
            if item:
                return True
        return False
else:
    any = any

# all() was introduced in 2.5
if sys.version_info[:2] < (2, 5):

    def all(seq):
        for item in seq:
            if not item:
                return False
        return True
else:
    all = all


# python2.4's os.makedirs() lacks EEXIST checks, so here's almost a
# literal copy from the python2.5's version of os module
if sys.version_info[:2] < (2, 5):
    import os.path as path
    from os import mkdir, curdir
    from errno import EEXIST

    def makedirs(name, mode=0777):
        head, tail = path.split(name)
        if not tail:
            head, tail = path.split(head)
        if head and tail and not path.exists(head):
            try:
                makedirs(head, mode)
            except OSError, e:
                # be happy if someone already created the path
                if e.errno != EEXIST:
                    raise
            if tail == curdir: # xxx/newdir/. exists if xxx/newdir exists
                return
        mkdir(name, mode)
else:
    from os import makedirs

# python 2.6 deprecates sha and md5 modules in favor of hashlib
try:
    _hashlib = __import__("hashlib")
except ImportError:
    from md5 import md5
    from sha import sha as sha1
else:
    from hashlib import md5 as md5
    from hashlib import sha1 as sha1

# python 2.6 deprecated the sets module in favor of a builtin set class
try:
    set = set
except NameError:
    from sets import Set as set
