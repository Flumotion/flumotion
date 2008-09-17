.. contents:: Table of Contents

============================================
 Developer introduction guide for Flumotion
============================================

This guide is written for people who wishes to participate and
contribute to the Flumotion project.


Getting started
===============

This section describes how you'll get started as a developer. It means fetching the sources, building,
and running.

Getting your development environment installed
----------------------------------------------

Create a directory tree to work in::

  $ cd; mkdir -p flu/unstable.stable; cd flu/unstable.stable

Check out jhbuild from cvs and install it::

  $ svn co http://svn.gnome.org/svn/jhbuild/trunk jhbuild && cd jhbuild && make -f Makefile.plain instal

Download the jhbuildrc file::

  $ cd; wget --no-check-certificate -O .jhbuildrc.flu "https://code.fluendo.com/flumotion/trac/file/flumotion/trunk/misc/jhbuildrc.flu?format=txt"

Download the correct modules file::

  $ cd ~/flu/; wget --no-check-certificate -O flu.unstable.stable.modules "https://code.fluendo.com/flumotion/trac/file/flumotion/trunk/misc/flu.unstable.stable.modules?format=txt"

Run::

  $ cd; bin/jhbuild -f .jhbuildrc.flu build flumotion

When this is done, you can start a shell in your new environment::

  $ bin/jhbuild -f .jhbuildrc.flu shell

From here you can run the server, the admin, flumotion-inspect, ...

If you want to test if you have a good build of flumotion, you can do (inside the jhbuild shell)::

  cd flu/$flavor/src/flumotion; make check

If later on you want to update to the latest code, you should repeat step 4 to update the modules file, and step 5 to rebuild everything.

To make it easier on your typing fingers, add this to your .bash_profile::

 alias jhb-flu="jhbuild -f $HOME/.jhbuildrc.flu.unstable.stable"

Then you can use jhb-flu as a shortcut that's easier to remember. 

Running a Manager with a worker
-------------------------------
Once everything is built and installed, you can try this to start the server::

  flumotion-manager -v -T tcp conf/managers/default/planet.xml

Note that the command above needs to be run from the root of you flumotion checkout.

On a separate terminal, do the following::

  flumotion-worker -v -T tcp -u user -p test

If there are no errors you should have a manager with a worker ready

Starting flumotion-admin
------------------------
If you followed the steps on the previous section you should be able to connect
to the manager you created using the following command::

  flumotion-admin

Which should run the graphical flumotion administration tool.
It should present you with a greeter. Choose the option: "Connect to a running manager". 
Click Forward. In the next page, disable the "Secure connection via SSL", Click Forward. 
Enter "user" as the username and "test" as the password. Click Forward.

You are now connected to the manager you created and should be presented with the 
configuration assistant which allows you to create a new flow.

Click on Forward until the assistant is finished at which point you should have a working flow.

Languages and Frameworks 
========================

This is a list of languages, frameworks and external libraries we use inside of Flumotion.
The list presented below includes a list of essential parts which are required to know to
efficiently contribute to Flumotion.

Python
------

Python is the primary programming language used to develop Flumotion.
Proficiency in Python is essential to be able to understand and extend
the sources.

Python is an open source project and is used widely in the open source 
community and thus there is plenty of freely available training material
on the web.

The following material is recommended to get started:

- `Official Python tutorial <http://docs.python.org/tut/tut.html>`_ 
- `Dive Into Python <http://diveintopython.org/toc/index.html>`_
- `Think like a Computer Scientist <http://openbookproject.net/thinkCSpy/index.xhtml>`_

Remember that all newly written Python code written must follow the `Style Guide`_.

C
-
A small part of Flumotion is written in C. There are mainly two reasons for
not writing the code in Python:

 - There are no existing python bindings available for a C library
 - Performance, Python cannot do it efficiently.

The general policy is that you should avoid writing code in C before you have
profiled the Python code and know that it's going to be part of a performance 
sensitive part. Do not use C unless you have a very good reason to do so.

GLib & GObject
--------------
GLib and GObject provides the foundation to both Gtk and GStreamer.
Things which are important to understand here are:

- signal connection and callbacks
- property access and modification
- general event loop understanding (idle, timeout, io input)


Gtk
---

- Boxing model from gtk+, vbox/hbox/table/alignment
- Dialogs/MessageDialogs
- UIManager/ActionGroup/Action
- FileChooser
- Packing
- Mnemonics/Keyboard accelerators
- Label/Pango Markup Stock icons
- Treeview (model, view, columns, cellrenderers)
- Textview (buffers, iters)


GStreamer
---------

- Elements
- Pipeline
- parse launch syntax
- Playing states
- Bus + Messages


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
  - perspective\_ and view\_ methods
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
FIXME


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
Trac is web interface and a central point of the development process.
The most important parts of the trac are:

- Timeline: `Timeline`_
- Code browser: `Code Browser`_
- Reporting a new ticket: `Open a new Ticket`_
- Searching for existing tickets: `Existing tickets`_
- Wiki: Wiki_

Pastebin
--------
FIXME

IRC
---
Most of the development discussion takes place on the #fluendo channel on the 
`Freenode <http://www.freenode.net/>`_ IRC network.
There's a irc interface to the buildbot interface called **flubber** which will inform you when 
the build brakes. The logic to find out who broke the build is rather fragile and the buildbot 
will sometimes blame the wrong person.

Mailing lists
-------------

If you're a contributor to Flumotion you should subscribe to both the flumotion-devel and the 
flumotion-commit mailing lists.
The web interface for subscribing to the mailing lists can be found `here
<http://lists.fluendo.com/mailman/listinfo/>`_.

Creating a ticket
-----------------

If you found a problem or if you already fixed a problem you should create a new ticket.
Before opening a ticket remember to check if there is any existing tickets open already.
  
Links: `Open a new Ticket`_

Generating a patch
------------------
FIXME

Reviewboard
-----------
FIXME

Committing
----------

When you have your code reviewed you're ready to check it into subversion.
First, generate a changelog using either prepare-ChangeLog::

  $ prepare-ChangeLog

or moap::

  $ moap cl pr

You should now end up with an auto-generated entry in the ChangeLog file.
Open it with your favorite editor and describe what you've just done, an example
of a good ChangeLog entry is::

 2006-05-25  Thomas Vander Stichele  <thomas at apestaart dot org>

	* flumotion/admin/gtk/client.py:
	privatize and rename self._sidepane
	clear the sidepane when a component goes to sleeping.
	Fixes #263.

The last part of the commit message, "Fixes #263" is a directive to trac. It means that
this commit solves the specified issue. It'll close the ticket and add a comment to it
referencing the commit. Always include this directive if the commit closes a real bug.

.. _Open a new Ticket: https://code.fluendo.com/flumotion/trac/newticket 
.. _Wiki: https://code.fluendo.com/flumotion/trac/wiki
.. _Code Browser: https://code.fluendo.com/flumotion/trac/browser 
.. _Timeline: https://code.fluendo.com/flumotion/trac/timeline
.. _Style guide: https://code.fluendo.com/flumotion/trac/browser/flumotion/trunk/doc/random/styleguide
.. _Existing tickets: https://code.fluendo.com/flumotion/trac/report 
