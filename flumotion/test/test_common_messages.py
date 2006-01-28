# -*- Mode: Python; test-case-name: flumotion.test.test_common_messages -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2004,2005,2006 Fluendo, S.L. (www.fluendo.com).
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

from twisted.trial import unittest
from twisted.spread import jelly
from twisted.internet import reactor

import common

import os
import gettext

from flumotion.common import messages
from flumotion.configure import configure

# markers
from flumotion.common.messages import N_, ngettext

# translatablers
T_ = messages.gettexter('flumotion')
TP_ = messages.ngettexter('flumotion')

class SerializeTest(unittest.TestCase):
    def testSerialize(self):
        t = T_(N_("Something is really wrong."))
        self.cmsg = messages.Error(t)
        self.mmsg = jelly.unjelly(jelly.jelly(self.cmsg))
        t = self.mmsg.translatables[0]
        self.assertEquals(t.format, "Something is really wrong.")
        self.assertEquals(self.mmsg.level, messages.ERROR)
        self.amsg = jelly.unjelly(jelly.jelly(self.mmsg))
        t = self.amsg.translatables[0]
        self.assertEquals(t.format, "Something is really wrong.")
        self.assertEquals(self.amsg.level, messages.ERROR)

    def testCreate(self):
        self.failUnless(messages.Info(T_(N_("Note"))))
        self.failUnless(messages.Warning(T_(N_("warning"))))

class TranslatableTest(unittest.TestCase):
    def testTranslatable(self):
        t = T_(N_("%s can be translated"), ("I", ))
        self.assertEquals(t.domain, "flumotion")
        self.assertEquals(t.format, "%s can be translated")
        self.assertEquals(t.args, ("I", ))

    def testTranslatablePlural(self):
        # Andy 3 is a droid in the Andy series and doesn't need translating
        t = TP_(ngettext("%s %d has %d thing", "%s %d has %d things", 5),
            ("Andy", 3, 5))
        self.assertEquals(t.domain, "flumotion")
        self.assertEquals(t.singular, "%s %d has %d thing")
        self.assertEquals(t.plural, "%s %d has %d things")
        self.assertEquals(t.count, 5)
        self.assertEquals(t.args, ("Andy", 3, 5))
        self.assertEquals(t.plural % t.args, "Andy 3 has 5 things")

        # now translate to nl_NL
        localedir = os.path.join(configure.localedatadir, 'locale')
        self.nl = gettext.translation("flumotion", localedir, ["nl_NL"])
        self.failUnless(self.nl)
        text = self.nl.ngettext(t.singular, t.plural, t.count) % t.args
        self.assertEquals(text, "Andy 3 heeft 5 dingen")

class TranslatorTest(unittest.TestCase):
    def testTranslateOne(self):
        t = T_(N_("%s can be translated"), ("Andy", ))

        translator = messages.Translator()
        localedir = os.path.join(configure.localedatadir, 'locale')
        translator.addLocaleDir('flumotion', localedir)
        text = translator.translateTranslatable(t, lang=["nl_NL"])
        self.assertEquals(text, 'Andy kan vertaald worden')
        
    def testTranslateMessage(self):
        cmsg = messages.Error(T_(N_("Something is really wrong. ")))
        t = T_(N_("But does %s know what ?"), ("Andy", ))
        cmsg.add(t)
        mmsg = jelly.unjelly(jelly.jelly(cmsg))

        translator = messages.Translator()
        localedir = os.path.join(configure.localedatadir, 'locale')
        translator.addLocaleDir('flumotion', localedir)

        text = translator.translate(mmsg, lang=["nl_NL"])
        self.assertEquals(text, "Er is iets echt mis. Maar weet Andy wat ?")

class ResultTest(unittest.TestCase):
    def setUp(self):
        self.translator = messages.Translator()
        localedir = os.path.join(configure.localedatadir, 'locale')
        self.translator.addLocaleDir('flumotion', localedir)

    def testSerializeWithWarning(self):
        wresult = messages.Result()
        wresult.add(messages.Warning(T_(N_("Warning"))))
        wresult.succeed("I did it")

        mresult = jelly.unjelly(jelly.jelly(wresult))
        self.failIf(mresult.failed)
        self.assertEquals(mresult.value, "I did it")
        m = mresult.messages[0]
        self.assertEquals(m.level, messages.WARNING)
        text = self.translator.translate(m, lang=["nl_NL",])
        self.assertEquals(text, "Waarschuwing")

    def testSerializeWithError(self):
        wresult = messages.Result()
        wresult.add(messages.Error(T_(N_("uh oh"))))

        mresult = jelly.unjelly(jelly.jelly(wresult))
        self.failUnless(mresult.failed)
        self.assertEquals(mresult.value, None)
        m = mresult.messages[0]
        self.assertEquals(m.level, messages.ERROR)
        text = self.translator.translate(m, lang=["nl_NL",])
        self.assertEquals(text, "o jeetje")
      
if __name__ == '__main__':
    unittest.main()
