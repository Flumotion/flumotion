# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4

import commands
import time

from flumotion.common.format import formatTime
from flumotion.monitor.nagios import util

__version__ = "$Rev: 6687 $"


class Recent(util.LogCommand):
    summary = 'check for recent logging of a string'
    description = """
Check the log file to assure that the given string was logged recently.

The given string will be passed to grep.

Note that Flumotion log files do not log the year, so this check assumes
that log lines are from the current year, or the previous year if the log
line would end up being in the future.

Note that Flumotion log files log in the server's local time, and this check
compares against the local time too, so the server logging and the server
checking should be in the same timezone.
"""
    usage = "[-s string] log-file-path"

    def addOptions(self):
        self.parser.add_option('-s', '--string',
            action="store", dest="string",
            help="string to grep for in the log",
            default="")
        default = 3600
        self.parser.add_option('-w', '--warning',
            action="store", dest="warning",
            help="age to warn for, in seconds (defaults to %r)" %
                default, default=default)
        default = 7200
        self.parser.add_option('-c', '--critical',
            action="store", dest="critical",
            help="age to critical for, in seconds (defaults to %r)" %
                default, default=default)

    def do(self, args):
        if not args:
            return util.unknown('Please specify a log file to check.')
        if len(args) > 1:
            return util.unknown('Please specify only one log file to check.')

        command = "grep '%s' %s | tail -n 1" % (
            self.options.string, " ".join(args))
        self.debug('executing %s' % command)
        output = commands.getoutput(command)
        self.debug('output: %s' % output)

        if not output:
            return util.unknown('Could not find string %s in log file' %
                self.options.string)

        level = output[:5].strip()
        if level not in ['ERROR', 'WARN', 'INFO', 'DEBUG', 'LOG']:
            return util.unknown("Last line is not a log line: '%s'" % output)

        # matches flumotion.extern.log.log
        # level   pid     object   cat      time
        # 5 + 1 + 7 + 1 + 32 + 1 + 17 + 1 + 15 == 80
        position = 5 + 1 + 7 + 1 + 32 + 1 + 17 + 1

        # log timestrings are currently in local time, which might be a mistake
        timestring = output[position:position + 15]
        timetuple = time.strptime(timestring, "%b %d %H:%M:%S")
        now = time.time()
        nowtuple = time.localtime(now)

        # since the year does not get logged, assume the log line is from this
        # year, or last year if the delta becomes negative
        timelist = list(timetuple)
        timelist[0] = nowtuple[0]
        if time.mktime(tuple(timelist)) > time.mktime(nowtuple):
            self.debug('timestamp is past now, so assume it is from last year')
            timelist[0] = nowtuple[0] - 1

        # mktime also works in local time, which hopefully matches the log's
        # local time
        timestamp = time.mktime(tuple(timelist))
        delta = now - int(timestamp)

        msg = 'Last log line%s is %s old.' % (
            self.options.string and " with '%s'" % self.options.string or '',
            formatTime(delta, fractional=2))
        if delta > int(self.options.critical):
            return util.critical(msg)
        elif delta > int(self.options.warning):
            return util.warning(msg)
        else:
            return util.ok(msg)


class Log(util.LogCommand):
    description = "Check log files."

    subCommandClasses = [Recent]
