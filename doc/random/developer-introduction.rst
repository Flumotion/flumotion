.. contents:: Table of Contents

.. _Open a new Ticket: https://code.fluendo.com/flumotion/trac/newticket 
.. _Wiki: https://code.fluendo.com/flumotion/trac/wiki
.. _Code Browser: https://code.fluendo.com/flumotion/trac/browser 
.. _Timeline: https://code.fluendo.com/flumotion/trac/timeline
.. _Style guide: https://code.fluendo.com/flumotion/trac/browser/flumotion/trunk/doc/random/styleguide
.. _Existing tickets: https://code.fluendo.com/flumotion/trac/report 
.. _Buildbot: http://build.fluendo.com:8070/

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

Once you have gstreamer installed on an uninstalled directory, you need to install flumotion the
same way. This time though, you get the code from subversion directly as this is the most up to date
code. So, let's start. create a folder and check it out::

  svn checkout https://code.fluendo.com/flumotion/svn/flumotion/trunk/ flumotion

First the build environment needs to be prepared::

  ./autogen.sh

Autogen might fail if you miss some dependencies. Normally you need the following:
- C compiler
- make
- libtool
- autoconf
- automake
- python
- gtk
- gstreamer
- pygobject
- pygtk
- gst-python
- kiwi

When the autogen script runs, you're almost ready, you just need to type::

  make

This will do a bunch of stuff, one of them is creating a script called **env** that is a small shell
script which prepares the environment to run flumotion properly.

So, once make is finished, type::

  $HOME/workdir/flumotion/env

and your environment is set up.


If you want to check out an installed flumotion, use the instructions found in the FIXME-JHBuild wiki page.

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

http://en.wikipedia.org/wiki/Automake

Shell / M
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
The web interface for subscribing to the `mailing lists
<http://lists.fluendo.com/mailman/listinfo/>`_.

Creating a ticket
-----------------

If you found a problem or if you already fixed a problem you should create a new ticket.
Before opening a ticket remember to check if there is any existing tickets open already.
  
Links: `Open a new Ticket`_

Generating a patch
------------------
To generate a patch use the svn diff command from the project root directory::

  svn diff

Review it carefully, it's usually easiest to do this by piping via colordiff and less::

  svn diff | colordiff | less -R 

If you have created new files, they won't show up. So remember to add them by doing::

  svn add new_file

When you're satisfied with the changes, save the patch to disk::

  svn diff > filename

filename can be anything, but it's recommended that you use a naming convention which scales.
For instance use **XX_vY.diff** where **XX** is the name of the bug and **Y** is an incremental counter.
For instance, if you're submitting the first patch to bug 2249 you will call it 2249_v1.diff

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

Updating translation
--------------------
To update the translations you can either use your normal editor (emacs,vim,eclipse etc)
or a specialized application for just translation (gtranslate)
Translations using gettext are stored in text-form in .**po** files and compiled into
.**gmo**/.**mo** files which used in runtime by applications.
The .**po** files are extracted from the source code, where special markers are used to
say that a string should be translated.

To update the .**po** files from the source code, issue the following command::

  make update-po

After that the translation should be up to date, normally just update one translation
at a time, so revert the changes to the .po files you are not interested in.
The flumotion.pot file is a template used for creating new translations.
The translations will be built (eg, compiled in .**gmo** files) when you install flumotion 
or when you just type::

  make 

If you want to test your translation and see how your application looks like, do the
following after making sure they are compiled::

  LANG=xx_XX.UTF-8 flumotion-admin

Where xx_XX is a language code, for instance::

  - ca_ES: Catalan (as spoken in Spain)
  - en_US: English (as spoken in USA), the default
  - es_ES: Spanish (as spoken in Spain)
  - sv_SE: Swedish (as spoken in Sweden)

Running unittests
-----------------
Flumotion comes with set of unit tests that are automatically run by BuildBot_ upon
each commit. It's highly recommended that you run all the tests before committing,
to avoid being embarrassed at buildbot when he complains that your checkin broke the build.

