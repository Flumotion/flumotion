import pygtk
pygtk.require('2.0')

# Install reactor, should move somewhere
from flumotion.twisted import gstreactor
gstreactor.install()

from epydoc.cli import cli
cli()
