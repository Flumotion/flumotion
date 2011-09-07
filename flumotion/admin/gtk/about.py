# -*- Mode: Python; test-case-name: flumotion.test.test_dialogs -*-
# -*- coding: UTF-8 -*-
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

"""new about dialog"""

import gettext
import os

import gtk

from flumotion.configure import configure

__version__ = "$Rev: 8811 $"
_ = gettext.gettext


class GtkAboutDialog(gtk.AboutDialog):

    def __init__(self, parent=None):
        gtk.AboutDialog.__init__(self)

        self.set_name('Flumotion')
        self.set_website("http://www.flumotion.net")

        authors = [
                   'Johan Dahlin',
                   'Alvin Delagon',
                   'David Gay i Tello',
                   'Pedro Gracia Fajardo',
                   'Aitor Guevara Escalante',
                   'Arek Korbik',
                   'Marek Kowalski',
                   'Julien Le Goff',
                   'Marc-André Lureau',
                   'Xavier Martinez',
                   'Jordi Massaguer Pla',
                   'Andoni Morales Alastruey',
                   'Zaheer Abbas Merali',
                   'Sébastien Merle',
                   'Thodoris Paschidis',
                   'Xavier Queralt Mateu',
                   'Guillaume Quintard',
                   'Josep Joan "Pepe" Ribas',
                   'Mike Smith',
                   'Guillem Solà',
                   'Wim Taymans',
                   'Jan Urbański',
                   'Thomas Vander Stichele',
                   'Andy Wingo',
        ]

        self.set_authors(authors)

        image = gtk.Image()
        image.set_from_file(os.path.join(configure.imagedir, 'flumotion.png'))

        self.set_logo(image.get_pixbuf())
        self.set_version(configure.version)

        comments = _('Flumotion is a streaming media server.\n\n'
                     '© 2004-2009 Fluendo S.L.\n'
                     '© 2010-2011 Flumotion Services, S.A.\n')
        self.set_comments(comments)

        license = _('Flumotion - a streaming media server\n'
                    'Copyright (C) 2004-2009 Fluendo, S.L.\n'
                    'Copyright (C) 2010,2011 Flumotion Services, S.A.\n'
                    'All rights reserved.\n\n'
                    'This file may be distributed and/or modified under '
                    'the terms of\n'
                    'the GNU Lesser General Public License version 2.1 '
                    'as published by\n'
                    'the Free Software Foundation.\n\n'
                    'This file is distributed without any warranty; '
                    'without even the implied\n'
                    'warranty of merchantability or fitness for a particular '
                    'purpose.\n'
                    'See "LICENSE.LGPL" in the source distribution for '
                    'more information.')

        self.set_license(license)
        self.set_wrap_license(True)
