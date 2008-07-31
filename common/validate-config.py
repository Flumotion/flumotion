# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4

import sys

from flumotion.manager import manager

from flumotion.common import setup
setup.setup()
setup.setupPackagePath()

vishnu = manager.Vishnu('validate')

vishnu.loadManagerConfigurationXML(sys.argv[1])
