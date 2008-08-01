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

"""debugging helper code
"""

import linecache
import gc
import re
import sys
import types

from twisted.python.reflect import filenameToModuleName

__version__ = "$Rev$"
_tracing = 0
_indent = ''


def trace_start(func_filter=None, ignore_files_re=None, print_returns=False,
                write=None):
    global _tracing, _indent

    if func_filter:
        func_filter = re.compile(func_filter)

    if ignore_files_re:
        ignore_files_re = re.compile(ignore_files_re)

    if not write:

        def write(indent, str, *args):
            print (indent + str) % args

    def do_trace(frame, event, arg):
        global _tracing, _indent

        if not _tracing:
            print '[tracing stopped]'
            return None

        co = frame.f_code

        if event == 'line':
            return do_trace
        if func_filter and not func_filter.search(co.co_name):
            return None
        if ignore_files_re and ignore_files_re.search(co.co_filename):
            return None
        elif event == 'call' or event == 'c_call':
            if co.co_name == '?':
                return None
            module = filenameToModuleName(co.co_filename)
            write(_indent, '%s:%d:%s():', module, frame.f_lineno, co.co_name)
            _indent += '  '
            return do_trace
        elif event == 'return' or event == 'c_return':
            if print_returns:
                write(_indent, 'return %r', arg)
            _indent = _indent[:-2]
            return None
        elif event == 'exception' or event == 'c_exception':
            if arg:
                write(_indent, 'Exception: %s:%d: %s (%s)', co.co_filename,
                      frame.f_lineno, arg[0].__name__, arg[1])
            else:
                write(_indent, 'Exception: (from C)')
            return do_trace
        else:
            write(_indent, 'unknown event: %s', event)
            return None

    _tracing += 1
    if _tracing == 1:
        assert _indent == ''
        sys.settrace(do_trace)


def trace_stop():
    global _tracing, _indent
    assert _tracing > 0
    _tracing -= 1
    if not _tracing:
        sys.settrace(None)
        _indent = ''


def print_stack(handle=None):
    f = sys._getframe(1)
    output = []
    while f:
        co = f.f_code
        filename = co.co_filename
        lineno = f.f_lineno
        name = co.co_name
        linecache.checkcache(filename)
        line = linecache.getline(filename, lineno)
        # reversed so we can reverse() later
        if f.f_locals:
            for k, v in f.f_locals.items():
                output.append('      %s = %r\n' % (k, v))
            output.append('    Locals:\n')
        if line:
            output.append('    %s\n' % line.strip())
        output.append('  File "%s", line %d, in %s\n' % (
            filename, lineno, name))
        f = f.f_back
    output.reverse()
    if handle is None:
        handle = sys.stdout
    for line in output:
        handle.write(line)


class UncollectableMonitor(object):

    def __init__(self, period=120):
        known = {}

        # set this if you want python to print out when uncollectable
        # objects are detected; will print out all objects in the cycle,
        # not just the one(s) that caused the cycle to be uncollectable
        #
        # gc.set_debug(gc.DEBUG_UNCOLLECTABLE | gc.DEBUG_INSTANCES |
        # gc.DEBUG_OBJECTS)

        from twisted.internet import reactor

        def sample():
            gc.collect()
            for o in gc.garbage:
                if o not in known:
                    known[o] = True
                    self.uncollectable(o)
            reactor.callLater(period, sample)

        reactor.callLater(period, sample)

    def uncollectable(self, obj):
        print '\nUncollectable object cycle in gc.garbage:'

        print "Parents:"
        self._printParents(obj, 2)
        print "Kids:"
        self._printKids(obj, 2)

    def _printParents(self, obj, level, indent='  '):
        print indent, self._shortRepr(obj)
        if level > 0:
            for p in gc.get_referrers(obj):
                self._printParents(p, level - 1, indent + '  ')

    def _printKids(self, obj, level, indent='  '):
        print indent, self._shortRepr(obj)
        if level > 0:
            for kid in gc.get_referents(obj):
                self._printKids(kid, level - 1, indent + '  ')

    def _shortRepr(self, obj):
        if not isinstance(obj, dict):
            return '%s %r @ 0x%x' % (type(obj).__name__, obj, id(obj))
        else:
            keys = obj.keys()
            keys.sort()
            return 'dict with keys %r @ 0x%x' % (keys, id(obj))


