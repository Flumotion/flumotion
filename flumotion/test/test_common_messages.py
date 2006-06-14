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
from twisted.spread import jelly, pb
from twisted.internet import reactor, defer

import common
import testclasses

import os
import gettext

from flumotion.common import messages, log
from flumotion.configure import configure
from flumotion.twisted import flavors
from flumotion.twisted.defer import defer_generator_method

import twisted.copyright #T1.3
#T1.3
def weHaveAnOldTwisted():
    return twisted.copyright.version[0] < '2'

# markers
from flumotion.common.messages import N_, ngettext

# translatablers
T_ = messages.gettexter('flumotion')

class SerializeTest(unittest.TestCase):
    def testSerialize(self):
        text = N_("Something is really wrong.")
        self.cmsg = messages.Error(T_(text))
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
        t = T_(N_("%s can be translated"), "I")
        self.assertEquals(t.domain, "flumotion")
        self.assertEquals(t.format, "%s can be translated")
        self.assertEquals(t.args, ("I", ))

    def testTranslatablePlural(self):
        # Andy 3 is a droid in the Andy series and doesn't need translating
        t = T_(ngettext("%s %d has %d thing", "%s %d has %d things", 5),
            "Andy", 3, 5)
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
        t = T_(N_("%s can be translated"), "Andy")

        translator = messages.Translator()
        localedir = os.path.join(configure.localedatadir, 'locale')
        translator.addLocaleDir('flumotion', localedir)
        text = translator.translateTranslatable(t, lang=["nl_NL"])
        self.assertEquals(text, 'Andy kan vertaald worden')
        
    def testTranslateMessage(self):
        cmsg = messages.Error(T_(N_("Something is really wrong. ")))
        t = T_(N_("But does %s know what ?"), "Andy")
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
      
# test if appending and removing messages works across a PB connection
class TestStateCacheable(flavors.StateCacheable):
    pass
class TestStateRemoteCache(flavors.StateRemoteCache):
    pass
pb.setUnjellyableForClass(TestStateCacheable, TestStateRemoteCache)

class TestRoot(testclasses.TestManagerRoot, log.Loggable):

    logCategory = "testroot"
    
    def setup(self):
        self.translatable = (T_(N_("Note")))
        self.message = messages.Info(self.translatable)
        self.other = messages.Warning(T_(N_("Warning")))

    def remote_getState(self):
        self.state = TestStateCacheable()
        self.state.addListKey('messages')
        return self.state

    def remote_getSameTranslatable(self):
        # return an instance of always the same translatable object
        self.debug("remote_getTranslatable: returning %r" % self.translatable)
        return self.translatable

    def remote_getEqualTranslatable(self):
        # return an instance of a new translatable object, but always equal
        t =  T_(N_("Note"))
        self.debug("remote_getTranslatable: returning %r" % t)
        return t

    def remote_getMessage(self):
        # just return a message, to test serialization
        self.debug("remote_getMessage: returning %r" % self.message)
        return self.message
        
    def remote_appendMessage(self):
        self.state.append('messages', self.message)

    def remote_appendOtherMessage(self):
        self.state.append('messages', self.other)

    def remote_removeMessage(self):
        self.state.remove('messages', self.message)

    def remote_removeOtherMessage(self):
        self.state.remove('messages', self.other)

