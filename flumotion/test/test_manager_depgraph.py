# -*- Mode: Python; test-case-name: flumotion.test.test_dag -*-
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

import common

from twisted.trial import unittest

from flumotion.manager.depgraph import DepGraph
from flumotion.common import planet, log, errors

class testDepGraph(unittest.TestCase):
    def _createComponent(self, defs):
        ret = planet.ManagerComponentState()

        ret.set("name", defs[0])
        ret.set("type", defs[1])
        ret.set("workerRequested", defs[2])
        
        # now handle eaters and feeders
        conf = {}
        
        source = []
        for eater in defs[4]:
            source.append(eater)
        
        conf["eater"] = {"default":source}

        ret.set("config", conf)
        return ret

        
    def testVideoOnlyOnOneWorker(self):
        """
        I test the simple videotest -> video encoder -> muxer -> httpstreamer
        with clock master set to videotest
        """
        
        dg = DepGraph()
        videotest_defs = ["video-test", "videotest", "default", 
            ["video-test:default"], [] ]
        videoenc_defs = ["video-encoder", "theora-encoder", "default",
            ["video-encoder:default"], ["video-test:default"] ]
        muxer_defs = ["muxer-video", "ogg-muxer", "default",
            ["muxer-video:default"], ["video-encoder:default"] ]
        streamer_defs = ["http-video", "http-streamer", "default", [],
            ["muxer-video:default"]]
        
        videotest = self._createComponent(videotest_defs)
        videoenc = self._createComponent(videoenc_defs)
        muxer = self._createComponent(muxer_defs)
        streamer = self._createComponent(streamer_defs)
        
        dg.addComponent(videotest)
        dg.addComponent(videoenc)
        dg.addComponent(muxer)
        dg.addComponent(streamer)
        dg.addClockMaster(videotest)
        dg.mapEatersToFeeders()
        
        # now check depgraph is correct
        startorder = dg._dag.sort()
        # check worker is the first node in the depgraph
        self.failUnless(startorder[0] == ("default", "WORKER"))
        # now check that the jobs are before the componentsetup
        # and componentsetup before componentready
        # and componentsetup before the eaters and feeders in that component
        # and eaters and feeders before componentready
        # and componentready before any clock master in that component
        for node in startorder:
            if node[1] == "JOB":
                jobindex = startorder.index(node)
                for postnode in startorder:
                    if postnode == (node[0], "COMPONENTSETUP"):
                        postindex = startorder.index(postnode)
                        self.failUnless(postindex > jobindex)
                    elif postnode == (node[0], "CLOCKMASTER"):
                        postindex = startorder.index(postnode)
                        self.failUnless(postindex > jobindex)
            # now check that the clock master is before all the component happy
            elif node[1] == "CLOCKMASTER":
                clockindex = startorder.index(node)
                for happynode in startorder:
                    if happynode[1] == "COMPONENTSTART":
                        happyindex = startorder.index(happynode)
                        self.failUnless(happyindex > clockindex)
        
            # now check that componentsetup before componentstart
            # also check the feeders are before their respective eaters
            elif node[1] == "COMPONENTSETUP":
                setupindex = startorder.index(node)
                # feeders = 
                for postnode in startorder:
                    if postnode == (node[0], "COMPONENTSTART"):
                        postindex = startorder.index(postnode)
                        self.failUnless(postindex > jobindex)
                    #elif postnode[1] == dg.EATER and postnode[0].component == node[0]:
                    #    postindex = startorder.index(postnode)
                    #    self.failUnless(postindex > jobindex)
                    #elif postnode[1] == dg.FEEDER and postnode[0].component == node[0]:
                    #    postindex = startorder.index(postnode)
                    #    self.failUnless(postindex > jobindex)
                        
        # Nothing should be started yet, because no workers logged in
        tobestarted = dg.whatShouldBeStarted()
        self.assertEquals(len(tobestarted), 0)
        dg.setWorkerStarted("default")
        
        # What is told to be started should be everything except the worker
        # which is already started
        #tobestarted = dg.whatShouldBeStarted()
        #self.assertEquals(len(tobestarted), len(startorder)-1)
        #dg.setJobStarted(videotest)
        #tobestarted = dg.whatShouldBeStarted()
        #self.assertEquals(len(tobestarted), len(startorder)-2)
        #self.failUnless((videotest, "JOB") not in tobestarted)

        dg.setJobStarted(videoenc)
        dg.setJobStarted(muxer)
        dg.setJobStarted(streamer)
        tobestarted = dg.whatShouldBeStarted()
        # go through tobestarted and check if state of all is 0
        for obj in tobestarted:
            self.failUnless(dg._state[obj] == False)
        
    def testBrokenDepGraph(self):
        dg = DepGraph()
        videotest_defs = ["video-test", "videotest", "default", ["video-test:default"], []]
        muxer_defs = ["muxer-video", "ogg-muxer", "default", ["muxer-video:default"],
            ["video-encoder:default"]]

        videotest = self._createComponent(videotest_defs)
        muxer = self._createComponent(muxer_defs)

        self.assertRaises(KeyError, dg.addClockMaster, videotest)
        dg.addComponent(videotest)
        dg.addComponent(muxer)
        # lets be naughty and try to mapEatersToFeeders before whole flow is in
        self.assertRaises(errors.ComponentConfigError, dg.mapEatersToFeeders)

    def testCleaningDepgraph(self):
        dg = DepGraph()
        videotest_defs = ["video-test", "videotest", "default", 
            ["video-test:default"], [] ]
        videoenc_defs = ["video-encoder", "theora-encoder", "default",
            ["video-encoder:default"], ["video-test:default"] ]
        muxer_defs = ["muxer-video", "ogg-muxer", "default",
            ["muxer-video:default"], ["video-encoder:default"] ]
        streamer_defs = ["http-video", "http-streamer", "default", [],
            ["muxer-video:default"]]
        
        videotest = self._createComponent(videotest_defs)
        videoenc = self._createComponent(videoenc_defs)
        muxer = self._createComponent(muxer_defs)
        streamer = self._createComponent(streamer_defs)
        
        dg.addComponent(videotest)
        dg.addComponent(videoenc)
        dg.addComponent(muxer)
        dg.addComponent(streamer)
        dg.addClockMaster(videotest)
        dg.mapEatersToFeeders()
        
        # now cleanup depgraph
        dg.removeComponent(videotest)
        dg.removeComponent(streamer)
        dg.removeComponent(muxer)
        dg.removeComponent(videoenc)

        started = dg.whatShouldBeStarted()
        assert(len(started) == 0)
        # let's make sure worker has no children
        assert(dg._dag.hasNode("default", "WORKER"))
        workerchildren = dg._dag.getChildrenTyped("default", "WORKER")
        assert(len(workerchildren) == 0)
        # make sure there are no nodes with children
        for node in dg._dag._nodes.values():
            assert(len(node.children) == 0)
            assert(len(node.parents) == 0)
        # make sure offspring is 0
        for node in dg._dag._nodes:
            assert(dg._dag.getOffspringTyped(node[0], node[1]) == [])
        # sort and see if everything is fine
        for node in dg._dag.sort():
            assert(dg._dag.hasNode(node[0], node[1]))
        
        dg.addComponent(videotest)
        dg.addComponent(videoenc)
        dg.addComponent(muxer)
        dg.addComponent(streamer)
        dg.addClockMaster(videotest)
        dg.mapEatersToFeeders()
        
        # Nothing should be started yet, because no workers logged in
        tobestarted = dg.whatShouldBeStarted()
        self.assertEquals(len(tobestarted), 0)
        dg.setWorkerStarted("default")

        startorder = dg.whatShouldBeStarted()
        # now check that the jobs are before the componentsetup
        # and componentsetup before componentready
        # and componentready before any clock master in that component
        for node in startorder:
            if node[1] == "JOB":
                jobindex = startorder.index(node)
                for postnode in startorder:
                    if postnode == (node[0], "COMPONENTSETUP"):
                        postindex = startorder.index(postnode)
                        self.failUnless(postindex > jobindex)
                    elif postnode == (node[0], "CLOCKMASTER"):
                        postindex = startorder.index(postnode)
                        self.failUnless(postindex > jobindex)
            # now check that the clock master is before all the component happy
            elif node[1] == "CLOCKMASTER":
                clockindex = startorder.index(node)
                for happynode in startorder:
                    if happynode[1] == "COMPONENTSTART":
                        happyindex = startorder.index(happynode)
                        self.failUnless(happyindex > clockindex)
        
            # now check that componentsetup before componentstart
            # also check the feeders are before their respective eaters
            elif node[1] == "COMPONENTSETUP":
                setupindex = startorder.index(node)
                # feeders = 
                for postnode in startorder:
                    if postnode == (node[0], "COMPONENTSTART"):
                        postindex = startorder.index(postnode)
                        self.failUnless(postindex > jobindex)

