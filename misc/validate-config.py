# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4

import sys

from flumotion.manager import manager

vishnu = manager.Vishnu('validate')

vishnu.loadManagerConfigurationXML(sys.argv[1])
