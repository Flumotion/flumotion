# -*- Mode: Python; test-case-name: flumotion.test.test_common_messages -*-
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
support for serializable translatable messages from component/manager to admin
"""

from twisted.spread import pb
import gettext

ERROR = 1
WARNING = 2
INFO = 3

def install(domain):
    """
    install 'N_' and 'ngettext' methods in the current namespace that
    can be used for marking translatable strings, and return
    Translatable instances.
    """
    import __builtin__
    N_ = lambda *args: TranslatableSingular(domain, *args)
    ngettext = lambda *args: TranslatablePlural(domain, *args)
    __builtin__.__dict__['ngettext'] = ngettext
    __builtin__.__dict__['N_'] = N_
    
class Translatable(pb.Copyable, pb.RemoteCopy):
    domain = None
    
class TranslatableSingular(Translatable):
    """
    I represent a translatable gettext msg in the singular form.
    """
    def __init__(self, domain, format, args=None):
        self.domain = domain
        self.format = format
        self.args = args
pb.setUnjellyableForClass(TranslatableSingular, TranslatableSingular)

class TranslatablePlural(Translatable):
    """
    I represent a translatable gettext msg in the plural form.
    """
    def __init__(self, domain, singular, plural, count, args=None):
        self.domain = domain
        self.singular = singular
        self.plural = plural
        self.count = count
        self.args = args
pb.setUnjellyableForClass(TranslatablePlural, TranslatablePlural)
    
class Translator:
    """
    I translate translatables and messages.
    I need to be told where locale directories can be found for all domains
    I need to translate for.
    """
    def __init__(self):
        self._localedirs = {} # domain name -> list of locale dirs

    def addLocaleDir(self, domain, dir):
        """
        Add a locale directory for the given text domain.
        """
        if not domain in self._localedirs.keys():
            self._localedirs[domain] = []

        if not dir in self._localedirs[domain]:
            self._localedirs[domain].append(dir)

    def translateTranslatable(self, translatable, lang=None):
        """
        Translate a translatable object, in the given language.

        @param lang: language code (or the current locale if None)
        """
        # gettext.translation objects are rumoured to be cached (API docs)
        domain = translatable.domain
        t = None
        # FIXME: possibly trap IOError and handle nicely ?
        for localedir in self._localedirs[domain]:
            t = gettext.translation(domain, localedir, lang)

        format = None
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

class Message(pb.Copyable, pb.RemoteCopy):
    """
    I am a message to be shown in a UI.
    I can be proxied from a worker or component to managers and admins.
    """
    def __init__(self, level, translatable, debug=None, id=None, priority=50):
        """
        @param level:        ERROR, WARNING or INFO
        @param translatable: a translatable possibly with markup for
                             linking to documentation or running commands.
        @param debug:        further, untranslated, debug information, not
                             always shown
        @param priority:     priority compared to other messages of the same
                             level
        """
        self.level = level
        self.translatables = [translatable, ]
        self.debug = debug
        self.id = id
        self.priority = priority

    def add(self, translatable):
        self.translatables.append(translatable)
pb.setUnjellyableForClass(Message, Message)

# these are implemented as factory functions instead of classes because
# properly proxying to the correct subclass is hard with Copyable/RemoteCopy
def Error(*args, **kwargs):
    return Message(ERROR, *args, **kwargs)

def Warning(*args, **kwargs):
    return Message(WARNING, *args, **kwargs)

def Info(*args, **kwargs):
    return Message(INFO, *args, **kwargs)

