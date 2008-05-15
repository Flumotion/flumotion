# -*- Mode: Python; test-case-name: flumotion.test.test_common_messages -*-
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
support for serializable translatable messages from component/manager to admin
"""

import time
import gettext

from flumotion.common import log
from flumotion.configure import configure
from twisted.spread import pb

__version__ = "$Rev$"

(ERROR,
 WARNING,
 INFO) = range(1, 4)

def N_(format):
    """
    Mark a singular string for translation, without translating it.
    """
    return format

def ngettext(singular, plural, count):
    """
    Mark a plural string for translation, without translating it.
    """
    return (singular, plural, count)

def gettexter(domain=configure.PACKAGE):
    """
    Return a function that takes a format string or tuple, and additional
    format args,
    and creates a L{Translatable} from it.

    Example::

        T_ = messages.gettexter('flumotion')
        t = T_(N_("Could not find '%s'."), file)

    @param domain: the gettext domain to create translatables for.
    """
    def create(format, *args):
        if isinstance(format, str):
            return TranslatableSingular(domain, format, *args)
        else:
            return TranslatablePlural(domain, format, *args)

    return lambda *args: create(*args)

class Translatable(pb.Copyable, pb.RemoteCopy):
    """
    I represent a serializable translatable gettext msg.
    """
    domain = None

# Taken from twisted.python.util; modified so that if compareAttributes
# grows, but we get a message from a remote side that doesn't have one
# of the new attributes, that we don't raise an exception
class FancyEqMixin:
    compareAttributes = ()
    def __eq__(self, other):
        if not self.compareAttributes:
            return self is other
        #XXX Maybe get rid of this, and rather use hasattr()s
        if not isinstance(other, self.__class__):
            return False
        for attr in self.compareAttributes:
            if hasattr(self, attr):
                if not hasattr(other, attr):
                    return False
                elif not getattr(self, attr) == getattr(other, attr):
                    return False
            elif hasattr(other, attr):
                return False
        return True

    def __ne__(self, other):
        return not self.__eq__(other)

# NOTE: subclassing FancyEqMixin allows us to compare two
# RemoteCopy instances gotten from the same Copyable; this allows
# state _append and _remove to work correctly
# Take note however that this also means that two RemoteCopy objects
# of two different Copyable objects, but with the same args, will
# also pass equality
# For our purposes, this is fine.

class TranslatableSingular(Translatable, FancyEqMixin):
    """
    I represent a translatable gettext msg in the singular form.
    """

    compareAttributes = ["domain", "format", "args"]

    def __init__(self, domain, format, *args):
        """
        @param domain: the text domain for translations of this message
        @param format: a format string
        @param args:   any arguments to the format string
        """
        self.domain = domain
        self.format = format
        self.args = args

    def untranslated(self):
        return self.format % self.args
pb.setUnjellyableForClass(TranslatableSingular, TranslatableSingular)

class TranslatablePlural(Translatable, FancyEqMixin):
    """
    I represent a translatable gettext msg in the plural form.
    """

    compareAttributes = ["domain", "singular", "plural", "count", "args"]

    def __init__(self, domain, format, *args):
        """
        @param domain: the text domain for translations of this message
        @param format: a (singular, plural, count) tuple
        @param args:   any arguments to the format string
        """
        singular, plural, count = format
        self.domain = domain
        self.singular = singular
        self.plural = plural
        self.count = count
        self.args = args

    def untranslated(self):
        return self.singular % self.args
pb.setUnjellyableForClass(TranslatablePlural, TranslatablePlural)

class Translator(log.Loggable):
    """
    I translate translatables and messages.
    I need to be told where locale directories can be found for all domains
    I need to translate for.
    """

    logCategory = "translator"

    def __init__(self):
        self._localedirs = {} # domain name -> list of locale dirs

    def addLocaleDir(self, domain, dir):
        """
        Add a locale directory for the given text domain.
        """
        if not domain in self._localedirs.keys():
            self._localedirs[domain] = []

        if not dir in self._localedirs[domain]:
            self.debug('Adding localedir %s for domain %s' % (dir, domain))
            self._localedirs[domain].append(dir)

    def translateTranslatable(self, translatable, lang=None):
        """
        Translate a translatable object, in the given language.

        @param lang: language code (or the current locale if None)
        """
        # gettext.translation objects are rumoured to be cached (API docs)
        domain = translatable.domain
        t = None
        if domain in self._localedirs.keys():
            # FIXME: possibly trap IOError and handle nicely ?
            for localedir in self._localedirs[domain]:
                try:
                    t = gettext.translation(domain, localedir, lang)
                except IOError:
                    pass
        else:
            self.debug('no locales for domain %s' % domain)

        format = None
        if not t:
            # if no translation object found, fall back to C
            self.debug('no translation found, falling back to C')
            if isinstance(translatable, TranslatableSingular):
                format = translatable.format
            elif isinstance(translatable, TranslatablePlural):
                if translatable.count == 1:
                    format = translatable.singular
                else:
                    format = translatable.plural
            else:
                raise NotImplementedError('Cannot translate translatable %r' %
                    translatable)
        else:
            # translation object found, translate
            if isinstance(translatable, TranslatableSingular):
                format = t.gettext(translatable.format)
            elif isinstance(translatable, TranslatablePlural):
                format = t.ngettext(translatable.singular, translatable.plural,
                    translatable.count)
            else:
                raise NotImplementedError('Cannot translate translatable %r' %
                    translatable)

        if translatable.args:
            return format % translatable.args
        else:
            return format

    def translate(self, message, lang=None):
        """
        Translate a message, in the given language.
        """
        strings = []
        for t in message.translatables:
            strings.append(self.translateTranslatable(t, lang))
        return "".join(strings)

# NOTE: same caveats apply for FancyEqMixin as above
# this might be a little heavy; we could consider only comparing
# on id, once we verify that all id's are unique

class Message(pb.Copyable, pb.RemoteCopy, FancyEqMixin):
    """
    I am a message to be shown in a UI.

    Projects should subclass this base class to provide default project
    and version class attributes.

    @ivar  section: name of the section in which the message is described.
    @type  section: str
    @ivar  anchor:  name of the anchor in which the message is described.
    @type  anchor:  str
    @ivar  description: the link text to show
    @type  description: L{flumotion.common.messages.Translatable}
    """
    project = configure.PACKAGE
    version = configure.version

    # these properties allow linking to the documentation
    section = None
    anchor = None
    description = None

    compareAttributes = ["level", "translatables", "debug", "id", "priority",
        "timestamp"]

    def __init__(self, level, translatable, debug=None, id=None, priority=50,
        timestamp=None):
        """
        Create a new message.

        The id identifies this kind of message, and serves two purposes.

        The first purpose is to serve as a key by which a kind of
        message might be removed from a set of messages. For example, a
        firewire component detecting that a cable has been plugged in
        will remove any message that the cable is unplugged.

        Secondly it serves so that the message viewers that watch the
        'current state' of some object only see the latest message of a
        given type. For example when messages are stored in persistent
        state objects that can be transferred over the network, it
        becomes inefficient to store the whole history of status
        messages. Message stores can keep only the latest message of a
        given ID.

        @param level:        ERROR, WARNING or INFO
        @param translatable: a translatable possibly with markup for
                             linking to documentation or running commands.
        @param debug:        further, untranslated, debug information, not
                             always shown
        @param priority:     priority compared to other messages of the same
                             level
        @param timestamp:    time since epoch at which the message was
                             generated, in seconds.
        @param id:           A unique id for this kind of message, as
                             discussed above. If not given, will be
                             generated from the contents of the
                             translatable.
        """
        self.level = level
        self.translatables = []
        self.debug = debug
        # FIXME: untranslated is a really poor choice of id
        self.id = id or translatable.untranslated()
        self.priority = priority
        self.timestamp = timestamp or time.time()
        # -1 is in __init__, -2 is in the subclass __init__, -3 is in the caller
        log.doLog(log.DEBUG, None, 'messages',
            'creating message %r', self, where=-3)
        self.add(translatable)

    def __repr__(self):
        return '<Message %r at %r>' % (self.id, id(self))

    def add(self, translatable):
        if not isinstance(translatable, Translatable):
            raise ValueError('%r is not Translatable' % translatable)
        self.translatables.append(translatable)
        log.doLog(log.DEBUG, None, 'messages',
            'message %r: adding %r', (id(self), translatable.untranslated()),
             where=-2)

pb.setUnjellyableForClass(Message, Message)

# these are implemented as factory functions instead of classes because
# properly proxying to the correct subclass is hard with Copyable/RemoteCopy
def Error(*args, **kwargs):
    """
    Create a L{Message} at ERROR level, indicating a failure that needs
    intervention to be resolved.
    """
    return Message(ERROR, *args, **kwargs)

def Warning(*args, **kwargs):
    """
    Create a L{Message} at WARNING level, indicating a potential problem.
    """
    return Message(WARNING, *args, **kwargs)

def Info(*args, **kwargs):
    """
    Create a L{Message} at INFO level.
    """
    return Message(INFO, *args, **kwargs)

class Result(pb.Copyable, pb.RemoteCopy):
    """
    I am used in worker checks to return a result.

    @ivar value:    the result value of the check
    @ivar failed:   whether or not the check failed.  Typically triggered
                    by adding an ERROR message to the result.
    @ivar messages: list of messages
    @type messages: list of L{Message}
    """
    def __init__(self):
        self.messages = []
        self.value = None
        self.failed = False

    def succeed(self, value):
        """
        Make the result be successful, setting the given result value.
        """
        self.value = value

    def add(self, message):
        """
        Add a message to the result.

        @type message: L{Message}
        """
        self.messages.append(message)
        if message.level == ERROR:
            self.failed = True
            self.value = None
pb.setUnjellyableForClass(Result, Result)
