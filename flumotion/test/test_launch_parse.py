# -*- Mode: Python; test-case-name: flumotion.test.test_common_componentui -*-
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

from flumotion.common.testsuite import TestCase
from flumotion.launch import parse


class TestLaunchParse(TestCase):

    def testParsePlug(self):

        def check(arg, exp):
            self.assertEqual(exp, parse.parse_plug(arg))

        check("\pn", ("pn", []))
        check("\pn,a1=v1,a2=v2",
              ("pn", [("a1", "v1"), ("a2", "v2")]))
        check("\pn,a1=[c1=d1],a2=v2",
              ("pn", [("a1", [("c1", "d1")]), ("a2", "v2")]))
        check("\pn,a1=v1,a2=[c1=d1,c2=d2],a3=v3",
              ("pn", [("a1", "v1"),
                      ("a2", [("c1", "d1"), ("c2", "d2")]),
                      ("a3", "v3")]))
        check("\pn,a1=v1,a2=[c1=d1]",
              ("pn", [("a1", "v1"), ("a2", [("c1", "d1")])]))
        check("\pn,a1=v1,a2=\[c1=d1\]",
              ("pn", [("a1", "v1"), ("a2", "[c1=d1]")]))
        check("\pn,a1=[c1=d1,c2=[e1=[g1=h1],e2=f2]]",
              ("pn", [("a1", [("c1", "d1"),
                              ("c2", [("e1", [("g1", "h1")]),
                                      ("e2", "f2")])])]))

    def testSloppyUnescape(self):

        def check(val, exp):
            self.assertEqual(parse.sloppy_unescape(val, "E"), exp)

        check("", "")
        check("\\", "\\")
        check("\\\\", "\\")
        check("E", "E")
        check("U", "U")
        check("E\\", "E\\")
        check("U\\", "U\\")
        check("\\E", "E")
        check("\\U", "\\U")
        check("\\\\E", "\\E")
        check("\\\\U", "\\U")
        check("\\\\\\E", "\\E")
        check("\\\\\\U", "\\\\U")
        check("\\U\\E\\U\\", "\\UE\\U\\")
        check("\\E\\U\\E\\", "E\\UE\\")
