# -*- Mode: Python; test-case-name: flumotion.test.test_i18n.py -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2004,2005,2006,2007,2008 Fluendo, S.L. (www.fluendo.com).
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

"""internationalization helpers
"""

import os
import gettext

from twisted.spread import pb

from flumotion.common import log
from flumotion.configure import configure

__version__ = "$Rev: 6693 $"


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

        T_ = gettexter('flumotion')
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
        if self.args:
            result = self.format % self.args
        else:
            result = self.format
        return result
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
        if self.args:
            result = self.singular % self.args
        else:
            result = self.singular
        return result
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


def getLL():
    """
    Return the (at most) two-letter language code set for message translation.
    """
    # LANGUAGE is a GNU extension; it can be colon-seperated but we ignore the
    # advanced stuff. If that's not present, just use LANG, as normal.
    language = os.environ.get('LANGUAGE', None)
    if language != None:
        LL = language[:2]
    else:
        lang = os.environ.get('LANG', 'en')
        LL = lang[:2]

    return LL


def installGettext():
    """
    Sets up gettext so that the program gets translated.
    Use this in any Flumotion end-user application that needs translations.
    """
    import locale

    localedir = os.path.join(configure.localedatadir, 'locale')
    log.debug("locale", "Loading locales from %s" % localedir)
    gettext.bindtextdomain(configure.PACKAGE, localedir)
    gettext.textdomain(configure.PACKAGE)
    # Some platforms such as win32 lacks localse.bindtextdomin/textdomain.
    # bindtextdomain/textdomain are undocumented functions only available
    # in the posix _locale module. We use them to avoid having to import
    # gtk.glade here and thus import gtk/create a connection to X.
    if hasattr(locale, 'bindtextdomain'):
        locale.bindtextdomain(configure.PACKAGE, localedir)
    if hasattr(locale, 'textdomain'):
        locale.textdomain(configure.PACKAGE)
