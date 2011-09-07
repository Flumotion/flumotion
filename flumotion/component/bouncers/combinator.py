# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4

# Flumotion - a streaming media server
# Copyright (C) 2004,2005,2006,2007,2008,2009 Fluendo, S.L.
# Copyright (C) 2010,2011 Flumotion Services, S.A.
# All rights reserved.
#
# This file may be distributed and/or modified under the terms of
# the GNU Lesser General Public License version 2.1 as published by
# the Free Software Foundation.
# This file is distributed without any warranty; without even the implied
# warranty of merchantability or fitness for a particular purpose.
# See "LICENSE.LGPL" in the source distribution for more information.
#
# Headers in this file shall remain intact.

"""
A bouncer-algorithm combinator, using the pyparsing module and a simple logic
expression language.
"""

try:
    import pyparsing
except ImportError:
    pyparsing = None

from twisted.internet import defer

from flumotion.common import keycards, log


class ParseException(Exception):
    """
    Error parsing combination specification.

    @cvar line: Line that triggered the error.
    @type line: string
    """


class CombinatorNode(object, log.Loggable):

    logCategory = "combinatornode"


class NotNode(CombinatorNode):

    logCategory = "notnode"

    def __init__(self, tokens):
        self.child = tokens[0][1]
        self.debug("creating combinator node using %r", self.child)

    def evaluate(self, keycard, context):
        d = self.child.evaluate(keycard, context)
        return d.addCallback(lambda (res, volatile): (not res, volatile))

    def synchronous_evaluate(self, context):
        return not self.child.synchronous_evaluate(context)


class AndNode(CombinatorNode):

    logCategory = "andnode"

    def __init__(self, tokens):
        self.children = tokens[0][0::2]
        self.debug("creating combinator node using %r", self.children)

    def evaluate(self, keycard, context):
        results = [(True, False)]

        d = defer.Deferred()

        for child in self.children:
            d.addCallback(self.set_result, keycard,
                          child, results, context)

        def decide_result(_):
            # nonvolatile False is nonvolatile False
            if results[-1] == (False, False):
                return False, False

            assert len(results) - 1 == len(self.children)

            result, volatile = True, False
            for res, vol in results:
                if not res:
                    assert vol
                    result = False
                if vol:
                    volatile = True
            return result, volatile

        d.addCallback(decide_result)
        d.callback(None)
        return d

    def set_result(self, _, keycard, child, results, context):
        self.log("processing results %r", results)

        # nonvolatile False is instant failure
        if results[-1] == (False, False):
            return

        d = child.evaluate(keycard, context)
        return d.addCallback(lambda (res, volatile):
                                 results.append((res, volatile)))

    def synchronous_evaluate(self, context):
        for child in self.children:
            if not child.synchronous_evaluate(context):
                return False
        return True


class OrNode(CombinatorNode):

    logCategory = "ornode"

    def __init__(self, tokens):
        self.children = tokens[0][0::2]
        self.debug("creating combinator node using %r", self.children)

    def evaluate(self, keycard, context):
        results = [(False, False)]

        d = defer.Deferred()

        for child in self.children:
            d.addCallback(self.set_result, keycard,
                          child, results, context)

        def decide_result(_):
            # nonvolatile True is nonvolatile True
            if results[-1] == (True, False):
                return True, False

            assert len(results) - 1 == len(self.children)

            result, volatile = False, False
            for res, vol in results:
                if res:
                    assert vol
                    result = True
                if vol:
                    volatile = True
            return result, volatile

        d.addCallback(decide_result)
        d.callback(None)
        return d

    def set_result(self, _, keycard, child, results, context):
        self.log("processing results %r", results)

        # nonvolatile True is instant success
        if results[-1] == (True, False):
            return

        d = child.evaluate(keycard, context)
        return d.addCallback(lambda (res, volatile):
                                 results.append((res, volatile)))

    def synchronous_evaluate(self, context):
        for child in self.children:
            if child.synchronous_evaluate(context):
                return True
        return False


class AlgorithmNode(CombinatorNode):

    logCategory = "algorithmnode"

    def __init__(self, name, call_function, volatile):
        self.debug("creating combinator node %r", name)
        self.name = name
        self.call_function = call_function
        self.volatile = volatile

    def get_state_and_reset(self, keycard, context):
        ret = bool(keycard and keycard.state == keycards.AUTHENTICATED)
        self.debug("node %r got response from algorithm for keycard %r: %r",
                   self.name, keycard, ret)
        if keycard:
            keycard.state = keycards.REQUESTING
        context[self.name] = ret
        return ret, self.result_volatile(ret)

    def evaluate(self, keycard, context):
        self.log("node %r evaluating %r in context %r",
                 self.name, keycard, context)
        if self.name in context:
            self.log("node %r found value in context: %r",
                     self.name, context[self.name])
            result = context[self.name]
            return defer.succeed((result, self.result_volatile(result)))
        self.debug("node %r calling algorithm with keycard %r",
                   self.name, keycard)
        d = defer.maybeDeferred(self.call_function, keycard)
        return d.addCallback(self.get_state_and_reset, context)

    def result_volatile(self, result):
        # failures are always nonvolatile
        if not result:
            return False
        # success can be volatile depending on the bouncer
        return self.volatile

    def synchronous_evaluate(self, context):
        self.debug("node %r evaluating synchronously in context %r",
                   self.name, context)
        return context[self.name]


class AlgorithmCombinator(log.Loggable):

    logCategory = 'combinator'

    def __init__(self, algorithms):
        self.algorithms = algorithms # name -> algorithm class

    def call_algorithm(self, name, keycard):
        return self.algorithms[name].authenticate(keycard)

    def create_combination(self, combination_spec):
        if pyparsing is None:
            self.create_fake_combination()
            return

        parser = self.create_parser(self.call_algorithm)
        try:
            self.combination = parser.parseString(combination_spec)[0]
        except pyparsing.ParseException, e:
            raise ParseException(e.line)

    def create_fake_combination(self):
        self.combination = AndNode([[]])
        self.combination.children = [
            AlgorithmNode(name, algorithm.authenticate, algorithm.volatile)
            for name, algorithm in self.algorithms.items()]

    def evaluate(self, keycard, context):
        d = self.combination.evaluate(keycard, context)
        return d.addCallback(lambda (ret, volatile): ret)

    def synchronous_evaluate(self, context):
        return self.combination.synchronous_evaluate(context)

    def create_parser(self, call_function):

        def create_algorithm_node(tokens):
            name = tokens[0]
            algorithm = self.algorithms[name]
            ret = AlgorithmNode(name,
                                algorithm.authenticate,
                                algorithm.volatile)
            return ret

        algorithm = pyparsing.oneOf(self.algorithms.keys())
        algorithm.setParseAction(create_algorithm_node)

        openended_expr = pyparsing.operatorPrecedence(
            algorithm,
            [("not", 1, pyparsing.opAssoc.RIGHT, NotNode),
             ("or", 2, pyparsing.opAssoc.LEFT, OrNode),
             ("and", 2, pyparsing.opAssoc.LEFT, AndNode)])

        return openended_expr + pyparsing.StringEnd()
