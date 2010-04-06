# -*- Mode: Python; test-case-name: test_command -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Copyright (C) 2006,2007 Thomas Vander Stichele <thomas at apestaart dot org>

# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Street #330, Boston, MA 02111-1307, USA.

import sys
import unittest
import StringIO

import command


class CommandTestCase(unittest.TestCase):

    def testCommandNoName(self):
        c = command.Command()
        self.assertEquals(c.name, "command")


class FakeSubSubCommand(command.Command):
    description = "Fake subsubcommand"
    aliases = "fssc"


class FakeSubCommand(command.Command):
    description = "Fake subcommand"
    subCommandClasses = [FakeSubSubCommand, ]


class FakeCommand(command.Command):
    description = "Fake command"
    subCommandClasses = [FakeSubCommand, ]


class FakeCommandTestCase(unittest.TestCase):

    def setUp(self):
        unittest.TestCase.setUp(self)
        self.out = StringIO.StringIO()
        self.err = StringIO.StringIO()
        self.c = FakeCommand(stdout=self.out, stderr=self.err)
        self.assertEquals(self.c.name, "fakecommand")

    def testHelpCommands(self):
        self.assertEquals(None, self.c.parse(['--help', ]))
        lookFor = "%s  " % self.c.subCommands.keys()[0]
        self.failUnless(self.out.getvalue().find(lookFor) > -1,
            "out %r does not contain %s" % (self.out.getvalue(), lookFor))

    def testNoCommand(self):
        ret = self.c.parse([])
        self.assertEquals(ret, 1)
        self.failIf(self.out.getvalue(), "Should not get output")
        # It seems the F7 version uppercases the first letter, making it Usage
        out = self.err.getvalue()
        self.failUnless(out[1:].startswith('sage:'),
            "output %s does not start with U/usage" % out)


class FakeSubCommandTestCase(unittest.TestCase):

    def setUp(self):
        unittest.TestCase.setUp(self)
        self.out = StringIO.StringIO()
        self.err = StringIO.StringIO()
        self.c = FakeSubCommand(stdout=self.out, stderr=self.err)
        self.assertEquals(self.c.name, "fakesubcommand")

    def testHelpCommands(self):
        self.assertEquals(None, self.c.parse(['--help', ]))
        lookFor = "%s  " % self.c.subCommands.keys()[0]
        self.failUnless(self.out.getvalue().find(lookFor) > -1,
            "out %r does not contain %s" % (self.out.getvalue(), lookFor))


if __name__ == '__main__':
    unittest.main()
