# -*- Mode: Python -*-
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

from flumotion.component import feedcomponent
from flumotion.common import errors

class SwitchMedium(feedcomponent.FeedComponentMedium):
    def remote_switchToMaster(self):
        return self.comp.switchToMaster()
    
    def remote_switchToBackup(self):
        return self.comp.switchToBackup()

class Switch(feedcomponent.MultiInputParseLaunchComponent):
    logCategory = 'comb-switch'
    componentMediumClass = SwitchMedium

    def init(self):
        self.uiState.addKey("active-eater")
        
    def do_check(self):
        self.debug("checking whether switch element exists")
        from flumotion.worker.checks import check
        d = check.checkPlugin('switch', 'gst-plugins-bad')
        def cb(result):
            for m in result.messages:
                self.addMessage(m)
            d.addCallback(cb)
            return d
        
    def switchToMaster(self):
        raise errors.NotImplementedError('subclasses should implement '
                                         'switchToMaster')

    def switchToBackup(self):
        raise errors.NotImplementedError('subclasses should implement '
                                         'switchToBackup')

    def isActive(self, eaterSubstring):
        # eaterSubstring is "master" or "backup"
        for eaterFeedId in self._inactiveEaters:
            eaterName = self.get_eater_name_for_feedId(eaterFeedId)
            if eaterSubstring in eaterName:
                return False
        return True

class SingleSwitch(Switch):
    logCategory = "comb-single-switch"

    def init(self):
        Switch.init(self)
        self.switchElement = None
        # eater name -> name of sink pad on switch element
        self.switchPads = {}

    def get_pipeline_string(self, properties):
        eaters = self.eater_names

        pipeline = "switch name=switch ! " \
            "identity silent=true single-segment=true name=iden "
        for eater in eaters:
            tmpl = '@ eater:%s @ ! switch. '
            pipeline += tmpl % eater

        pipeline += 'iden.'

        return pipeline

    def configure_pipeline(self, pipeline, properties):
        self.switchElement = sw = pipeline.get_by_name("switch")
        # figure out the pads connected for the eaters
        padPeers = {} # padName -> peer element name
        for sinkPadNumber in range(0, len(self.eater_names)):
            padPeers["sink%d" % sinkPadNumber] = sw.get_pad("sink%d" % (
                sinkPadNumber)).get_peer().get_parent().get_name()

        for feedId in self.eater_names:
            eaterName = self.get_eater_name_for_feedId(feedId)
            self.debug("feedId %s is mapped to eater name %s", feedId, 
                eaterName)
            if eaterName:
                for sinkPad in padPeers:
                    if feedId in padPeers[sinkPad]:
                        self.switchPads[eaterName] = sinkPad
                if not self.switchPads.has_key(eaterName):    
                    self.warning("could not find sink pad for eater %s", 
                        eaterName )
        # make sure switch has the correct sink pad as active
        self.debug("Setting switch's active-pad to %s", 
            self.switchPads["master"])
        self.switchElement.set_property("active-pad", 
            self.switchPads["master"])
        self.uiState.set("active-eater", "master")

    def switchToMaster(self):
        if self.isActive("master"):
            self.switchElement.set_property("active-pad",
                self.switchPads["master"])
            self.uiState.set("active-eater", "master")
        else:
            self.warning("Could not switch to master because the master eater "
                "is not active.")
        
    def switchToBackup(self):
        if self.isActive("backup"):
            self.switchElement.set_property("active-pad",
                self.switchPads["backup"])
            self.uiState.set("active-eater", "backup")
        else:
            self.warning("Could not switch to backup because the backup eater "
                "is not active.")
    

class AVSwitch(Switch):
    logCategory = "comb-av-switch"

    def init(self):
        Switch.init(self)
        self.audioSwitchElement = None
        self.videoSwitchElement = None
        # eater name -> name of sink pad on switch element
        self.switchPads = {}

    def get_pipeline_string(self, properties):
        eaters = self.eater_names

        pipeline = "switch name=vswitch ! " \
            "identity silent=true single-segment=true name=viden " \
            "switch name=aswitch ! " \
            "identity silent=true single-segment=true name=aiden "
        for eater in eaters:
            if "video" in eater:
                tmpl = '@ eater:%s @ ! vswitch. '
            if "audio" in eater:
                tmpl = '@ eater:%s @ ! aswitch. '
            pipeline += tmpl % eater

        pipeline += 'viden. ! @feeder::video@ aiden. ! @feeder::audio@'

        return pipeline

    def configure_pipeline(self, pipeline, properties):
        self.videoSwitchElement = vsw = pipeline.get_by_name("vswitch")
        self.audioSwitchElement = asw = pipeline.get_by_name("aswitch")

        # figure out how many pads should be connected for the eaters
        # 1 + number of eaters with eaterName *-backup
        numVideoPads = 1 + len(self.config["eater"]["video-backup"])
        numAudioPads = 1 + len(self.config["eater"]["audio-backup"]) 
        padPeers = {} # (padName, switchElement) -> peer element name
        for sinkPadNumber in range(0, numVideoPads):
            padPeers[("sink%d" % sinkPadNumber, vsw)] = \
                vsw.get_pad("sink%d" % (
                sinkPadNumber)).get_peer().get_parent().get_name()
        for sinkPadNumber in range(0, numAudioPads):
            padPeers[("sink%d" % sinkPadNumber, asw)] = \
                asw.get_pad("sink%d" % (
                sinkPadNumber)).get_peer().get_parent().get_name()

        for feedId in self.eater_names:
            eaterName = self.get_eater_name_for_feedId(feedId)
            self.debug("feedId %s is mapped to eater name %s", feedId, 
                eaterName)
            if eaterName:
                for sinkPadName, switchElement in padPeers:
                    if feedId in padPeers[(sinkPadName, switchElement)]:
                        self.switchPads[eaterName] = sinkPadName
                if not self.switchPads.has_key(eaterName):
                    self.warning("could not find sink pad for eater %s", 
                        eaterName )
        # make sure switch has the correct sink pad as active
        self.debug("Setting video switch's active-pad to %s", 
            self.switchPads["video-master"])
        vsw.set_property("active-pad", 
            self.switchPads["video-master"])
        self.debug("Setting audio switch's active-pad to %s",
            self.switchPads["audio-master"])
        asw.set_property("active-pad",
            self.switchPads["audio-master"])
        self.uiState.set("active-eater", "master")

    def switchToMaster(self):
        if self.isActive("master"):
            self._setLastTimestamp()
            self.videoSwitchElement.set_property("active-pad",
                self.switchPads["video-master"])
            self.audioSwitchElement.set_property("active-pad",
                self.switchPads["audio-master"])
            self.uiState.set("active-eater", "master")
        else:
            self.warning("Could not switch to master because at least "
                "one of the master eaters is not active.")

        
    def switchToBackup(self):
        if self.isActive("backup"):
            self._setLastTimestamp()
            self.videoSwitchElement.set_property("active-pad",
                self.switchPads["video-backup"])
            self.audioSwitchElement.set_property("active-pad",
                self.switchPads["audio-backup"])
            self.uiState.set("active-eater", "backup")
        else:
            self.warning("Could not switch to backup because at least "
                "one of the backup eaters is not active.")

    def _setLastTimestamp(self):
        vswTs = self.videoSwitchElement.get_property("last-timestamp")
        aswTs = self.audioSwitchElement.get_property("last-timestamp")

        if aswTs > vswTs:
            self.videoSwitchElement.set_property("stop-value",
                aswTs)
        else:
            self.audioSwitchElement.set_property("stop-value",
                vswTs)
