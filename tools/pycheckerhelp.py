# lots of little imports done before anything else so that
# we don't get weird stray module errors

import pygtk
pygtk.require('2.0')

import gobject

import gtk
import gtk.gdk
import gtk.glade

#import gst
#import gst.interfaces

import pyexpat

# fake out pychecker
loop = gobject.MainLoop()
gtk.main_iteration()

m = pyexpat