The tool to run unittests in python is called Trial, and is a part of the twisted framework.

You can the tests by typing the following::

  trial flumotion.test

Running the whole testsuite usually takes a couple of minutes, even on a fast machine,
running a part of it can be done by specifying a filename(s) or module name(s) as argument
to trial::

  trial flumotion.test.test_parts
  trial flumotion/test/test_parts.py

The commands above will do the same thing, running all tests in the tests_part.py file.
You can also run just a specific test of a specific test class::

  trial flumotion.test.test_parts.TestAdminStatusbar.testPushRemove

Jordi's material
================

FIXME: This should be moved and incorporated in sections above


How to try stuff
----------------
Once you have your environment setup, you may want to try stuff and to debug it.
The easiest thing to do is to start an admin. Then, from the GUI, you can create a manager and
worker, and then a flow from the wizard. See how to start an admin section for more information.
When you want to do more interesting things, you start a manager and, at least, a worker by
yourself, and then start an admin that connects to the manager. See how to start a manager and how
to start a worker section. Then, you import the flow you want to test.
Trick: An easy way to create flow examples is to run the wizard and then to export that flow. Then
you can modify it and import it. You can also find good examples in the flumotion-flowtester
project, in the data/flows directory. You can check that project from subversion::

  svn checkout https://code.fluendo.com/flumotion/svn/flumotion-flowtester/trunk/ flumotion-flowtester

In order to see more or less information, you can set the environment debug variable::

  export FLU_DEBUG=level

where level is one of 1,2,3,4,5
if you set it to 4 (FLU_DEBUG=4) it will output everything except info messages (4 is the debug
level). With 5, it will output even the info messages. 1 will output only errors.
Then, what you do is edit the .py files and write stuff to the debug level on the log. This way you
can localize the problem and see some values.
In order to write to the debug, you will usually do::

  self.debug(message)

as almost every object inherits from the Logger class.
When looking for a gstreamer problem, you should try to find the pipeline. This is usually created
on the component at the get_pipeline_string function. You can get it from there or write it to the log.
Then, you can run the pipeline using the gst-launch to see if this is the problem (see some things
more about gstreamer).


How to setup external projects
------------------------------
If you have external projects, you have to set up an additional variable, that is the
FLU_PROJECT_PATH, that should contain your project directory, for example::

  FLU_PROJECT_PATH=$HOME/workdir/myproject

This way the components of the project will be available on the manager and workers.
How to start a manager
This is the command line for starting a manager with maximum debug level, provided that you had
set up the right environment::

  FLU_DEBUG=5 flumotion-manager conf/managers/default/planet.xml > /tmp/flumotion-manager.log 2>&1

after that, open another console and do::

  tail -f /tmp/flumotion-manager.log

to see the output.

How to start an admin
---------------------
This is the command line for starting an admin with maximum debug level, provided that you had
set up the right environment::

 FLU_DEBUG=5 flumotion-admin > /tmp/flumotion-admin.log 2>&1

If you had started a manager, you can connect to it from the admin. Otherwise, you can create a
manager and worker from the admin.
When no flows has been set up, the admin will start the wizard. If you want to create a test flow,
you can use the wizard. If you already have a flow you want to test, skip the wizard and import the
flow.
From the admin, you can use the debug and write debug marker options in order to change the
debug level of components and to write a mark on the log. This last thing is very useful as the log
contains lots of lines and you may be interested in only one part. Moreover, when not all the
workers are at the same computer, the clock may not be synchronized and this marker will help you
localize the error.

Changing the mood of a component
--------------------------------
Components have different moods:

- sleeping
- waking
- happy
- hungry
- lost
- sad

Some times you want a component to be in a specific mood for testing purposes. Here are a couple
of tricks:
How to make a component:

- **sad**: send a kill SIGSEV (11) to its job
- **lost**: send a STOP signal to its job
- **sleeping**: send a TERM signal to its job
- **hungry**: connect it to a lost component

