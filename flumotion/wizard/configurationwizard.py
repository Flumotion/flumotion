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
import sets

from twisted.internet import defer

from flumotion.common import errors, messages
from flumotion.common.common import pathToModuleName
from flumotion.common.messages import N_, ngettext
from flumotion.common.pygobject import gsignal
from flumotion.ui.wizard import SectionWizard, WizardStep
from flumotion.wizard.basesteps import ConsumerStep
from flumotion.wizard.consumptionsteps import ConsumptionStep
from flumotion.wizard.conversionsteps import ConversionStep
from flumotion.wizard.productionsteps import ProductionStep
from flumotion.wizard.save import WizardSaver
from flumotion.wizard.worker import WorkerList
from flumotion.wizard.workerstep import WorkerWizardStep

# pychecker doesn't like the auto-generated widget attrs
# or the extra args we name in callbacks
__pychecker__ = 'no-classattr no-argsused'
__version__ = "$Rev$"
T_ = messages.gettexter('flumotion')
_ = gettext.gettext



# the denominator arg for all calls of this function was sniffed from
# the glade file's spinbutton adjustment

def _fraction_from_float(number, denominator):
    """
    Return a string to be used in serializing to XML.
    """
    return "%d/%d" % (number * denominator, denominator)


class WelcomeStep(WizardStep):
    glade_file = 'wizard_welcome.glade'
    name = _('Welcome')
    section = _('Welcome')
    icon = 'wizard.png'

    def get_next(self):
        return None


class LicenseStep(WizardStep):
    name = _("Content License")
    glade_file = "wizard_license.glade"
    section = _('License')
    icon = 'licenses.png'

    # Public API

    def getLicenseType(self):
        """Get the selected license type
        @returns: the license type or None
        @rtype: string or None
        """
        if self.set_license.get_active():
            return self.license.get_selected()

    # WizardStep

    def setup(self):
        self.license.prefill([
            (_('Creative Commons'), 'CC'),
            (_('Commercial'), 'Commercial')])

    def get_next(self):
        return None

    # Callbacks

    def on_set_license__toggled(self, button):
        self.license.set_sensitive(button.get_active())


class SummaryStep(WizardStep):
    name = _("Summary")
    section = _("Summary")
    glade_file = "wizard_summary.glade"
    icon = 'summary.png'
    last_step = True

    # WizardStep

    def get_next(self):
        return None


