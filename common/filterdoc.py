# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4

# this script filters output from gendoc according to regexps
# It can't be done inside gendoc.py by replacing stderr, because epydoc
# does stderr replacement of its own

import re
import StringIO

# we filter out multi-line blocks by looking for start markers and
# corresponding stop markers.

# Each start marker can have multiple stop markers.  Each stop marker can
# have multiple blocks that need filtering out.

import sys
debug = sys.stdout.write
debug = lambda x: x


class REO:
    flags = 0

    def __init__(self, pattern):
        """
        @param pattern: the regexp pattern to match
        @type  pattern: str

        If pattern is None, it is meant to match anything, even empty.
        """
        if pattern:
            self.reo = re.compile(pattern, self.flags)
        else:
            self.reo = None


class Block(REO):
    flags = re.MULTILINE


class Stop(REO):
    blocks = None

    def __init__(self, pattern, blocks=None):
        REO.__init__(self, pattern)
        if blocks:
            for b in blocks:
                self.addBlock(b)

    def addBlock(self, block):
        if not self.blocks:
            self.blocks = []
        self.blocks.append(block)


class Start(REO):
    stops = None

    def __init__(self, pattern, stops=None):
        REO.__init__(self, pattern)
        if stops:
            for s in stops:
                self.addStop(s)

    def addStop(self, stop):
        if not self.stops:
            self.stops = []
        self.stops.append(stop)


starts = [
    Start('^=+$', [
        Stop('^$', [
            Block('In gtk'),
            Block('In gobject'),
            Block('In __builtin__'),
            # don't catch only /twisted/ since we have a twisted dir too
            Block('.*/twisted/spread'),
            Block('.*/twisted/trial'),
        ])
    ]),
    Start('- TestResult', [
        Stop('TestCase.run\)$', [
            Block('from twisted.trial'),
        ])
    ]),
    Start('.*\/ihooks.py.*DeprecationWarning: The sre module', [
        Stop('.*return imp.load_source\(name, filename, file\)', [
            Block(None),
        ])
    ]),
    Start('.*epydoc\/uid.py:.*GtkDeprecationWarning', [
        Stop('.*obj not in self._module.value', [
            Block(None),
        ])
    ]),
    Start('.* - twisted\.', [
        Stop('.*\(base method=', [
            Block(None),
        ])
    ]),
    Start('.* - pb.BrokerFactory', [
        Stop('.*\(from twisted.spread.flavors.Root.rootObject\)', [
            Block(None),
        ])
    ]),
    Start('.* - TestResult', [
        Stop('.*\(from twisted.trial.unittest.TestCase.run\)', [
            Block(None),
        ])
    ]),
]

singles = [
    "^Warning: <type 'exceptions\.",
    "^Warning: UID conflict detected: gobject",
    "^Warning: UID conflict detected: __builtin__",
    "^Warning: UID conflict detected: twisted",
    ".*- pb.getObjectAt \(from twisted.spread.flavors.Root\)",
    ".*- Deferred \(from twisted.trial.unittest.TestCase.run\)"]


class Filter:

    def __init__(self, stdin, stdout):
        self._stdin = stdin
        self._stdout = stdout
        self._starts = []
        self._reos = []
        self._multilines = []
        self._buffer = ''

    def addRegExpObject(self, reo):
        """
        Add a regexp for text to filter out.
        """
        self._reos.append(reo)

    def addStart(self, start):
        self._starts.append(start)

    def start(self):
        while True:
            line = self._stdin.readline()
            # handle EOF
            if line == '':
                break

            foundMatch = False
            for reo in self._reos:
                if re.match(reo, line):
                    foundMatch = True
                    continue

            if foundMatch:
                continue

            self._buffer += line

            for start in self._starts:
                if start.reo.match(line):
                    debug("found start: %s" % line)
                    # we're in a matching start block, look for the stop marker
                    stopFound = False
                    blockFound = False
                    lines = ''

                    while not stopFound:
                        line = self._stdin.readline()
                        # handle EOF
                        if line == '':
                            break

                        # see if any stop matches
                        for stop in start.stops:
                            if stop.reo.match(line):
                                stopFound = True
                                debug("found stop: %s" % line)
                                debug("have block: %s" % lines)

                                break

                        if not stopFound:
                            lines += line

                    # now that a stop is found, see if we can match a block
                    # to filter out
                    for block in stop.blocks:
                        if block.reo == None or block.reo.match(lines):
                            debug("found block: %s" % lines)
                            self._buffer = ''
                            blockFound = True

                    # if no block was found, we should append the
                    # suspected block lines and the stop line
                    if not blockFound:
                        self._buffer += lines + line

            self._stdout.write(self._buffer)
            self._stdout.flush()
            self._buffer = ''

import sys
f = Filter(sys.stdin, sys.stdout)
for s in starts:
    f.addStart(s)
for s in singles:
    reo = re.compile(s)
    f.addRegExpObject(reo)

f.start()
