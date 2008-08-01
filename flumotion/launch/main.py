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

"""
Flumotion-launch: A gst-launch analog for Flumotion.

The goal of flumotion-launch is to provide an easy way for testing
flumotion components, without involving much of Flumotion's core code.

Flumotion-launch takes a terse gst-launch-like syntax, translates that
into a component graph, and starts the components. An example would be::

  flumotion-launch videotest ! theora-encoder ! ogg-muxer ! http-streamer

You can also set properties::

  flumotion-launch videotest framerate=15/2

You can link specific feeders as well::

  flumotion-launch firewire .audio ! vorbis-encoder
  flumotion-launch firewire firewire0.audio ! vorbis-encoder

Components can be backreferenced using their names::

  flumotion-launch videotest audiotest videotest0. ! ogg-muxer \
                   audiotest0. ! ogg-muxer0.

In addition, components can have plugs::

  flumotion-launch http-streamer /apachelogger,logfile=/dev/stdout

Flumotion-launch explicitly avoids much of Flumotion's core logic. It
does not import flumotion.manager, flumotion.admin, or flumotion.worker.
There is no depgraph, no feed server, no job process. Although it might
be useful in the future to add a way to use the standard interfaces to
start components via admin, manager, worker, and job instances, this
low-level interface is useful in debugging problems and should be kept.
"""


import os
import sys

from twisted.python import reflect
from twisted.internet import reactor, defer

from flumotion.common import log, common, registry, errors, messages
from flumotion.common import i18n
from flumotion.common.options import OptionParser
from flumotion.configure import configure
from flumotion.twisted import flavors

from flumotion.launch import parse

from gettext import gettext as _

__version__ = "$Rev$"
_headings = {
    messages.ERROR: _('Error'),
    messages.WARNING: _('Warning'),
    messages.INFO: _('Note')}


def err(x):
    sys.stderr.write(x + '\n')
    raise SystemExit(1)


class ComponentWrapper(object, log.Loggable):
    logCategory = "compwrapper"

    def __init__(self, config):
        self.name = config['name']
        self.config = config
        self.procedure = self._getProcedure(config['type'])
        self.component = None

    def _getProcedure(self, type):
        r = registry.getRegistry()
        c = r.getComponent(type)
        try:
            entry = c.getEntryByType('component')
        except KeyError:
            err('Component %s has no component entry' % self.name)
        importname = entry.getModuleName(c.getBase())
        try:
            module = reflect.namedAny(importname)
        except Exception, e:
            err('Could not load module %s for component %s: %s'
                % (importname, self.name, e))
        return getattr(module, entry.getFunction())

    def instantiate(self):
        errors = []

        def haveError(value):
            translator = i18n.Translator()
            localedir = os.path.join(configure.localedatadir, 'locale')
            # FIXME: add locales as messages from domains come in
            translator.addLocaleDir(configure.PACKAGE, localedir)
            print "%s: %s" % (_headings[value.level],
                              translator.translate(value))
            if value.debug:
                print "Debug information:", value.debug
            errors.append(value)

        self.component = self.procedure(self.config,
                                        haveError=haveError)
        return not bool(errors)

    def provideMasterClock(self, port):
        # rtype: defer.Deferred
        d = self.component.provide_master_clock(port)
        return d

    def set_master_clock(self, ip, port, base_time):
        return self.component.set_master_clock(ip, port, base_time)

    def stop(self):
        return self.component.stop()

    def feedToFD(self, feedName, fd):
        self.debug('feedToFD(feedName=%s, %d)' % (feedName, fd))
        return self.component.feedToFD(feedName, fd, os.close)

    def eatFromFD(self, eaterAlias, feedId, fd):
        self.debug('eatFromFD(eaterAlias=%s, feedId=%s, %d)',
                   eaterAlias, feedId, fd)
        return self.component.eatFromFD(eaterAlias, feedId, fd)


