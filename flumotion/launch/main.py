# -*- Mode: Python -*-
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


"""
Flumotion-launch: A gst-launch analog for Flumotion.

The goal of flumotion-launch is to provide an easy way for testing
flumotion components, without involving much of Flumotion's core code.

Flumotion-launch takes a terse gst-launch-like syntax, translates that
into a component graph, and starts the components. An example would be:

  flumotion-launch videotest ! theora-encoder ! ogg-muxer ! http-streamer

You can also set properties:

  flumotion-launch videotest framerate=15/2

You can link specific feeders as well:

  flumotion-launch firewire .audio ! vorbis-encoder
  flumotion-launch firewire firewire0.audio ! vorbis-encoder

Components can be backreferenced using their names:

  flumotion-launch videotest audiotest videotest0. ! ogg-muxer \
                   audiotest0. ! ogg-muxer0.

In addition, components can have plugs:

  flumotion-launch http-streamer /apachelogger,logfile=/dev/stdout

Flumotion-launch explicitly avoids much of Flumotion's core logic. It
does not import flumotion.manager, flumotion.admin, or flumotion.worker.
There is no depgraph, no feed server, no job process. Although it might
be useful in the future to add a way to use the standard interfaces to
start components via admin, manager, worker, and job instances, this
low-level interface is useful in debugging problems and should be kept.
"""


import optparse
import os
import sys

from twisted.python import reflect
from twisted.internet import reactor, defer

from flumotion.common import log, common, registry, errors

from flumotion.launch import parse

def err(x):
    sys.stderr.write(x + '\n')
    raise SystemExit(1)


class ComponentWrapper(object):
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
        self.component = self.procedure()
        return self.component.setup(self.config)

    def provideMasterClock(self, port):
        ret = self.component.provide_master_clock(port)
        # grrrrr! for some reason getting the ip requires being
        # connected? I suppose it *is* always my ip relative to ip X
        # though...
        if not ret[0]:
            ret = ("127.0.0.1", ret[1], ret[2])
        return ret

    def start(self, clocking):
        return self.component.start(clocking)

    def stop(self):
        return self.component.stop()

    def feedToFD(self, feedName, fd):
        return self.component.feedToFD(feedName, fd)

    def eatFromFD(self, feedId, fd):
        return self.component.eatFromFD(feedId, fd)

def make_pipes(wrappers):
    fds = {} # feedcompname:feeder => (fd, start())
    wrappersByName = dict([(wrapper.name, wrapper)
                           for wrapper in wrappers])
    def starter(wrapper, feedName, write):
        return lambda: wrapper.feedToFD(feedName, write)
    for wrapper in wrappers:
        for source in wrapper.config.get('source', []):
            compName, feedName = source.split(':')
            read, write = os.pipe()
            start = starter(wrappersByName[compName], feedName, write)
            fds[source] = (read, start)
    return fds

def DeferredDelay(time, val):
    d = defer.Deferred()
    reactor.callLater(time, d.callback, val)
    return d

def start_components(wrappers, fds, delay):
    # figure out the links and start the components

    # first phase: instantiation and setup
    def got_results(results):
        success = True
        for result, wrapper in zip(results, wrappers):
            if not result[0]:
                print ("Component %s failed to start, reason: %r"
                       % (wrapper, result[1]))
                success = False
        if not success:
            raise errors.ComponentStartError()

    def choose_clocking(unused):
        # second phase: clocking
        need_sync = [(x.config['clock-master'], x) for x in wrappers
                     if x.config['clock-master'] is not None]
        need_sync.sort()
        need_sync = [x[1] for x in need_sync]

        if need_sync:
            master = need_sync.pop(0)
            print "Telling", master.name, "to provide the master clock."
            clocking = master.provideMasterClock(7600 - 1) # hack!
            return need_sync, clocking
        else:
            return None, None

    def add_delay(val):
        if delay:
            print 'Delaying component startup by %f seconds...' % delay
            return DeferredDelay(delay, val)
        else:
            return defer.succeed(val)

    def do_start(synchronization, wrapper):
        need_sync, clocking = synchronization

        # start it up, with clocking data only if it needs it
        for source in wrapper.config.get('source', []):
            read, start = fds[source]
            wrapper.eatFromFD(source, read)
            start()
        d = wrapper.start(wrapper in need_sync and clocking or None)
        d.addCallback(lambda val: synchronization)
        return d

    def do_stop(failure):
        for wrapper in wrappers:
            wrapper.stop()
        return failure

    d = defer.DeferredList([wrapper.instantiate() for wrapper in wrappers])
    d.addCallback(got_results)
    d.addCallback(choose_clocking)
    for wrapper in wrappers:
        d.addCallback(add_delay)
        d.addCallback(do_start, wrapper)
    d.addErrback(do_stop)
    return d

def main(args):
    from flumotion.common import setup
    setup.setupPackagePath()
    from flumotion.configure import configure
    log.debug('manager', 'Running Flumotion version %s' %
        configure.version)
    import twisted.copyright
    log.debug('manager', 'Running against Twisted version %s' %
        twisted.copyright.version)
    from flumotion.project import project
    for p in project.list():
        log.debug('manager', 'Registered project %s version %s' % (
            p, project.get(p, 'version')))

    parser = optparse.OptionParser()
    parser.add_option('-d', '--debug',
                      action="store", type="string", dest="debug",
                      help="set debug levels")
    parser.add_option('', '--delay',
                      action="store", type="float", dest="delay",
                      help="set debug levels")
    parser.add_option('-v', '--verbose',
                      action="store_true", dest="verbose",
                      help="be verbose")
    parser.add_option('', '--version',
                      action="store_true", dest="version",
                      default=False,
                      help="show version information")

    log.debug('worker', 'Parsing arguments (%r)' % ', '.join(args))
    options, args = parser.parse_args(args)

    # verbose overrides --debug
    if options.verbose:
        options.debug = "*:3"
 
    # handle all options
    if options.version:
        print common.version("flumotion-launch")
        return 0

    if options.debug:
        log.setFluDebug(options.debug)

    if options.delay:
        delay = options.delay
    else:
        delay = 0.

    # note parser versus parse
    configs = parse.parse_args(args[1:])

    # load the modules, make the component
    wrappers = [ComponentWrapper(config) for config in configs]

    # make socket pairs
    fds = make_pipes(wrappers)

    reactor.running = False
    reactor.failure = False
    reactor.callLater(0, lambda: setattr(reactor, 'running', True))

    d = start_components(wrappers, fds, delay)

    def errback(failure):
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
