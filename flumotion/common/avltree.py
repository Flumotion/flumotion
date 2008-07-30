# -*- Mode: Python; test-case-name: flumotion.test.test_common_messages -*-
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

"""self-balancing binary search tree.
A pure python functional-style self-balancing binary search tree
implementation, with an object-oriented wrapper. Useful for maintaining
sorted sets, traversing sets in order, and closest-match lookups.
"""

__version__ = "$Rev$"


def node(l, v, r, b):
    """Make an AVL tree node, consisting of a left tree, a value, a
    right tree, and the "balance factor": the difference in lengths
    between the right and left sides, respectively."""
    return (l, v, r, b)


def height(tree):
    """Return the height of an AVL tree. Relies on the balance factors
    being consistent."""
    if tree is None:
        return 0
    else:
        l, v, r, b = tree
        if b <= 0:
            return height(l) + 1
        else:
            return height(r) + 1


def debug(tree, level=0):
    """Print out a debugging representation of an AVL tree."""
    if tree is None:
        return
    l, v, r, b = tree
    debug(l, level+1)
    bchr = {-2: '--',
            -1: '-',
            0: '0',
            1: '+',
            2: '++'}.get(b, '?')
    print '%s%s: %r' % ('    '*level, bchr, v)
    debug(r, level+1)


def fromseq(seq):
    """Populate and return an AVL tree from an iterable sequence."""
    t = None
    for x in seq:
        _, t = insert(t, x)
    return t


def _balance(hdiff, l, v, r, b):
    """Internal method to rebalance an AVL tree, called as needed."""
    # if we have to rebalance, in the end the node has balance 0;
    # for details see GNU libavl docs
    if b < -1:
        # rotate right
        ll, lv, lr, lb = l
        if lb == -1:
            # easy case, lv is new root
            new = node(ll, lv, node(lr, v, r, 0), 0)
            if hdiff <= 0:
                # deletion; maybe we decreased in height
                old = node(l, v, r, b)
                hdiff += height(new) - height(old)
            else:
                # we know that for insertion we don't increase in height
                hdiff = 0
            return hdiff, new
        elif lb == 0:
            # can only happen in deletion
            new = node(ll, lv, node(lr, v, r, -1), +1)
            old = node(l, v, r, b)
            hdiff += height(new) - height(old)
            return hdiff, new
        else: # lb == +1
            # lrv will be the new root
            lrl, lrv, lrr, lrb = lr
            if lrb == 0: # lr is the new node
                newleftb = newrightb = 0
            elif lrb == -1:
                newleftb = 0
                newrightb = +1
            else: # lrb == +1
                newleftb = -1
                newrightb = 0
            new = node(node(ll, lv, lrl, newleftb), lrv,
                       node(lrr, v, r, newrightb), 0)
            if hdiff <= 0:
                # deletion; maybe we decreased in height
                old = node(l, v, r, b)
                hdiff += height(new) - height(old)
            else:
                # we know that for insertion we don't increase in height
                hdiff = 0

            return hdiff, new
    elif b > 1:
        # rotate left
        rl, rv, rr, rb = r
        if rb == +1:
            # easy case, rv is new root
            new = node(node(l, v, rl, 0), rv, rr, 0)
            if hdiff <= 0:
                # deletion; maybe we decreased in height
                old = node(l, v, r, b)
                hdiff += height(new) - height(old)
            else:
                # we know that for insertion we don't increase in height
                hdiff = 0
            return hdiff, new
        elif rb == 0:
            # can only happen in deletion
            new = node(node(l, v, rl, +1), rv, rr, -1)
            old = node(l, v, r, b)
            hdiff += height(new) - height(old)
            return hdiff, new
        else: # rb == -1
            # rlv will be the new root
            rll, rlv, rlr, rlb = rl
            if rlb == 0: # rl is the new node
                newleftb = newrightb = 0
            elif rlb == +1:
                newleftb = -1
                newrightb = 0
            else: # rlb == -1
                newleftb = 0
                newrightb = +1
            new = node(node(l, v, rll, newleftb), rlv,
                       node(rlr, rv, rr, newrightb), 0)
            if hdiff <= 0:
                # deletion; maybe we decreased in height
                old = node(l, v, r, b)
                hdiff += height(new) - height(old)
            else:
                # we know that for insertion we don't increase in height
                hdiff = 0
            return hdiff, new
    else:
        return hdiff, node(l, v, r, b)


