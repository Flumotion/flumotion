# -*- Mode: Python; test-case-name: flumotion.test.test_i18n -*-
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

import locale
import gettext
import os

from flumotion.common import testsuite
from flumotion.configure import configure


# marking/translating for singulars
_ = gettext.gettext
def N_(format): return format

# marking for plurals can only be done with a "fake" ngettext
# just adding, say, NP_ to --keyword for xgettext doesn't pick up on
# the plurality

# so we use this global ngettext for marking, and gettext.ngettext for
# actually translating
def ngettext(singular, plural, count): return (singular, plural, count)

# this test uses the class-based gettext API
class TestSingularClassbased(testsuite.TestCase):
    def setUp(self):
        localedir = os.path.join(configure.localedatadir, 'locale')
        mo = gettext.find("flumotion", localedir, ["nl_NL"])
        self.failUnless(mo)
        self.nl = gettext.translation("flumotion", localedir, ["nl_NL"])
        self.failUnless(self.nl)
        self.able = N_("I am a translatable string")
        self.ed = self.nl.gettext("I am a translated string")

    def testTranslatable(self):
        self.assertEquals(self.able, "I am a translatable string")
        self.assertEquals(self.nl.gettext(self.able),
            "Ik ben een vertaalbare string")

    def testTranslated(self):
        self.assertEquals(self.ed, "Ik ben een vertaalde string")

# these tests use the regular gettext API

# helper class for gettext API tests
class TestGettext(testsuite.TestCase):
    def setUp(self):
        self.oldlocaledir = gettext.bindtextdomain('flumotion')
        self.oldlocale = locale.setlocale(locale.LC_MESSAGES)

        # switch to nl
        localedir = os.path.join(configure.localedatadir, 'locale')
        gettext.bindtextdomain('flumotion', localedir)
        gettext.textdomain('flumotion')
        # FIXME: for some reason locale.setlocale does not work, only env
        #locale.setlocale(locale.LC_ALL, "nl_NL")
        os.environ['LANG'] = 'nl_NL'
        # LANGUAGE is a GNU extension that overrides LANG. Ubuntu sets it by
        # default for unknown reasons.
        os.environ['LANGUAGE'] = 'nl_NL'

    def tearDown(self):
        gettext.bindtextdomain('flumotion', self.oldlocaledir)
        locale.setlocale(locale.LC_MESSAGES, self.oldlocale)

class TestSingularGettext(TestGettext):
    def setUp(self):
        TestGettext.setUp(self)
        self.able = N_("I am a translatable string")
        self.ed = _("I am a translated string")

    def testTranslatable(self):
        self.assertEquals(self.able, "I am a translatable string")
        self.assertEquals(gettext.gettext(self.able),
            "Ik ben een vertaalbare string")

    def testTranslated(self):
        self.assertEquals(self.ed, "Ik ben een vertaalde string")

class TestPluralGettext(TestGettext):
    def setUp(self):
        TestGettext.setUp(self)

        self.count = 5
        # use our "fake" ngettext so it gets picked up
        self.ableone = ngettext("I can translate %d thing",
            "I can translate %d things", 1)
        # use the "real" ngettext, from the module, also gets picked up
        self.edone = gettext.ngettext("I translated %d thing",
            "I translated %d things", 1)
        self.ablecount = ngettext("I can translate %d thing",
            "I can translate %d things", self.count)
        self.edcount = gettext.ngettext("I translated %d thing",
            "I translated %d things", self.count)

    def testTranslatable(self):
        self.assertEquals(len(self.ableone), 3)
        self.assertEquals(len(self.ablecount), 3)

        # now translate them
        translated = gettext.ngettext(*self.ableone)
        self.assertEquals(translated, "Ik kan %d ding vertalen")
        self.assertEquals(translated % 1, "Ik kan 1 ding vertalen")

        translated = gettext.ngettext(*self.ablecount)
        self.assertEquals(translated, "Ik kan %d dingen vertalen")
        self.assertEquals(translated % self.count, "Ik kan 5 dingen vertalen")

    def testTranslated(self):
        self.assertEquals(self.edone, "Ik vertaalde %d ding")
        self.assertEquals(self.edone % 1, "Ik vertaalde 1 ding")
        self.assertEquals(self.edcount, "Ik vertaalde %d dingen")
        self.assertEquals(self.edcount % 5, "Ik vertaalde 5 dingen")