class ConfigurationWizard(SectionWizard):
    gsignal('finished', str)

    sections = [
        WelcomeStep,
        ProductionStep,
        ConversionStep,
        ConsumptionStep,
        LicenseStep,
        SummaryStep]

    def __init__(self, parent=None, admin=None):
        SectionWizard.__init__(self, parent)
        self._admin = admin
        self._workerHeavenState = None
        self._last_worker = 0 # combo id last worker from step to step

        self._flowName = 'default'

        self._worker_list = WorkerList()
        self.top_vbox.pack_start(self._worker_list, False, False)
        self._worker_list.connect('worker-selected',
                                  self.on_combobox_worker_changed)

    # SectionWizard

    def get_first_step(self):
        return WelcomeStep(self)

    def completed(self):
        self._save()

    def destroy(self):
        SectionWizard.destroy(self)
        self._admin = None

    def run(self, interactive, workerHeavenState, main=True):
        self._workerHeavenState = workerHeavenState
        self._worker_list.set_worker_heaven_state(workerHeavenState)

        SectionWizard.run(self, interactive, main)

    def before_show_step(self, step):
        if isinstance(step, WorkerWizardStep):
            self._worker_list.show()
            self._worker_list.notify_selected()
        else:
            self._worker_list.hide()

        self._setup_worker(step, self._worker_list.get_worker())

    def prepare_next_step(self, step):
        self._setup_worker(step, self._worker_list.get_worker())
        SectionWizard.prepare_next_step(self, step)

    # Public API

    def hasAudio(self):
        """If the configured feed has a audio stream
        @return: if we have audio
        @rtype: bool
        """
        source_step = self.get_step('Source')
        return source_step.hasAudio()

    def hasVideo(self):
        """If the configured feed has a video stream
        @return: if we have video
        @rtype: bool
        """
        source_step = self.get_step('Source')
        return bool(source_step.get_video_producer())

    def getConsumptionSteps(self):
        """Fetches the consumption steps chosen by the user
        @returns: consumption steps
        """
        for step in self.getVisitedSteps():
            if isinstance(step, ConsumerStep):
                yield step

    def canSelectWorker(self, canSelect):
        """Defines if it's possible to select a worker
        @param canSelect: if a worker can be selected
        @type canSelect: bool
        """
        self._worker_list.set_sensitive(canSelect)

    def check_elements(self, workerName, *elementNames):
        """
        Check if the given list of GStreamer elements exist on the given worker.

        @param workerName: name of the worker to check on
        @param elementNames: names of the elements to check

        @returns: a deferred returning a tuple of the missing elements
        """
        if not self._admin:
            self.debug('No admin connected, not checking presence of elements')
            return

        asked = sets.Set(elementNames)
        def _checkElementsCallback(existing, workerName):
            existing = sets.Set(existing)
            self.block_next(False)
            return tuple(asked.difference(existing))

        self.block_next(True)
        d = self._admin.checkElements(workerName, elementNames)
        d.addCallback(_checkElementsCallback, workerName)
        return d

    def require_elements(self, workerName, *elementNames):
        """
        Require that the given list of GStreamer elements exists on the
        given worker. If the elements do not exist, an error message is
        posted and the next button remains blocked.

        @param workerName: name of the worker to check on
        @param elementNames: names of the elements to check
        """
        if not self._admin:
            self.debug('No admin connected, not checking presence of elements')
            return

        self.debug('requiring elements %r' % (elementNames,))
        def got_missing_elements(elements, workerName):
            if elements:
                self.warning('elements %r do not exist' % (elements,))
                f = ngettext("Worker '%s' is missing GStreamer element '%s'.",
                    "Worker '%s' is missing GStreamer elements '%s'.",
                    len(elements))
                message = messages.Error(T_(f, workerName,
                    "', '".join(elements)))
                message.add(T_(N_("\n"
                    "Please install the necessary GStreamer plug-ins that "
                    "provide these elements and restart the worker.")))
                message.add(T_(N_("\n\n"
                    "You will not be able to go forward using this worker.")))
                message.id = 'element' + '-'.join(elementNames)
                self.add_msg(message)
            self.block_next(bool(elements))
            return elements

        self.block_next(True)
        d = self.check_elements(workerName, *elementNames)
        d.addCallback(got_missing_elements, workerName)

        return d

    def check_import(self, workerName, moduleName):
        """
        Check if the given module can be imported.

        @param workerName:  name of the worker to check on
        @param moduleName:  name of the module to import

        @returns: a deferred returning None or Failure.
        """
        if not self._admin:
            self.debug('No admin connected, not checking presence of elements')
            return

        d = self._admin.checkImport(workerName, moduleName)
        return d

    def require_import(self, workerName, moduleName, projectName=None,
                       projectURL=None):
        """
        Require that the given module can be imported on the given worker.
        If the module cannot be imported, an error message is
        posted and the next button remains blocked.

        @param workerName:  name of the worker to check on
        @param moduleName:  name of the module to import
        @param projectName: name of the module to import
        @param projectURL:  URL of the project
        """
        if not self._admin:
            self.debug('No admin connected, not checking presence of elements')
            return

        self.debug('requiring module %s' % moduleName)
        def _checkImportErrback(failure):
            self.warning('could not import %s', moduleName)
            message = messages.Error(T_(N_(
                "Worker '%s' cannot import module '%s'."),
                workerName, moduleName))
            if projectName:
                message.add(T_(N_("\n"
                    "This module is part of '%s'."), projectName))
            if projectURL:
                message.add(T_(N_("\n"
                    "The project's homepage is %s"), projectURL))
            message.add(T_(N_("\n\n"
                "You will not be able to go forward using this worker.")))
            self.block_next(True)
            message.id = 'module-%s' % moduleName
            self.add_msg(message)

        d = self.check_import(workerName, moduleName)
        d.addErrback(_checkImportErrback)
        return d

    # FIXME: maybe add id here for return messages ?
    def run_in_worker(self, worker, module, function, *args, **kwargs):
        """
        Run the given function and arguments on the selected worker.

        @param worker:
        @param module:
        @param function:
        @returns: L{twisted.internet.defer.Deferred}
        """
        self.debug('run_in_worker(module=%r, function=%r)' % (module, function))
        admin = self._admin
        if not admin:
            self.warning('skipping run_in_worker, no admin')
            return defer.fail(errors.FlumotionError('no admin'))

        if not worker:
            self.warning('skipping run_in_worker, no worker')
            return defer.fail(errors.FlumotionError('no worker'))

        d = admin.workerRun(worker, module, function, *args, **kwargs)

        def callback(result):
            self.debug('run_in_worker callbacked a result')
            self.clear_msg(function)

            if not isinstance(result, messages.Result):
                msg = messages.Error(T_(
                    N_("Internal error: could not run check code on worker.")),
                    debug=('function %r returned a non-Result %r'
                           % (function, result)))
                self.add_msg(msg)
                raise errors.RemoteRunError(function, 'Internal error.')

            for m in result.messages:
                self.debug('showing msg %r' % m)
                self.add_msg(m)

            if result.failed:
                self.debug('... that failed')
                raise errors.RemoteRunFailure(function, 'Result failed')
            self.debug('... that succeeded')
            return result.value

        def errback(failure):
            self.debug('run_in_worker errbacked, showing error msg')
            if failure.check(errors.RemoteRunError):
                debug = failure.value
            else:
                debug = "Failure while running %s.%s:\n%s" % (
                    module, function, failure.getTraceback())

            msg = messages.Error(T_(
                N_("Internal error: could not run check code on worker.")),
                debug=debug)
            self.add_msg(msg)
            raise errors.RemoteRunError(function, 'Internal error.')

        d.addErrback(errback)
        d.addCallback(callback)
        return d

    def get_wizard_entry(self, component_type):
        """Fetches a wizard bundle from a specific kind of component
        @param component_type: the component type to get the wizard entry
          bundle from.
        @returns: a deferred returning either::
          - factory of the component
          - noBundle error: if the component lacks a wizard bundle
        """
        def got_entry_point((filename, procname)):
            modname = pathToModuleName(filename)
            d = self._admin.getBundledFunction(modname, procname)
            self.clear_msg('wizard-bundle')
            return d

        self.clear_msg('wizard-bundle')
        d = self._admin.callRemote('getEntryByType', component_type, 'wizard')
        d.addCallback(got_entry_point)
        return d

    def get_wizard_plug_entry(self, plug_type):
        """Fetches a wizard bundle from a specific kind of plug
        @param plug_type: the plug type to get the wizard entry
          bundle from.
        @returns: a deferred returning either::
          - factory of the plug
          - noBundle error: if the plug lacks a wizard bundle
        """
        def got_entry_point((filename, procname)):
            modname = pathToModuleName(filename)
            d = self._admin.getBundledFunction(modname, procname)
            self.clear_msg('wizard-bundle')
            return d

        self.clear_msg('wizard-bundle')
        d = self._admin.callRemote('getPlugEntry', plug_type, 'wizard')
        d.addCallback(got_entry_point)
        return d

    def getWizardEntries(self, wizard_types=None, provides=None, accepts=None):
        """Queries the manager for a list of wizard entry matching the
        query.
        @param types: list of component types to fetch, is usually
          something like ['video-producer'] or ['audio-encoder']
        @type  types: list of strings
        @param provides: formats provided, eg ['jpeg', 'speex']
        @type  provides: list of strings
        @param accepts: formats accepted, eg ['theora']
        @type  accepts: list of strings
        @returns: a deferred returning a list
                  of L{flumotion.common.componentui.WizardEntryState}
        """
        self.debug('querying wizard entries (wizard_types=%r,provides=%r'
                   ',accepts=%r)'% (wizard_types, provides, accepts))
        return self._admin.getWizardEntries(wizard_types=wizard_types,
                                            provides=provides,
                                            accepts=accepts)


    # Private

    def _setup_worker(self, step, worker):
        # get name of active worker
        self.debug('%r setting worker to %s' % (step, worker))
        step.worker = worker

    def _save(self):
        save = WizardSaver()
        save.setFlowName(self._flowName)

        source_step = self.get_step('Source')
        save.setAudioProducer(source_step.get_audio_producer())
        save.setVideoProducer(source_step.get_video_producer())

        try:
            overlay_step = self.get_step('Overlay')
        except KeyError:
            pass
        else:
            save.setVideoOverlay(overlay_step.getOverlay())

        encoding_step = self.get_step('Encoding')
        save.setAudioEncoder(encoding_step.get_audio_encoder())
        save.setVideoEncoder(encoding_step.get_video_encoder())
        save.setMuxer(encoding_step.get_muxer_type(), encoding_step.worker)

        for step in self.getConsumptionSteps():
            consumerType = step.getConsumerType()
            save.addConsumer(step.getConsumerModel(), consumerType)

            for server in step.getServerConsumers():
                save.addServerConsumer(server, consumerType)

            for porter in step.getPorters():
                save.addPorter(porter, consumerType)

        license_step = self.get_step('Content License')
        if license_step.getLicenseType() == 'CC':
            save.setUseCCLicense(True)

        configuration = save.getXML()
        self.emit('finished', configuration)
        del save

    # Callbacks

    def on_combobox_worker_changed(self, combobox, worker):
        self.debug('combobox_worker_changed, worker %r' % worker)
        if worker:
            self.clear_msg('worker-error')
            self._last_worker = worker
            step = self._current_step
            if step and isinstance(step, WorkerWizardStep):
                self._setup_worker(step, worker)
                self.debug('calling %r.worker_changed' % step)
                step.worker_changed(worker)
        else:
            msg = messages.Error(T_(
                    N_('All workers have logged out.\n'
                    'Make sure your Flumotion network is running '
                    'properly and try again.')),
                id='worker-error')
            self.add_msg(msg)

