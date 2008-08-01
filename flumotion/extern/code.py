#!/usr/bin/env python
# Can be run standalone, or as a module

# gpython.py: GTK+-compatible read-eval-print loop.
# Adopted for use in Flumotion by Andy Wingo.
#
# Copyright (C) 2001 Brian McErlean
# Copyright (C) 2003 John Finlay
# Copyright (C) 2004 Guilherme Salgado
# Copyright (C) 2005 Andy Wingo
#
# gpython.py originates in ActiveState Python Cookbook Recipe 65109,
# http://aspn.activestate.com/ASPN/Cookbook/Python/Recipe/65109.
#
# Following the Cookbook license policy at
# http://aspn.activestate.com/ASPN/Cookbook/Python, this file is
# licensed under the same terms as Python itself.


import __builtin__
import __main__
import codeop
import keyword
import re
import readline
import threading
import traceback
import sys
import string

import pygtk
pygtk.require("2.0")
import gobject
import gtk


__all__ = ['interact']


class Completer:

    def __init__(self, globals, lokals):
        self.globals = globals
        self.locals = lokals

        self.completions = keyword.kwlist + \
                           __builtin__.__dict__.keys() + \
                           __main__.__dict__.keys()

    def complete(self, text, state):
        if state == 0:
            text = text.split(' ')[-1]
            if "." in text:
                self.matches = self.attr_matches(text)
            else:
                self.matches = self.global_matches(text)
        try:
            return self.matches[state]
        except IndexError:
            return None

    def update(self, globs, locs):
        self.globals = globs
        self.locals = locs

        for key in self.locals.keys():
            if not key in self.completions:
                self.completions.append(key)
        for key in self.globals.keys():
            if not key in self.completions:
                self.completions.append(key)

    def global_matches(self, text):
        matches = []
        n = len(text)
        for word in self.completions:
            if word[:n] == text:
                matches.append(word)
        return matches

    def attr_matches(self, text):
        m = re.match(r"(\w+(\.\w+)*)\.(\w*)", text)
        if not m:
            return
        expr, attr = m.group(1, 3)

        obj = eval(expr, self.globals, self.locals)
        words = dir(obj)

        matches = []
        n = len(attr)
        for word in words:
            if word[:n] == attr:
                matches.append("%s.%s" % (expr, word))
        return matches


class GtkInterpreter(threading.Thread):
    """Run a gtk main() in a separate thread.
    Python commands can be passed to the thread where they will be executed.
    This is implemented by periodically checking for passed code using a
    GTK timeout callback.
    """
    TIMEOUT = 100 # Millisecond interval between timeouts.

    def __init__(self, globals=None, locals=None):
        threading.Thread.__init__(self)
        self.ready = threading.Condition()
        self.globs = globals or {'__name__':
                                 '__console__', 'gtk': gtk}
        self.locs = locals or {}
        self._has_quit = False
        self.cmd = ''       # Current code block
        self.new_cmd = None # Waiting line of code, or None if none waiting

        self.completer = Completer(self.globs, self.locs)

    def run(self):
        print self.banner
        readline.set_completer(self.completer.complete)
        readline.parse_and_bind('tab: complete')
        ps1 = getattr(self, 'ps1', '>>> ')
        ps2 = getattr(self, 'ps1', '... ')
        read = self.reader

        prompt = ps1
        try:
            while True:
                command = read(prompt) + '\n' # raw_input strips newlines
                prompt = self.feed(command) and ps1 or ps2
        except (EOFError, KeyboardInterrupt):
            pass
        print
        self._has_quit = True

    def code_exec(self):
        """Execute waiting code.  Called every timeout period."""
        self.ready.acquire()

        if self._has_quit:
            if self.main_loop:
                self.main_loop.quit()
            return False

        if self.new_cmd != None:
            self.ready.notify()
            self.cmd = self.cmd + self.new_cmd
            self.new_cmd = None
            try:
                code = codeop.compile_command(self.cmd[:-1])
                if code:
                    self.cmd = ''
                    exec code in self.globs, self.locs
                    self.completer.update(self.globs, self.locs)
            except Exception:
                traceback.print_exc()
                self.cmd = ''

        self.ready.release()
        return True

    def feed_sync(self, code):
        if (not code) or (code[-1]<>'\n'):
            code = code +'\n' # raw_input strips newline
        self.ready.acquire()
        self.completer.update(self.globs, self.locs)
        self.new_cmd = code
        self.code_exec()
        self.ready.release()
        return not self.cmd

    def feed(self, code):
        """Feed a line of code to the thread.
        This function will block until the code checked by the GTK thread.
        Return true if executed the code.
        Returns false if deferring execution until complete block available.
        """
         # raw_input strips newline
        if (not code) or (code[-1]<>'\n'):
            code = code +'\n'
        self.completer.update(self.globs, self.locs)
        self.ready.acquire()
        self.new_cmd = code
        self.ready.wait()  # Wait until processed in timeout interval
        self.ready.release()

        return not self.cmd

    def interact(self, banner=None, reader=None, block=False):
        self.banner = banner or 'Interactive GTK Shell'
        self.reader = reader or raw_input
        gobject.timeout_add(self.TIMEOUT, self.code_exec)
        gtk.gdk.threads_init()
        self.start()
        self.main_loop = block and gobject.MainLoop()
        if self.main_loop:
            self.main_loop.run()

# Read user input in a loop, and send each line to the interpreter thread.


def interact(banner=None, reader=None, local=None):
    interpreter = GtkInterpreter(locals=local)
    interpreter.interact(banner, reader)

if __name__=="__main__":
    interpreter = GtkInterpreter()
    interpreter.feed_sync("import sys")
    interpreter.feed_sync("sys.path.append('.')")

    if len(sys.argv) > 1:
        for file in open(sys.argv[1]).readlines():
            interpreter.feed_sync(file)

    banner = 'Interactive GTK Shell'
    py_version = string.join(map(str, sys.version_info[:3]), '.')
    pygtk_version = string.join(map(str, gtk.pygtk_version), '.')
    gtk_version = string.join(map(str, gtk.gtk_version), '.')
    banner += '\nPython %s, Pygtk %s, GTK+ %s' % (py_version, pygtk_version,
                                                  gtk_version)

    interpreter.interact(banner, block=True)
