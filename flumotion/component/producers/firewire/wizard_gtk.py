# -*- Mode: Python -*-
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

import gettext
import os
import math

from zope.interface import implements

from flumotion.admin.assistant.interfaces import IProducerPlugin
from flumotion.admin.assistant.models import AudioProducer, VideoProducer, \
     AudioEncoder, VideoEncoder, VideoConverter
from flumotion.common import errors, messages
from flumotion.common.i18n import N_, gettexter
from flumotion.admin.gtk.basesteps import AudioProducerStep, VideoProducerStep

__pychecker__ = 'no-returnvalues'
__version__ = "$Rev$"
_ = gettext.gettext
T_ = gettexter()


class FireWireProducer(AudioProducer, VideoProducer):
    componentType = 'firewire-producer'

    def __init__(self):
        super(FireWireProducer, self).__init__()

        self.properties.is_square = True
        self.properties.framerate = 12.5
        self.properties.decoder = 'ffdec_dvvideo'
        self.properties.deinterlace_mode = 'auto'
        self.properties.deinterlace_method = 'ffmpeg'

    def __eq__(self, other):
        if not isinstance(other, FireWireProducer):
            return False

        guid1 = self.properties.get('guid', None)
        guid2 = other.properties.get('guid', None)

        return guid1 == guid2 and AudioProducer.__eq__(self, other)

    def getFeederName(self, component):
        if isinstance(component, AudioEncoder):
            return 'audio'
        elif isinstance(component, (VideoEncoder, VideoConverter)):
            return 'video'
        else:
            raise AssertionError


class _FireWireCommon:
    icon = 'firewire.png'
    gladeFile = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              'wizard.glade')
    componentType = 'firewire'
    width_corrections = ['none', 'pad', 'stretch']

    def __init__(self):
        # options detected from the device:
        self._dims = None
        self._factors = [1, 2, 3, 4, 6, 8]
        self._input_heights = None
        self._input_widths = None
        self._par = None

        # these are instance state variables:
        self._factor_i = 0             # index into self.factors
        self._width_correction = None     # currently chosen item from
                                          # width_corrections

    # WizardStep

    def workerChanged(self, worker):
        self.model.worker = worker
        self._populateDevices()

    # Private

    def _setSensitive(self, is_sensitive):
        self.vbox_controls.set_sensitive(is_sensitive)
        self.wizard.blockNext(not is_sensitive)

    def _update_output_format(self, update_correction=False):
        self._update_label_camera_settings()

        # factor is a double
        if self.combobox_scaled_height.get_selected() is not None:
            self._factor_i = self.combobox_scaled_height.get_selected()

        self._update_width_correction()
        self._update_label_output_format(update_correction)

    def _update_label_camera_settings(self):
        # update label_camera_settings
        standard = 'Unknown'
        aspect = 'Unknown'
        h = self._dims[1]
        if h == 576:
            standard = 'PAL'
        elif h == 480:
            standard = 'NTSC'
        else:
            self.warning('Unknown capture standard for height %d' % h)

        nom = self._par[0]
        den = self._par[1]
        if nom == 59 or nom == 10:
            aspect = '4:3'
        elif nom == 118 or nom == 40:
            aspect = '16:9'
        else:
            self.warning('Unknown pixel aspect ratio %d/%d' % (nom, den))

        text = _('%s, %s (%d/%d pixel aspect ratio)') % (standard, aspect,
            nom, den)
        self.label_camera_settings.set_text(text)

    def _update_width_correction(self):
        self._width_correction = None
        for i in type(self).width_corrections:
            if getattr(self, 'radiobutton_width_' + i).get_active():
                self._width_correction = i
                break
        assert self._width_correction

    def _update_label_output_format(self, update_correction):
        d = self._get_width_height()
        if self._width_correction == 'stretch':
            # is_square is True in this case (otherwise PAR is recomputed)
            # => DAR can be destroyed
            # we ensure multiple of 8 to avoid videobox padding, and stretch
            self.model.properties.width = (d['ow'] + 8) - d['ow'] % 8
            out_width = self.model.properties.width
        elif self._width_correction == 'pad':
            # only specify height, to let videobox compute the width
            self.model.properties.height = d['oh']
            out_width = (d['ow'] + 8) - d['ow'] % 8
            #FIXME: This used to work without setting the width
            self.model.properties.width = out_width
        else:
            self.model.properties.width = d['ow']
            out_width = d['ow']
            # if is_square, height can be managed automatically by videoscale
            if self.model.properties.is_square:
                self.model.properties.height = 0
        num, den = 1, 1
        if not self.model.properties.is_square:
            num, den = self._par[0], self._par[1]

        msg = _('%dx%d, %d/%d pixel aspect ratio') % (
                   out_width, d['oh'], num, den)
        self.label_output_format.set_markup(msg)

        if update_correction:
            # if scaled width (after squaring) is not multiple of 8, present
            # width correction and select padding as default.
            self.frame_width_correction.set_sensitive(d['ow'] % 8 != 0)
            self.radiobutton_width_none.set_active(d['ow'] % 8 == 0)
            self.radiobutton_width_pad.set_active(d['ow'] % 8 != 0)

    def _get_width_height(self):
        # returns dict with sw, sh, ow, oh
        # which are scaled width and height, and output width and height
        oh = self._input_heights[self._factor_i]
        ow = self._input_widths[self._factor_i]
        par = 1. * self._par[0] / self._par[1]

        if self.model.properties.is_square:
            ow = int(math.ceil(ow * par))
            # for GStreamer element sanity, make ow an even number
            # FIXME: check if this can now be removed
            # ow = ow + (2 - (ow % 2)) % 2
        return dict(ow=ow, oh=oh)

    def _populateDevices(self):
        self._setSensitive(False)
        msg = messages.Info(T_(N_('Checking for Firewire devices...')),
            mid='firewire-check')
        self.wizard.add_msg(msg)
        d = self.runInWorker('flumotion.worker.checks.device',
                             'fetchDevices', 'firewire-check',
                             ['dv1394src'], 'guid')

        def firewireCheckDone(devices):
            self.wizard.clear_msg('firewire-check')
            self.guid.prefill(devices)

        def trapRemoteFailure(failure):
            failure.trap(errors.RemoteRunFailure)

        def trapRemoteError(failure):
            failure.trap(errors.RemoteRunError)

        d.addCallback(firewireCheckDone)
        d.addErrback(trapRemoteError)
        d.addErrback(trapRemoteFailure)

        return d

    def _runChecks(self):
        self._setSensitive(False)
        msg = messages.Info(T_(N_('Checking for Firewire device...')),
            mid='firewire-check')
        self.wizard.add_msg(msg)

        d = self.runInWorker('flumotion.worker.checks.gst010', 'check1394',
            mid='firewire-check', guid=self.guid.get_selected())

        def chooseDecoder(missing):
            if 'ffdec_dvvideo' in missing and 'dvdec' not in missing:
                msg = messages.Warning(T_(
                    N_("GStreamer's dv decoder element (dvdec) will be used "
                       "instead of FFmpeg's which is better in terms of "
                       "performance.\nIf the configuration doesn't work "
                       "properly, consider installing the ffmpeg plugins for "
                       "gstreamer.")), mid='firewire-warning')
                self.wizard.add_msg(msg)
                self.model.properties.decoder = 'dvdec'
            elif 'dvdec' in missing:
                msg = messages.Error(T_(
                    N_("None of the dv decoder elements was found in your "
                       "system, consider installing the ffmpeg plugins for "
                       "gstreamer to continue.")), mid='firewire-error')
                self.wizard.add_msg(msg)
                self.wizard.blockNext(True)

        def firewireCheckDone(options):
            self.wizard.clear_msg('firewire-check')
            self._dims = (options['width'], options['height'])
            self._par = options['par']
            self._input_heights = [self._dims[1]/i for i in self._factors]
            self._input_widths = [self._dims[0]/i for i in self._factors]
            values = []
            for i, height in enumerate(self._input_heights):
                values.append(('%d pixels' % height, i))
            self.combobox_scaled_height.prefill(values)
            if len(values) > 2:
                self.combobox_scaled_height.set_active(1)
            self._setSensitive(True)
            self._update_output_format(True)

            d = self.wizard.checkElements(self.model.worker,
                                          'ffdec_dvvideo', 'dvdec')
            d.addCallback(chooseDecoder)
            return d

        def trapRemoteFailure(failure):
            failure.trap(errors.RemoteRunFailure)

        def trapRemoteError(failure):
            failure.trap(errors.RemoteRunError)

        d.addCallback(firewireCheckDone)
        d.addErrback(trapRemoteError)
        d.addErrback(trapRemoteFailure)
        return d

    # Callbacks

    def on_is_square_toggled(self, radio):
        self._update_output_format(True)

    def on_guid_changed(self, combo):
        self._runChecks()

    def on_combobox_scaled_height_changed(self, combo):
        self._update_output_format(True)

    def on_radiobutton_width_none_toggled(self, radio):
        self._update_output_format()

    def on_radiobutton_width_stretch_toggled(self, radio):
        self._update_output_format()

    def on_radiobutton_width_pad_toggled(self, radio):
        self._update_output_format()


