# -*- Mode: Python; test-case-name:flumotion.test.test_config -*-
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

import random

from flumotion.common import avltree
from flumotion.common import testsuite

attr = testsuite.attr


class TestAVLTree(testsuite.TestCase):

    def assertBalanced(self, tree):
        if tree is None:
            return 0
        l, v, r, b = tree
        lh = self.assertBalanced(l)
        rh = self.assertBalanced(r)
        try:
            self.assertEquals(rh - lh, b, "incorrect balance factor")
        except:
            print 'rh:', rh, 'lh:', lh, 'b:', b
            avltree.debug(tree)
            raise
        self.failIf(b < -1, "unbalanced tree: left side too tall")
        self.failIf(b > 1, "unbalanced tree: right side too tall")
        return max(lh, rh) + 1

    def assertOrdered(self, tree, minv, len):
        n = 0
        for v in avltree.iterate(tree):
            self.failUnless(minv < v)
            minv = v
            n += 1
        self.assertEquals(n, len)

    def testInsertAscendingRemoveAscending(self):
        tree = avltree.AVLTree()

        LEN=40

        for i in range(LEN):
            tree.insert(i)
            self.assertOrdered(tree.tree, -1, i+1)
            self.assertBalanced(tree.tree)

        for i in range(LEN):
            tree.delete(i)
            self.assertOrdered(tree.tree, i, 40-i-1)
            self.assertBalanced(tree.tree)

    def testInsertAscendingRemoveDescending(self):
        tree = avltree.AVLTree()

        LEN=40

        for i in range(LEN):
            tree.insert(i)
            self.assertOrdered(tree.tree, -1, i+1)
            self.assertBalanced(tree.tree)

        for i in range(LEN-1, -1, -1):
            tree.delete(i)
            self.assertOrdered(tree.tree, -1, i)
            self.assertBalanced(tree.tree)

    def testInsertDescendingRemoveDescending(self):
        tree = avltree.AVLTree()

        LEN=40

        for i in range(LEN-1, -1, -1):
            tree.insert(i)
            self.assertOrdered(tree.tree, i-1, LEN-i)
            self.assertBalanced(tree.tree)

        for i in range(LEN-1, -1, -1):
            tree.delete(i)
            self.assertOrdered(tree.tree, -1, i)
            self.assertBalanced(tree.tree)

    def testInsertDescendingRemoveAscending(self):
        tree = avltree.AVLTree()

        LEN=40

        for i in range(LEN-1, -1, -1):
            tree.insert(i)
            self.assertOrdered(tree.tree, i-1, LEN-i)
            self.assertBalanced(tree.tree)

        for i in range(LEN):
            tree.delete(i)
            self.assertOrdered(tree.tree, i, 40-i-1)
            self.assertBalanced(tree.tree)

    @attr('slow')
    def testInsertRandomRemoveRandom(self):
        tree = avltree.AVLTree()

        LEN=200

        values = range(LEN)
        inserted = []
        for i in range(LEN-1, -1, -1):
            v = values.pop(random.randint(0, i))
            inserted.append(v)
            tree.insert(v)
            try:
                self.assertOrdered(tree.tree, -1, LEN-i)
                self.assertBalanced(tree.tree)
            except:
                print 'insertion order:', inserted
                raise

        values = range(LEN)
        for i in range(LEN-1, -1, -1):
            v = values.pop(random.randint(0, i))
            savetree = tree.tree
            tree.delete(v)
            try:
                self.assertOrdered(tree.tree, values and values[0]-1 or -1, i)
                self.assertBalanced(tree.tree)
            except:
                print 'while deleting:', v, 'from:', savetree
                avltree.debug(savetree)
                raise
