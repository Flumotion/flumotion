# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4

import sys

from flumotion.common import registry

from flumotion.common import setup
setup.setup()
setup.setupPackagePath()

registry = registry.getRegistry()

basket = registry.makeBundlerBasket()

bundlerNames = basket.getBundlerNames()

exitCode = 0

for name in bundlerNames:
    try:
        basket.getBundlerByName(name).bundle()
    except OSError, e:
        sys.stderr.write("Bundle %s references missing file %s\n" % (
            name, e.filename))
        exitCode += 1

sys.exit(exitCode)