class AllocMonitor(object):

    def __init__(self, period=10, analyze=None, allocPrint=None):
        self.period = period
        self.objset = None

        from sizer import scanner, annotate

        from twisted.internet import reactor

        if analyze is not None:
            self.analyze = analyze
        if allocPrint is not None:
            self.allocPrint = allocPrint

        def sample():
            objset = scanner.Objects()
            annotate.markparents(objset)

            if self.objset:
                self.analyze(self.objset, objset)

            self.objset = objset
            reactor.callLater(self.period, sample)

        reactor.callLater(self.period, sample)

    def analyze(self, old, new):
        from sizer import operations

        size = 0

        for k in operations.diff(new, old):
            size -= old[k].size

        allocators = {}
        diff = operations.diff(old, new)
        for k in diff:
            w = new[k]
            size += w.size
            if not w.parents:
                print "Unreferenced object %r, what?" % (w, )
            for p in w.parents:
                if id(p.obj) == id(self.__dict__):
                    continue
                if id(p.obj) not in diff:
                    # print "Object %r alloced by %r" % (w, p)
                    if p not in allocators:
                        allocators[p] = []
                    allocators[p].append(w)
        print "Total alloc size:", size
        for p in allocators:
            if p.obj == old or p.obj == new:
                print 'foo'
            else:
                self.allocPrint(p, allocators[p])
        for o in gc.garbage:
            print '\nUncollectable object cycle in gc.garbage:'
            self._printCycle(new[id(o)])

    def _printCycle(self, root):
        print "Parents:"
        self._printParents(root, 2)
        print "Kids:"
        self._printKids(root, 2)

    def _printParents(self, wrap, level, indent='  '):
        print indent, self._wrapperRepr(wrap)
        if level > 0:
            for p in wrap.parents:
                self._printParents(p, level - 1, indent + '  ')

    def _printKids(self, wrap, level, indent='  '):
        print indent, self._wrapperRepr(wrap)
        if level > 0:
            for kid in wrap.children:
                self._printKids(kid, level - 1, indent + '  ')

    def _allocStack(self, wrap, stack):
        stack.append(wrap)
        for p in wrap.parents:
            if (isinstance(p.obj, types.ModuleType)
                or isinstance(p.obj, type)
                or isinstance(p.obj, types.InstanceType)):
                stack.append(p)
                return stack
        if len(wrap.parents) == 1:
            return self._allocStack(wrap.parents[0], stack)
        return stack

    def _wrapperRepr(self, wrap):
        o = wrap.obj
        if wrap.type != dict:
            return '%s %r @ 0x%x' % (wrap.type.__name__, o, id(o))
        else:
            keys = o.keys()
            keys.sort()
            return 'dict with keys %r @ 0x%x' % (keys, id(o))

    def allocPrint(self, allocator, directAllocs):
        allocStack = self._allocStack(allocator, [])

        print '\nAlloc by ' + self._wrapperRepr(allocStack.pop(0))
        while allocStack:
            print '  referenced by ' + self._wrapperRepr(allocStack.pop(0))

        print "%d new %s:" % (len(directAllocs),
                              len(directAllocs) == 1 and "object" or "objects")
        for wrap in directAllocs:
            print '  ' + self._wrapperRepr(wrap)


def getVersions():
    """
    Get versions of all flumotion modules based on svn Rev keyword.
    """
    r = {}
    for modname in sys.modules:
        mod = sys.modules[modname]
        if modname.startswith('flumotion.') and hasattr(mod, "__version__"):
            # Has the form: "$Rev$"
            try:
                versionnum = int(mod.__version__[6:-2])
                r[modname] = versionnum
            except IndexError:
                pass
            except ValueError:
                pass

    return r
