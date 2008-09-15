============================================
 Developer introduction guide for Flumotion
============================================

This guide is written for people who wishes to participate and
contribute to the Flumotion project.


Getting started
===============

Getting your development environment installed
----------------------------------------------
FIXME: Add content from UsingJHBuild


Running a Manager with a worker
-------------------------------

Starting flumotion-admin
------------------------

Programming Languages
=====================

Python
------

Python is the primary programming language used to develop Flumotion.
Proficiency in Python is essential to be able to understand and extend
the sources.

Python is an open source project and is used widely in the open source 
community and thus there is plenty of freely available training material
on the web.

The following material is recommended to get started:
- http://docs.python.org/tut/tut.html Official Python tutorial
- http://diveintopython.org/toc/index.html Dive Into Python
- http://openbookproject.net/thinkCSpy/index.xhtml

C
-
A small part of Flumotion is written in C. There are mainly two reasons for
not writing the code in Python:
 - There are no existing python bindings available for a C library
 - Performance, Python cannot do it efficiently.

The general policy is that you should avoid writing code in C before you have
profiled the Python code and know that it's going to be part of a performance 
sensitive part. Do not use C unless you have a very good reason to do so.

Frameworks / External libraries
===============================

This is a list of frameworks and external libraries we use inside of Flumotion.
The list presented below includes a list of essential

GLib & GObject
--------------
GLib and GObject provides the foundation to both Gtk and GStreamer.
Things which are important to understand here are:
- signal connection and callbacks
- property access and modification
- general event loop understanding (idle, timeout, io input)


Gtk
---
Boxing model from gtk+, vbox/hbox/table/alignment
Dialogs/MessageDialogs
UIManager/ActionGroup/Action
FileChooser
Packing
Mnemonics/Keyboard accelerators
Label/Pango Markup Stock icons
Treeview (model, view, columns, cellrenderers)
Textview (buffers, iters)


GStreamer
---------
Elements
Pipeline
parse launch syntax
Playing states
Bus + Messages


Glade 
------
Defining signals. Avoiding hardcoding of width/height
Reading the HIG and applying it consistently within the project


Kiwi
----
Proxy/View/Delegate


Twisted
-------
Twisted is an asynchronous framework for Python.
It's an integral part of Flumotion and is used for many different things.
This is what you need to know:
- deferreds
- reactor:
  - mainloop integration
  - calllater
  - listenTCP
- spread/pb:
  - callRemote
  - perspective/view_ methods
  - jelly registration
  - clientfactory/serverfactory
- cred: portal/realm
- python: namedAny, log
- trial: invoking, deferred tests
- zope.interfaces: implement new interfaces

Development process
===================

Build system
------------
Makefile
Basic Autotools


Shell / M4
----------
Shell and M4 are languages used in minor places in the Flumotion code base.
Mainly by the build process, which forms a part of autotools.

Makefile
--------


Subversion
----------
The source code of Flumotion is stored in a Subversion repository.
You need to be able to use subversion properly.

The SVN book is a good introduction to SVN.

Understand and query information from the web frontend.

Pay special attention to the Basic Work Cycle in the third Chapter:

  * checkout: FIXME link
  * status
  * diff
  * revert
  * update
  * commit

Trac
----

Pastebin
--------

IRC / Mailing lists
-------------------

Creating a bug report
---------------------

Generating a patch
------------------

Reviewboard
-----------

Style guide
-----------
Link to url: https://code.fluendo.com/flumotion/trac/browser/flumotion/trunk/doc/random/styleguide
