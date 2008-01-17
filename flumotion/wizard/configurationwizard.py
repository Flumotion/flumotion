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

__version__ = "$Rev$"

import gettext
import sets

import gtk
from twisted.internet import defer

from flumotion.common import errors, messages
from flumotion.common.common import pathToModuleName
from flumotion.common.messages import N_, ngettext
from flumotion.common.pygobject import gsignal
from flumotion.ui.wizard import SectionWizard, WizardStep
from flumotion.wizard import save
from flumotion.wizard.basesteps import WorkerWizardStep
from flumotion.wizard.consumptionsteps import ConsumptionStep
from flumotion.wizard.conversionsteps import ConversionStep
from flumotion.wizard.enums import LicenseType
from flumotion.wizard.models import Flow
from flumotion.wizard.productionsteps import ProductionStep
from flumotion.wizard.worker import WorkerList

T_ = messages.gettexter('flumotion')
_ = gettext.gettext


# pychecker doesn't like the auto-generated widget attrs
# or the extra args we name in callbacks
__pychecker__ = 'no-classattr no-argsused'

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

    def before_show(self):
        self.textview_message.realize()
        normal_bg = self.textview_message.get_style().bg[gtk.STATE_NORMAL]
        self.textview_message.modify_base(gtk.STATE_INSENSITIVE, normal_bg)

    def get_next(self):
        return None


class LicenseStep(WizardStep):
    name = _("Content License")
    glade_file = "wizard_license.glade"
    section = _('License')
    icon = 'licenses.png'

    # WizardStep

    def setup(self):
        self.license.set_enum(LicenseType)

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

    def before_show(self):
        self.textview_message.realize()
        normal_bg = self.textview_message.get_style().bg[gtk.STATE_NORMAL]
        self.textview_message.modify_base(gtk.STATE_INSENSITIVE, normal_bg)

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
        self._save = save.WizardSaver(self)
        self._workerHeavenState = None
        self._last_worker = 0 # combo id last worker from step to step

        self.flow = Flow("default")

        self._worker_list = WorkerList()
        self.top_vbox.pack_start(self._worker_list, False, False)
        self._worker_list.connect('worker-selected',
                                  self.on_combobox_worker_changed)

    # SectionWizard

    def get_first_step(self):
        return WelcomeStep(self)

    def completed(self):
        configuration = self._save.getXML()
        self.emit('finished', configuration)

    def destroy(self):
        SectionWizard.destroy(self)
        self._admin = None
        del self._save

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
                self.block_next(True)
                message.id = 'element' + '-'.join(elementNames)
                self.add_msg(message)
            return elements

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
        """
        Fetches a wizard bundle from a specific kind of component
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

    # Private

    def _setup_worker(self, step, worker):
        # get name of active worker
        self.debug('%r setting worker to %s' % (step, worker))
        step.worker = worker

    def _set_worker_from_step(self, step):
        if not hasattr(step, 'worker'):
            return

        model = self.combobox_worker.get_model()
        current_text = step.worker
        for row in model:
            text = model.get(row.iter, 0)[0]
            if current_text == text:
                self.combobox_worker.set_active_iter(row.iter)
                break

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
                step.worker_changed()
        else:
            msg = messages.Error(T_(
                    N_('All workers have logged out.\n'
                    'Make sure your Flumotion network is running '
                    'properly and try again.')),
                id='worker-error')
            self.add_msg(msg)