class FireWireVideoStep(_FireWireCommon, VideoProducerStep):
    name = 'Firewire'
    title = _('Firewire Video')
    docSection = 'help-configuration-assistant-producer-video-firewire'
    docAnchor = ''
    docVersion = 'local'

    def __init__(self, wizard, model):
        VideoProducerStep.__init__(self, wizard, model)
        _FireWireCommon.__init__(self)

    def setup(self):
        self.guid.data_type = int
        self.framerate.data_type = float
        self.add_proxy(self.model.properties,
                       ['guid', 'framerate', 'is_square'])


class FireWireAudioStep(_FireWireCommon, AudioProducerStep):
    name = 'Firewire audio'
    title = _('Firewire Audio')
    docSection = 'help-configuration-assistant-producer-audio-firewire'
    docAnchor = ''
    docVersion = 'local'

    def __init__(self, wizard, model):
        AudioProducerStep.__init__(self, wizard, model)
        _FireWireCommon.__init__(self)

    # WizardStep

    def setup(self):
        self.guid.data_type = int
        self.add_proxy(self.model.properties, ['guid'])
        self.frame_scaling.hide()
        self.frame_width_correction.hide()
        self.frame_capture.hide()
        self.frame_output_format.hide()

    def getNext(self):
        return None


class FireWireWizardPlugin(object):
    implements(IProducerPlugin)

    def __init__(self, wizard):
        self.wizard = wizard

    def getProductionStep(self, type):
        if type == 'audio':
            return FireWireAudioStep(self.wizard, FireWireProducer())
        elif type == 'video':
            return FireWireVideoStep(self.wizard, FireWireProducer())