def insert(tree, value):
    """Insert a value into an AVL tree. Returns a tuple of
    (heightdifference, tree). The original tree is unmodified."""
    if tree is None:
        return 1, (None, value, None, 0)
    else:
        l, v, r, b = tree
        if value < v:
            hdiff, newl = insert(l, value)
            if hdiff > 0:
                if b > 0:
                    hdiff = 0
                b -= 1
            return _balance(hdiff, newl, v, r, b)
        elif value > v:
            hdiff, newr = insert(r, value)
            if hdiff > 0:
                if b < 0:
                    hdiff = 0
                b += 1
            return _balance(hdiff, l, v, newr, b)
        else:
            raise ValueError('tree already has value %r' % (value, ))


def delete(tree, value):
    """Delete a value from an AVL tree. Like L{insert}, returns a tuple
    of (heightdifference, tree). The original tree is unmodified."""

    def popmin((l, v, r, b)):
        if l is None:
            minv = v
            return minv, -1, r
        else:
            minv, hdiff, newl = popmin(l)
            if hdiff != 0:
                if b >= 0:
                    # overall height only changes if left was taller before
                    hdiff = 0
                b += 1

            return (minv, ) + _balance(hdiff, newl, v, r, b)

    if tree is None:
        raise ValueError('tree has no value %r' % (value, ))
    else:
        l, v, r, b = tree
        if value < v:
            hdiff, newl = delete(l, value)
            if hdiff != 0:
                if b >= 0:
                    # overall height only changes if left was
                    # taller before
                    hdiff = 0
                b += 1
            return _balance(hdiff, newl, v, r, b)
        elif value > v:
            hdiff, newr = delete(r, value)
            if hdiff != 0:
                if b <= 0:
                    # overall height only changes if right was
                    # taller before
                    hdiff = 0
                b -= 1
            return _balance(hdiff, l, v, newr, b)
        else:
            # we have found the node!
            if r is None:
                # no right link, just replace with left
                return -1, l
            else:
                newv, hdiff, newr = popmin(r)
                if hdiff != 0:
                    if b <= 0:
                        # overall height only changes if right was
                        # taller before
                        hdiff = 0
                    b -= 1
                return _balance(hdiff, l, newv, newr, b)


def lookup(tree, value):
    """Look up a node in an AVL tree. Returns a node tuple or False if
    the value was not found."""
    if tree is None:
        return False
    else:
        l, v, r, b = tree
        if value < v:
            return lookup(l, v)
        elif value > v:
            return lookup(r, v)
        else:
            return tree


def iterate(tree):
    """Iterate over an AVL tree, starting with the lowest-ordered
    value."""
    if tree is not None:
        l, v, r, b = tree
        for x in iterate(l):
            yield x
        yield v
        for x in iterate(r):
            yield x


def iteratereversed(tree):
    """Iterate over an AVL tree, starting with the highest-ordered
    value."""
    if tree is not None:
        l, v, r, b = tree
        for x in iteratereversed(r):
            yield x
        yield v
        for x in iteratereversed(l):
            yield x


class AVLTree(object):

    def __init__(self, seq=()):
        self._len = len(seq)
        self.tree = fromseq(seq)

    def insert(self, value):
        _, self.tree = insert(self.tree, value)
        self._len += 1

    def delete(self, value):
        _, self.tree = delete(self.tree, value)
        self._len -= 1

    def __contains__(self, value):
        return bool(lookup(self.tree, value))

    def __len__(self):
        return self._len

    def __iter__(self):
        return iterate(self.tree)

    def iterreversed(self):
        return iteratereversed(self.tree)
