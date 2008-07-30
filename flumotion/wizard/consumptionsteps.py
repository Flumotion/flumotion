# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2004,2005,2006,2007,2008 Fluendo, S.L. (www.fluendo.com).
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

import gettext

from flumotion.common.python import any as pany
from flumotion.configure import configure
from flumotion.ui.wizard import WizardStep
from flumotion.wizard.httpstreamersteps import HTTPBothStep, HTTPAudioStep, \
     HTTPVideoStep
from flumotion.wizard.diskersteps import DiskBothStep, DiskAudioStep, \
     DiskVideoStep
from flumotion.wizard.models import Porter
from flumotion.wizard.shout2steps import Shout2BothStep, Shout2AudioStep, \
     Shout2VideoStep
from flumotion.wizard.workerstep import WorkerWizardStep

__version__ = "$Rev$"
_ = gettext.gettext


class HTTPCommon(object):
    def __init__(self):
        self.has_client_limit = False
        self.has_bandwidth_limit = False
        self.client_limit = 1000
        self.bandwidth_limit = 500.0
        self.burst_on_connect = False


class ConsumptionStep(WizardStep):
    name = 'Consumption'
    title = _('Consumption')
    section = _('Consumption')
    icon = 'consumption.png'
    gladeFile = 'consumption-wizard.glade'

    def __init__(self, wizard):
        self._httpCommon = HTTPCommon()
        self._httpPorter = Porter(
            worker=None, port=configure.defaultHTTPStreamPort)
        WizardStep.__init__(self, wizard)

    # Public

    def getHTTPCommon(self):
        return self._httpCommon

    def getHTTPPorter(self):
        return self._httpPorter

    # WizardStep

    def activated(self):
        hasAudio = self.wizard.hasAudio()
        hasVideo = self.wizard.hasVideo()
        hasBoth = hasAudio and hasVideo

        possibleButtons = [self.http_audio_video,
                           self.http_audio,
                           self.http_video,
                           self.disk_audio_video,
                           self.disk_audio,
                           self.disk_video,
                           ]
        shoutButtons = [self.shout2_audio_video,
                        self.shout2_audio,
                        self.shout2_video]

        if self._canEmbedShout():
            possibleButtons.extend(shoutButtons)
        else:
            self.shout2.set_active(False)
            self.shout2.hide()
            for button in shoutButtons:
                button.hide()

        # Hide all checkbuttons if we don't have both audio and video selected
        for checkbutton in possibleButtons:
            checkbutton.set_property('visible', hasBoth)

    def getNext(self, step=None):
        steps = self._getSteps()
        assert steps

        if step is None:
            step_class = steps[0]
        else:
            step_class = step.__class__
            if step_class in steps and steps[-1] != step_class:
                step_class = steps[steps.index(step_class)+1]
            else:
                return

        return step_class(self.wizard)

    # Private

    def _verify(self):
        disk = self.disk.get_active()
        disk_audio = self.disk_audio.get_active()
        disk_video = self.disk_video.get_active()
        disk_audio_video = self.disk_audio_video.get_active()
        http = self.http.get_active()
        http_audio = self.http_audio.get_active()
        http_video = self.http_video.get_active()
        http_audio_video = self.http_audio_video.get_active()
        shout2 = self.shout2.get_active()
        shout2_audio = self.shout2_audio.get_active()
        shout2_video = self.shout2_video.get_active()
        shout2_audio_video = self.shout2_audio_video.get_active()

        blockNext = True
        if ((disk and pany([disk_audio, disk_video, disk_audio_video])) or
            (http and pany([http_audio, http_video, http_audio_video])) or
            (shout2 and pany([shout2_audio, shout2_video, shout2_audio_video]))):
            blockNext = False
        self.wizard.blockNext(blockNext)

    def _canEmbedShout(self):
        encodingStep = self.wizard.getStep('Encoding')
        # Shoutcast supports only mp3 and ogg
        if (encodingStep.getAudioFormat() == 'mp3' or
            encodingStep.getMuxerFormat() == 'ogg'):
            return True
        return False

    def _getSteps(self):
        uielements = []
        retval = []
        if self.http.get_active():
            retval.append(HTTPConsumptionStep)
            uielements.append(
                ([HTTPAudioStep, HTTPVideoStep, HTTPBothStep],
                 [self.http_audio,
                  self.http_video,
                  self.http_audio_video]))
        if self.disk.get_active():
            uielements.append(
                ([DiskAudioStep, DiskVideoStep, DiskBothStep],
                 [self.disk_audio,
                  self.disk_video,
                  self.disk_audio_video]))
        if self.shout2.get_active() and self._canEmbedShout():
            uielements.append(
                ([Shout2AudioStep, Shout2VideoStep, Shout2BothStep],
                 [self.shout2_audio,
                  self.shout2_video,
                  self.shout2_audio_video]))

        has_audio = self.wizard.hasAudio()
        has_video = self.wizard.hasVideo()

        for steps, (audio, video, audio_video) in uielements:
            # Audio & Video, all checkbuttons are visible and
            # changeable by the user
            if has_audio and has_video:
                enable_audio_video = audio_video.get_active()
                enable_audio = audio.get_active()
                enable_video = video.get_active()
            # Audio only, user cannot chose, the checkbuttons are not
            # visible and it is not possible for the user to change,
            # just add audio, and nothing else
            elif has_audio and not has_video:
                enable_audio_video = False
                enable_audio = True
                enable_video = False
            # Video only, like audio only but with video
            elif has_video and not has_audio:
                enable_audio_video = False
                enable_audio = False
                enable_video = True
            else:
                raise AssertionError

            audio_step, video_step, audio_video_step = steps
            if enable_audio_video:
                retval.append(audio_video_step)
            if enable_audio:
                retval.append(audio_step)
            if enable_video:
                retval.append(video_step)

        return retval

    # Callbacks

    def on_disk__toggled(self, button):
        value = self.disk.get_active()
        self.disk_audio_video.set_sensitive(value)
        self.disk_audio.set_sensitive(value)
        self.disk_video.set_sensitive(value)

        self._verify()

    def on_shout2__toggled(self, button):
        value = self.shout2.get_active()
        self.shout2_audio_video.set_sensitive(value)
        self.shout2_audio.set_sensitive(value)
        self.shout2_video.set_sensitive(value)

        self._verify()

    def on_http_audio_video__toggled(self, button):
        self._verify()

    def on_http_audio__toggled(self, button):
        self._verify()

    def on_http_video__toggled(self, button):
        self._verify()

    def on_http__toggled(self, button):
        value = self.http.get_active()
        self.http_audio_video.set_sensitive(value)
        self.http_audio.set_sensitive(value)
        self.http_video.set_sensitive(value)

        self._verify()