In order to know the pid of the job that is running the component, you have two options:
1. Open the admin and look the pid column on the UI interface.
2. Do a "ps aux | grep flumotion-job" and find out which is the process you want to send a signal.

How to run pychecker
--------------------
For every commit, a tool called pychecker is run against the code in order to find bugs on it. So, it is
a good idea to run it against your code before any commit. I would recommend to install pychecker from CVS 
as there are a couple of bugs that has been fixed there that flumotion uses. 
See more info at the `pychecker homepage <http://pychecker.sourceforge.net/>`_.

The way to run it is::

  make pychecker

Replace flumotion/admin/gtk/client.py for the path to the file you want to check.

Generating API documentation
----------------------------
By default, flumotion contains documentation for the basic classes as html pages. This
documentation, very useful when writing new components, is not that useful when debugging or
learning the internals, so you may want to have all the classes in the project documented as html
pages, with tree hierarchies, links, etc.
All this documentation is generated using epydoc. In order to change the input files for the epydoc,
you have to edit the doc/reference/Makefile.am file and modify the MODULE_FILES variable as :

  MODULE_FILES = $(shell cd $(top_srcdir) && find flumotion | grep

3I am sorry I can not give more information on this specific topic, but I did not take notes when I installed pychecker
and applied the patches, so I can not give a better advice.

  py | grep -v .svn | grep -v cache | grep -v pyc | grep -v __init__ | grep -v "~" | sort)

Do not commit this changes as this is only for you to understand the internals of flumotion.

Invoking remote component methods
---------------------------------
As you learn flumotion, you'll realized that components have a remote interface that can be called.
This remote interface is usually for the manager but you can also call it from the command line by
using the flumotion-command utility. For example, for calling the method setFluDebugMarker on
the producer-video component, you could open a terminal and type::

  flumotion-command -m user:test@localhost:7531 invoke /default/producer-video setFluDebugMarker s "HOLA"

This will make the producer-video component to write “HOLA” on the log. user and test are the
username and the password for logging into the manager that is running on localhost and listening
on the port 7531.
Flumotion-inspect
Like gstreamer-inspect, flumotion-inspect show you a list of configured values and modules that are
registered::

  flumotion-inspect

You can also call flumotion-inspect on a component in order to know more about it::

  flumotion-inspect component

Applying a patch
----------------
If the patch has been created as explained before, you can patch the project as:

  patch -p0 < /tmp/flumotion-##.patch

You can always revert to trunk by using svn revert.

How to use moap (checking in changes)
-------------------------------------
For committing changes to subversion, we use moap4. Moap is a tool that generates a Changelog
file from all the changes and, after we edit that file, it commits to the repository the changes (and
the Changelog itself). Moap does more things than that, but these are the features we are interested
now.
So, once we have changes that had to be committed, we generate the Changelog by:

  moap changelog prepare

Then we edit the Changelog file by using our preferred editor. If there are files we do not want to
commit, we just have to remove them from the latest entry in the Changelog file. Moap will only
commit the files that are in the latest entry of the Changelog.
If you created new files, you'll realize that they do not appear on the Changelog. You need to add
them before to the repository, by doing svn add.
Once you are ready, you commit by::

  moap changelog checkin

Take in mind that, if you are writing a patch for a ticket in the trac, writing "Fixes #x" on the
Changelog file, where x is the ticket number, will update the trac ticket.
If you decide not to commit anything, you can always revert the Changelog file to the previous one
by doing svn revert.

Further documentation
---------------------
On the svn flumotion project there is a random docs directory. Some info there is very useful and
some may be outdated. You can read it from your checkout directory or online from `here
<https://code.fluendo.com/flumotion/trac/browser/flumotion/trunk/doc/random/>`_.

Also, you could checkout the flumotion-doc project and build the most up to date documentation
yourself (by using autogen.sh and make, as usual)::

  svn checkout https://code.fluendo.com/flumotion/svn/flumotion-doc/trunk flumotion-doc


