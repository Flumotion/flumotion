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
import os
import sets

from gtk import gdk
from twisted.internet import defer

from flumotion.common import errors, messages
from flumotion.common.common import pathToModuleName
from flumotion.common.i18n import N_, ngettext, gettexter
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
T_ = gettexter()
_ = gettext.gettext



# the denominator arg for all calls of this function was sniffed from
# the glade file's spinbutton adjustment

def _fraction_from_float(number, denominator):
    """
    Return a string to be used in serializing to XML.
    """
    return "%d/%d" % (number * denominator, denominator)


class WelcomeStep(WizardStep):
    gladeFile = 'welcome-wizard.glade'
    name = _('Welcome')
    section = _('Welcome')
    icon = 'wizard.png'

    def getNext(self):
        return None


class LicenseStep(WizardStep):
    name = _("Content License")
    gladeFile = "license-wizard.glade"
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

    def getNext(self):
        return None

    # Callbacks

    def on_set_license__toggled(self, button):
        self.license.set_sensitive(button.get_active())


class SummaryStep(WizardStep):
    name = _("Summary")
    section = _("Summary")
    gladeFile = "summary-wizard.glade"
    icon = 'summary.png'
    lastStep = True

    # WizardStep

    def getNext(self):
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
        self._cursorWatch = gdk.Cursor(gdk.WATCH)
        self._tasks = []
        self._admin = admin
        self._workerHeavenState = None
        self._lastWorker = 0 # combo id last worker from step to step

        self._flowName = 'default'

        self._workerList = WorkerList()
        self.top_vbox.pack_start(self._workerList, False, False)
        self._workerList.connect('worker-selected',
                                  self.on_combobox_worker_changed)

    # SectionWizard

    def getFirstStep(self):
        return WelcomeStep(self)

    def completed(self):
        save = self._prepareSave()
        self.emit('finished', save.getXML())

    def destroy(self):
        SectionWizard.destroy(self)
        self._admin = None

    def run(self, interactive, workerHeavenState, main=True):
        self._workerHeavenState = workerHeavenState
        self._workerList.setWorkerHeavenState(workerHeavenState)

        SectionWizard.run(self, interactive, main)

    def beforeShowStep(self, step):
        if isinstance(step, WorkerWizardStep):
            self._workerList.show()
            self._workerList.notifySelected()
        else:
            self._workerList.hide()

        self._setupWorker(step, self._workerList.getWorker())

    def prepareNextStep(self, step):
        self._setupWorker(step, self._workerList.getWorker())
        SectionWizard.prepareNextStep(self, step)

    def blockNext(self, block):
        # Do not block/unblock if we have tasks running
        if self._tasks:
            return
        SectionWizard.blockNext(self, block)

    # Public API

    def waitForTask(self, taskName):
        """Instruct the wizard that we're waiting for a task
        to be finished. This changes the cursor and prevents
        the user from continuing moving forward.
        Each call to this method should have another call
        to taskFinished() when the task is actually done.
        @param taskName: name of the name
        """
        self.info("waiting for task %s" % (taskName,))
        if not self._tasks:
            if self.window1.window is not None:
                self.window1.window.set_cursor(self._cursorWatch)
            self.blockNext(True)
        self._tasks.append(taskName)

    def taskFinished(self, blockNext=False):
        """Instruct the wizard that a task was finished.
        @param blockNext: if we should still next when done
        """
        if not self._tasks:
            raise AssertionError(
                "Stray call to taskFinished(), forgot to call waitForTask()?")
        
        taskName = self._tasks.pop()
        self.info("task %s has now finished" % (taskName,))
        if not self._tasks:
            self.window1.window.set_cursor(None)
            self.blockNext(blockNext)

    def pendingTask(self):
        """Returns true if there are any pending tasks
        @returns: if there are pending tasks
        """
        return bool(self._tasks)

    def hasAudio(self):
        """If the configured feed has a audio stream
        @return: if we have audio
        @rtype: bool
        """
        source_step = self.getStep('Production')
        return source_step.hasAudio()

    def hasVideo(self):
        """If the configured feed has a video stream
        @return: if we have video
        @rtype: bool
        """
        source_step = self.getStep('Production')
        return bool(source_step.getVideoProducer())

    def getConsumptionSteps(self):
        """Fetches the consumption steps chosen by the user
        @returns: consumption steps
        """
        for step in self.getVisitedSteps():
            if isinstance(step, ConsumerStep):
                yield step

    def checkElements(self, workerName, *elementNames):
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
            self.taskFinished()
            return tuple(asked.difference(existing))

        self.waitForTask('check elements %r' % (elementNames,))
        d = self._admin.checkElements(workerName, elementNames)
        d.addCallback(_checkElementsCallback, workerName)
        return d

    def requireElements(self, workerName, *elementNames):
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
        def gotMissingElements(elements, workerName):
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
            self.taskFinished(bool(elements))
            return elements

        self.waitForTask('require elements %r' % (elementNames,))
        d = self.checkElements(workerName, *elementNames)
        d.addCallback(gotMissingElements, workerName)

        return d

    def checkImport(self, workerName, moduleName):
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

    def requireImport(self, workerName, moduleName, projectName=None,
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
            message.id = 'module-%s' % moduleName
            self.add_msg(message)
            self.taskFinished(True)

        d = self.checkImport(workerName, moduleName)
        d.addErrback(_checkImportErrback)
        return d

    # FIXME: maybe add id here for return messages ?
    def runInWorker(self, worker, module, function, *args, **kwargs):
        """
        Run the given function and arguments on the selected worker.

        @param worker:
        @param module:
        @param function:
        @returns: L{twisted.internet.defer.Deferred}
        """
        self.debug('runInWorker(module=%r, function=%r)' % (module, function))
        admin = self._admin
        if not admin:
            self.warning('skipping runInWorker, no admin')
            return defer.fail(errors.FlumotionError('no admin'))

        if not worker:
            self.warning('skipping runInWorker, no worker')
            return defer.fail(errors.FlumotionError('no worker'))

        def callback(result):
            self.debug('runInWorker callbacked a result')
            self.clear_msg(function)

            if not isinstance(result, messages.Result):
                msg = messages.Error(T_(
                    N_("Internal error: could not run check code on worker.")),
                    debug=('function %r returned a non-Result %r'
                           % (function, result)))
                self.add_msg(msg)
                self.taskFinished(True)
                raise errors.RemoteRunError(function, 'Internal error.')

            for m in result.messages:
                self.debug('showing msg %r' % m)
                self.add_msg(m)

            if result.failed:
                self.debug('... that failed')
                self.taskFinished(True)
                raise errors.RemoteRunFailure(function, 'Result failed')
            self.debug('... that succeeded')
            self.taskFinished()
            return result.value

        def errback(failure):
            self.debug('runInWorker errbacked, showing error msg')
            if failure.check(errors.RemoteRunError):
                debug = failure.value
            else:
                debug = "Failure while running %s.%s:\n%s" % (
                    module, function, failure.getTraceback())

            msg = messages.Error(T_(
                N_("Internal error: could not run check code on worker.")),
                debug=debug)
            self.add_msg(msg)
            self.taskFinished(True)
            raise errors.RemoteRunError(function, 'Internal error.')

        self.waitForTask('run in worker: %s.%s(%r, %r)' % (module, function,
                                                           args, kwargs))
        d = admin.workerRun(worker, module, function, *args, **kwargs)
        d.addErrback(errback)
        d.addCallback(callback)
        return d

    def _gotEntryPoint(self, (filename, procname)):
        # The manager always returns / as a path separator, replace them with
        # the separator since the rest of our infrastructure depends on that.
        filename = filename.replace('/', os.path.sep)
        modname = pathToModuleName(filename)
        d = self._admin.getBundledFunction(modname, procname)
        self.clear_msg('wizard-bundle')
        self.taskFinished()
        return d

    def getWizardEntry(self, componentType):
        """Fetches a wizard bundle from a specific kind of component
        @param componentType: the component type to get the wizard entry
          bundle from.
        @returns: a deferred returning either::
          - factory of the component
          - noBundle error: if the component lacks a wizard bundle
        """
        self.waitForTask('get wizard entry %s' % (componentType,))
        self.clear_msg('wizard-bundle')
        d = self._admin.callRemote('getEntryByType', componentType, 'wizard')
        d.addCallback(self._gotEntryPoint)
        return d

    def getWizardPlugEntry(self, plugType):
        """Fetches a wizard bundle from a specific kind of plug
        @param plugType: the plug type to get the wizard entry
          bundle from.
        @returns: a deferred returning either::
          - factory of the plug
          - noBundle error: if the plug lacks a wizard bundle
        """
        self.waitForTask('get wizard plug %s' % (plugType,))
        self.clear_msg('wizard-bundle')
        d = self._admin.callRemote('getPlugEntry', plugType, 'wizard')
        d.addCallback(self._gotEntryPoint)
        return d

    def getWizardEntries(self, wizardTypes=None, provides=None, accepts=None):
        """Queries the manager for a list of wizard entries matching the
        query.
        @param wizardTypes: list of component types to fetch, is usually
                            something like ['video-producer'] or
                            ['audio-encoder']
        @type  wizardTypes: list of str
        @param provides:    formats provided, eg ['jpeg', 'speex']
        @type  provides:    list of str
        @param accepts:     formats accepted, eg ['theora']
        @type  accepts:     list of str

        @returns: a deferred returning a list
                  of L{flumotion.common.componentui.WizardEntryState}
        """
        self.debug('querying wizard entries (wizardTypes=%r,provides=%r'
                   ',accepts=%r)'% (wizardTypes, provides, accepts))
        return self._admin.getWizardEntries(wizardTypes=wizardTypes,
                                            provides=provides,
                                            accepts=accepts)


    # Private

    def _setupWorker(self, step, worker):
        # get name of active worker
        self.debug('%r setting worker to %s' % (step, worker))
        step.worker = worker

    def _prepareSave(self):
        save = WizardSaver()
        save.setFlowName(self._flowName)

        productionStep = self.getStep('Production')
        if productionStep.hasOnDemand():
            ondemandStep = self.getStep('Demand')
            save.addServerConsumer(
                ondemandStep.getServerConsumer(), 'ondemand')
            return save

        save.setAudioProducer(productionStep.getAudioProducer())
        save.setVideoProducer(productionStep.getVideoProducer())

        if productionStep.hasVideo():
            overlayStep = self.getStep('Overlay')
            save.setVideoOverlay(overlayStep.getOverlay())

        encodingStep = self.getStep('Encoding')
        save.setAudioEncoder(encodingStep.getAudioEncoder())
        save.setVideoEncoder(encodingStep.getVideoEncoder())
        save.setMuxer(encodingStep.getMuxerType(), encodingStep.worker)

        consumptionStep = self.getStep('Consumption')
        save.addPorter(consumptionStep.getHTTPPorter(), 'http')
        for step in self.getConsumptionSteps():
            consumerType = step.getConsumerType()
            save.addConsumer(step.getConsumerModel(), consumerType)

            for server in step.getServerConsumers():
                save.addServerConsumer(server, consumerType)

        licenseStep = self.getStep('Content License')
        if licenseStep.getLicenseType() == 'CC':
            save.setUseCCLicense(True)

        return save

    # Callbacks

    def on_combobox_worker_changed(self, combobox, worker):
        self.debug('combobox_workerChanged, worker %r' % worker)
        if worker:
            self.clear_msg('worker-error')
            self._lastWorker = worker
            step = self._currentStep
            if step and isinstance(step, WorkerWizardStep):
                self._setupWorker(step, worker)
                self.debug('calling %r.workerChanged' % step)
                step.workerChanged(worker)
        else:
            msg = messages.Error(T_(
                    N_('All workers have logged out.\n'
                    'Make sure your Flumotion network is running '
                    'properly and try again.')),
                id='worker-error')
            self.add_msg(msg)