def make_pipes(wrappers):
    fds = {} # feedcompname:feeder => (fd, start())
    wrappersByName = dict([(wrapper.name, wrapper)
                           for wrapper in wrappers])

    def starter(wrapper, feedName, write):
        return lambda: wrapper.feedToFD(feedName, write)
    for wrapper in wrappers:
        eaters = wrapper.config.get('eater', {})
        for eaterName in eaters:
            for feedId, eaterAlias in eaters[eaterName]:
                compName, feederName = common.parseFeedId(feedId)
                read, write = os.pipe()
                log.debug('launch', '%s: read from fd %d, write to fd %d',
                          feedId, read, write)
                start = starter(wrappersByName[compName], feederName, write)
                fds[feedId] = (read, start)
    return fds


def start_components(wrappers, fds):
    # figure out the links and start the components

    def provide_clock():
        # second phase: clocking
        need_sync = [x for x in wrappers if x.config['clock-master']]

        if need_sync:
            master = None
            for x in need_sync:
                if x.config['clock-master'] == x.config['avatarId']:
                    master = x
                    break
            assert master
            need_sync.remove(master)
            d = master.provideMasterClock(7600 - 1) # hack!

            def addNeedSync(clocking):
                return need_sync, clocking
            d.addCallback(addNeedSync)
            return d
        else:
            return defer.succeed((None, None))

    def do_start(synchronization, wrapper):
        need_sync, clocking = synchronization

        # start it up, with clocking data only if it needs it
        eaters = wrapper.config.get('eater', {})
        for eaterName in eaters:
            for feedId, eaterAlias in eaters[eaterName]:
                read, start = fds[feedId]
                wrapper.eatFromFD(eaterAlias, feedId, read)
                start()
        if (not need_sync) or (wrapper not in need_sync) or (not clocking):
            clocking = None
        if clocking:
            wrapper.set_master_clock(*clocking)
        return synchronization

    def do_stop(failure):
        for wrapper in wrappers:
            wrapper.stop()
        return failure

    for wrapper in wrappers:
        if not wrapper.instantiate():
            # we don't have a ComponentState, so we cheat and give the
            # exception a wrapper
            return defer.fail(errors.ComponentStartError(wrapper))
    d = provide_clock()
    for wrapper in wrappers:
        d.addCallback(do_start, wrapper)
    d.addErrback(do_stop)
    return d


def main(args):
    from flumotion.common import setup
    setup.setupPackagePath()
    from flumotion.configure import configure
    log.debug('launch', 'Running Flumotion version %s' %
        configure.version)
    import twisted.copyright
    log.debug('launch', 'Running against Twisted version %s' %
        twisted.copyright.version)
    from flumotion.project import project
    for p in project.list():
        log.debug('launch', 'Registered project %s version %s' % (
            p, project.get(p, 'version')))

    parser = OptionParser(domain="flumotion-launch")

    log.debug('launch', 'Parsing arguments (%r)' % ', '.join(args))
    options, args = parser.parse_args(args)

    i18n.installGettext()

    # verbose overrides --debug
    if options.verbose:
        log.setFluDebug("*:3")

    # handle all options
    if options.version:
        print common.version("flumotion-launch")
        return 0

    if options.debug:
        log.setFluDebug(options.debug)

    # note parser versus parse
    configs = parse.parse_args(args[1:])

    # load the modules, make the component
    wrappers = [ComponentWrapper(config) for config in configs]

    # make socket pairs
    fds = make_pipes(wrappers)

    reactor.running = False
    reactor.failure = False
    reactor.callLater(0, lambda: setattr(reactor, 'running', True))

    d = start_components(wrappers, fds)

    def errback(failure):
        log.debug('launch', log.getFailureMessage(failure))
        print "Error occurred: %s" % failure.getErrorMessage()
        failure.printDetailedTraceback()
        reactor.failure = True
        if reactor.running:
            print "Stopping reactor."
            reactor.stop()
    d.addErrback(errback)

    if not reactor.failure:
        print 'Running the reactor. Press Ctrl-C to exit.'

        log.debug('launch', 'Starting reactor')
        reactor.run()

        log.debug('launch', 'Reactor stopped')

    if reactor.failure:
        return 1
    else:
        return 0