class PBSerializationTest(unittest.TestCase):
    def setUp(self):
        self.changes = []
        self.runServer()

    def tearDown(self):
        d = self.stopServer()
        if weHaveAnOldTwisted():
            unittest.deferredResult(d)
        else:
            yield d
    tearDown = defer_generator_method(tearDown)
        
    # helper functions to start PB comms
    def runClient(self):
        f = pb.PBClientFactory()
        self.cport = reactor.connectTCP("127.0.0.1", self.port, f)
        d = f.getRootObject()
        d.addCallback(self.clientConnected)
        return d
        #.addCallbacks(self.connected, self.notConnected)
        # self.id = reactor.callLater(10, self.timeOut)

    def clientConnected(self, perspective):
        self.perspective = perspective
        self._dDisconnect = defer.Deferred()
        perspective.notifyOnDisconnect(
            lambda r: self._dDisconnect.callback(None))

    def stopClient(self):
        self.cport.disconnect()
        return self._dDisconnect

    def runServer(self):
        testroot = TestRoot()
        testroot.setup()
        factory = pb.PBServerFactory(testroot)
        factory.unsafeTracebacks = 1
        self.sport = reactor.listenTCP(0, factory, interface="127.0.0.1")
        self.port = self.sport.getHost().port

    def stopServer(self):
        d = self.sport.stopListening()
        return d

    # actual tests
    def testGetSameTranslatableTwice(self):
        # getting the remote translatable twice
        # should result in equal (but not necessarily the same) object
    
        # start everything
        d = self.runClient()
        if weHaveAnOldTwisted():
            unittest.deferredResult(self.runClient())
            dd = self.perspective.callRemote('getSameTranslatable')
            t1 = unittest.deferredResult(dd)
            self.failUnless(t1)

            # get it again
            dd = self.perspective.callRemote('getSameTranslatable')
            t2 = unittest.deferredResult(dd)
            self.failUnless(t2)

            # check if they proxied to objects that are equal, but different
            self.assertEquals(t1, t2)
            self.failUnless(t1 == t2)
            self.failIf(t1 is t2)
         
            # stop
            unittest.deferredResult(self.stopClient())
        else:
            def runClientCallback(result):
                # get the message
                dd = self.perspective.callRemote('getSameTranslatable')
                def getSameTranslatableCallback(t1):
                    self.failUnless(t1)
                    # get it again
                    dd = self.perspective.callRemote('getSameTranslatable')
                    def getSameTranslatableAgainCallback(t2):
                        self.failUnless(t2)
                        # check if they proxied to objects that are equal,
                        # but different
                        self.assertEquals(t1, t2)
                        self.failUnless(t1 == t2)
                        self.failIf(t1 is t2)
         
                        # stop
                        d = self.stopClient()
                        def stopClientCallback(res):
                            pass
                        d.addCallback(stopClientCallback)
                        return d
                    dd.addCallback(getSameTranslatableAgainCallback)
                    return dd
                dd.addCallback(getSameTranslatableCallback)
                return dd
            d.addCallback(runClientCallback)
            return d

    def testGetEqualTranslatableTwice(self):
        # getting two different but equal translatable twice
        # will also result in equal (but not necessarily the same) object
    
        # start everything
        d = self.runClient()
        if weHaveAnOldTwisted():
            unittest.deferredResult(self.runClient())
            # get the message
            d = self.perspective.callRemote('getEqualTranslatable')
            t1 = unittest.deferredResult(d)
            self.failUnless(t1)

            # get it again
            d = self.perspective.callRemote('getEqualTranslatable')
            t2 = unittest.deferredResult(d)
            self.failUnless(t2)

            # check if they proxied to objects that are equal, but different
            self.assertEquals(t1, t2)
            self.failUnless(t1 == t2)
            self.failIf(t1 is t2)
         
            # stop
            unittest.deferredResult(self.stopClient())
        else:
            def runClientCallback(result):
                d = self.perspective.callRemote('getEqualTranslatable')
                def getEqualTranslatableCallback(t1):
                    self.failUnless(t1)
                    d = self.perspective.callRemote('getEqualTranslatable')
                    def getEqualAgainCallback(t2):
                        self.failUnless(t2)
                        self.assertEquals(t1, t2)
                        self.failUnless(t1 == t2)
                        self.failIf(t1 is t2)
                        d = self.stopClient()
                        def stopClientCallback(res):
                            pass
                        d.addCallback(stopClientCallback)
                        return d
                    d.addCallback(getEqualAgainCallback)
                    return d
                d.addCallback(getEqualTranslatableCallback)
                return d
            d.addCallback(runClientCallback)
            return d


    def testGetSameMessageTwice(self):
        # getting two proxied reference of the same ManagerMessage
        # should result in equal, but different objects
    
        # start everything
        d = self.runClient()
        if weHaveAnOldTwisted():
            unittest.deferredResult(self.runClient())
            # get the message
            d = self.perspective.callRemote('getMessage')
            t1 = unittest.deferredResult(d)
            self.failUnless(t1)

            # get it again
            d = self.perspective.callRemote('getMessage')
            t2 = unittest.deferredResult(d)
            self.failUnless(t2)

            # check if they proxied to objects that are equal, but different
            self.assertEquals(t1, t2)
            self.failUnless(t1 == t2)
            self.failIf(t1 is t2)
         
            # stop
            unittest.deferredResult(self.stopClient())
        else:
            def runClientCallback(result):
                d = self.perspective.callRemote('getMessage')
                def getMessageCallback(m1):
                    self.failUnless(m1)
                    d = self.perspective.callRemote('getMessage')
                    def getMessageAgainCallback(m2):
                        self.failUnless(m2)
                        self.assertEquals(m1, m2)
                        self.failUnless(m1 == m2)
                        self.failIf(m1 is m2)
                        d = self.stopClient()
                        def stopClientCallback(res):
                            pass
                        d.addCallback(stopClientCallback)
                        return d
                    d.addCallback(getMessageAgainCallback)
                    return d
                d.addCallback(getMessageCallback)
                return d
            d.addCallback(runClientCallback)
            return d

    def testMessageAppendRemove(self):
        # this is what we eventually want; get the messages removed properly
        # from the list key

        # start everything
        d = self.runClient()

        if weHaveAnOldTwisted():
            unittest.deferredResult(d)
        
            # get the state
            d = self.perspective.callRemote('getState')
            state = unittest.deferredResult(d)

            self.failUnless(state)
            self.assertEqual(len(state.get('messages')), 0)

            # ask server to append a message
            d = self.perspective.callRemote('appendMessage')
            r = unittest.deferredResult(d)

            l = state.get('messages')
            self.assertEquals(len(l), 1)
            self.assertEquals(l[0].level, messages.INFO)

            # ask server to append another message
            d = self.perspective.callRemote('appendOtherMessage')
            r = unittest.deferredResult(d)

            l = state.get('messages')
            self.assertEquals(len(l), 2)
            self.assertEquals(l[0].level, messages.INFO)
            self.assertEquals(l[1].level, messages.WARNING)

            # ask server to remove other message
            d = self.perspective.callRemote('removeOtherMessage')
            r = unittest.deferredResult(d)

            l = state.get('messages')
            self.assertEquals(len(l), 1)
            self.assertEquals(l[0].level, messages.INFO)

            # ask server to remove first message
            d = self.perspective.callRemote('removeMessage')
            r = unittest.deferredResult(d)

            l = state.get('messages')
            self.assertEquals(len(l), 0)

            # stop
            unittest.deferredResult(self.stopClient())
        else:
            def runClientCallback(result):
                d = self.stopClient()
                def stopClientCallback(res):
                    pass
                d.addCallback(stopClientCallback)
                return d
            d.addCallback(runClientCallback)
            return d

if __name__ == '__main__':
    unittest.main()