class HTTPConsumptionStep(WorkerWizardStep):
    """I am a step of the configuration wizard which allows you
    to configure the common http properties of a stream
    """
    name = 'HTTPStreaming'
    title = _('HTTP Streaming')
    section = _('Consumption')
    icon = 'consumption.png'
    gladeFile = 'http-wizard.glade'

    def __init__(self, wizard):
        consumptionStep = wizard.getStep('Consumption')
        self.common = consumptionStep.getHTTPCommon()
        self.porter = consumptionStep.getHTTPPorter()
        WorkerWizardStep.__init__(self, wizard)

    # WizardStep

    def setup(self):
        self.bandwidth_limit.data_type = float
        self.burst_on_connect.data_type = bool
        self.client_limit.data_type = int
        self.port.data_type = int

        self.add_proxy(self.porter.properties, ['port'])
        self.add_proxy(self.common, ['has_client_limit',
                                     'has_bandwidth_limit',
                                     'client_limit',
                                     'bandwidth_limit',
                                     'burst_on_connect'])

    def activated(self):
        self._verify()

    def getNext(self):
        return self.wizard.getStep('Consumption').getNext(self)

    def workerChanged(self, worker):
        self.porter.worker = worker

    # Private

    def _verify(self):
        self.client_limit.set_sensitive(
            self.has_client_limit.get_active())
        self.bandwidth_limit.set_sensitive(
            self.has_bandwidth_limit.get_active())

    # Callbacks

    def on_has_client_limit_toggled(self, checkbutton):
         self._verify()

    def on_has_bandwidth_limit_toggled(self, checkbutton):
         self._verify()
