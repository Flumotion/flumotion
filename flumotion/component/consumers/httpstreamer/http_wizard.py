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

from flumotion.configure import configure
from flumotion.wizard.basesteps import WorkerWizardStep

__version__ = "$Rev$"
_ = gettext.gettext
X_ = _


class HTTPStep(WorkerWizardStep):
    glade_file = 'wizard_http.glade'
    section = _('Consumption')
    component_type = 'http-streamer'

    def __init__(self, wizard):
        self._blocked = False
        WorkerWizardStep.__init__(self, wizard)

    # WizardStep

    def setup(self):
        self.spinbutton_port.set_value(self.port)

    def activated(self):
        self._check_elements()
        self._verify()

    def worker_changed(self):
        self._check_elements()

    def get_state(self):
        options = {
            'mount-point': self.entry_mount_point.get_text(),
            'burst-on-connect': self.checkbutton_burst_on_connect.get_active(),
            'port': int(self.spinbutton_port.get_value()),
            }

        if not self.checkbutton_bandwidth_limit.get_active():
            options['bandwidth-limit'] = int(
                self.spinbutton_bandwidth_limit.get_value() * 1e6)
        if not self.checkbutton_client_limit.get_active():
            options['client-limit'] = int(
                self.spinbutton_client_limit.get_value())
        return options

    def get_next(self):
        return self.wizard.get_step('Consumption').get_next(self)

    # Private

    def _check_elements(self):
        def got_missing(missing):
            blocked = bool(missing)
            self._block_next(blocked)

        self._block_next(True)

        d = self.wizard.require_elements(self.worker, 'multifdsink')
        d.addCallback(got_missing)

    def _verify(self):
        self.spinbutton_client_limit.set_sensitive(
            self.checkbutton_client_limit.get_active())
        self.spinbutton_bandwidth_limit.set_sensitive(
            self.checkbutton_bandwidth_limit.get_active())
        self._update_blocked()

    def _block_next(self, blocked):
        if self._blocked == blocked:
            return
        self._blocked = blocked
        self.wizard.block_next(blocked)

    def _update_blocked(self):
        self.wizard.block_next(
            self._blocked or self.entry_mount_point.get_text() == '')

    # Callbacks

    def on_entry_mount_point_changed(self, entry):
        self._verify()

    def on_checkbutton_client_limit_toggled(self, checkbutton):
        self._verify()

    def on_checkbutton_bandwidth_limit_toggled(self, checkbutton):
        self._verify()


class HTTPBothStep(HTTPStep):
    name = _('HTTP Streamer (audio & video)')
    sidebar_name = _('HTTP audio/video')
    port = configure.defaultStreamPortRange[0]


class HTTPAudioStep(HTTPStep):
    name = _('HTTP Streamer (audio only)')
    sidebar_name = _('HTTP audio')
    port = configure.defaultStreamPortRange[1]


class HTTPVideoStep(HTTPStep):
    name = _('HTTP Streamer (video only)')
    sidebar_name = _('HTTP video')
    port = configure.defaultStreamPortRange[2]


