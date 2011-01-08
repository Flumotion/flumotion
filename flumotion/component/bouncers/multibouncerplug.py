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

from twisted.internet import defer
from twisted.python import util

from flumotion.common import keycards, watched
from flumotion.common import messages, errors, documentation
from flumotion.common.i18n import N_, gettexter
from flumotion.component.bouncers import base, plug, combinator

T_ = gettexter()


class MultiBouncerPlug(plug.BouncerPlug):

    logCategory = 'multibouncerplug'

    def start(self, component):
        self.watchable_keycards = watched.WatchedDict() # keycard id -> Keycard
        self.contexts = {} # keycard id -> {algorithm name -> result}
        self.algorithms = util.OrderedDict() # name -> algorithm

        def add_entry(entry, algorithm):
            name = entry['type']
            if name in self.algorithms:
                suffix = 1
                while ('%s-%d' % (name, suffix)) in self.algorithms:
                    suffix += 1
                name = '%s-%d' % (name, suffix)

            assert name not in self.algorithms
            self.algorithms[name] = algorithm
            return name

        # get all algorithm plugs this component has, put them into
        # self.algorithms with unique names
        entries = component.config['plugs'].get(base.BOUNCER_ALGORITHM_SOCKET,
                                                [])
        algorithms = component.plugs.get(base.BOUNCER_ALGORITHM_SOCKET, [])

        if not algorithms:
            m = messages.Error(T_(N_(
                        "The multibouncerplug requires at least one bouncer "
                        "algorithm plug to be present")), mid='no-algorithm')
            component.addMessage(m)
            raise errors.ComponentSetupHandledError()

        for entry, algorithm in zip(entries, algorithms):
            # add the algorithm to the algorithms dictionary
            name = add_entry(entry, algorithm)
            # provide the algorithm with the keycard store
            algorithm.set_keycard_store(self.watchable_keycards)
            # provide the algorithm with an expiry function crafted especially
            # for it (containing its unique name)
            expire = lambda ids: self.algorithm_expire_keycard_ids(ids, name)
            algorithm.set_expire_function(expire)

        self.debug("configured with algorithms %r", self.algorithms.keys())

        # create the algorithm combinator
        props = self.args['properties']
        self.combinator = combinator.AlgorithmCombinator(self.algorithms)

        if 'combination' in props and combinator.pyparsing is None:
            m = messages.Error(T_(N_(
                        "To use the 'combination' property you need to "
                        "have the 'pyparsing' module installed.\n")),
                               mid='missing-pyparsing')
            documentation.messageAddPythonInstall(m, 'pyparsing')
            component.addMessage(m)
            raise errors.ComponentSetupHandledError()

        # get the combination specification, defaulting to implicit AND
        spec = props.get('combination', ' and '.join(self.algorithms.keys()))
        self.debug("using combination %s", spec)
        try:
            self.combinator.create_combination(spec)
        except combinator.ParseException, e:
            m = messages.Error(T_(N_(
                        "Invalid algorithms combination: %s"), str(e)),
                               mid='wrong-combination')

            component.addMessage(m)
            raise errors.ComponentSetupHandledError()

        return plug.BouncerPlug.start(self, component)

    def authenticate(self, keycard):
        # create a context for this request
        context = {}
        # ask the combinator for an answer
        d = self.combinator.evaluate(keycard, context)

        def authenticated(res, keycard):
            # the answer is True/False
            if not res:
                # False, return None as per the bouncer protocol
                return None
            if hasattr(keycard, 'ttl') and keycard.ttl <= 0:
                # keycard was invalid on input
                self.log('immediately expiring keycard %r', keycard)
                return None
            if self.addKeycard(keycard):
                # keycard added, set state to AUTHENTICATED, keep the context,
                # return to caller
                keycard.state = keycards.AUTHENTICATED
                self.contexts[keycard.id] = context
                self.watchable_keycards[keycard.id] = keycard
                return keycard

        d.addCallback(authenticated, keycard)

        return d

    def on_keycardRemoved(self, keycard):
        # clear our references to the keycard
        del self.contexts[keycard.id]
        del self.watchable_keycards[keycard.id]

    def algorithm_expire_keycard_ids(self, keycard_ids, name):
        # this gets called by a particular algorithm when it wants to expire a
        # keycard
        to_expire = []

        self.debug("algorithm %r requested expiration of keycards %r",
                   name, keycard_ids)

        for keycard_id in keycard_ids:
            # change the result in the context
            context = self.contexts[keycard_id]
            context[name] = False
            # Reevaluate in the combinator. Because we already got an answer
            # for that context, it should contain all necesary info, so we
            # never should call any algorithm method: just do synchronous
            # evaluation.
            if not self.combinator.synchronous_evaluate(context):
                self.log("keycard with id %r will be expired", keycard_id)
                to_expire.append(keycard_id)

        return self.expireKeycardIds(to_expire)
