
.. contents:: Table of Contents

.. _Open a new Ticket: https://code.flumotion.com/trac/newticket 
.. _Wiki: https://code.flumotion.com/trac/wiki
.. _Code Browser: https://code.flumotion.com/trac/browser 
.. _Timeline: https://code.flumotion.com/trac/timeline
.. _Style guide: https://code.flumotion.com/trac/browser/flumotion/doc/random/styleguide
.. _Existing tickets: https://code.flumotion.com/trac/report 
.. _Buildbot: http://build.fluendo.com:8070/
.. _Trial: http://twistedmatrix.com/trac/wiki/TwistedTrial
.. _Twisted: http://twistedmatrix.com/
.. _Gtk: http://www.gtk.org/
.. _JHBuildWiki: https://code.flumotion.com/trac/wiki/UsingJHBuild
.. _GLib: http://library.gnome.org/devel/glib/
.. _GObject: http://library.gnome.org/devel/gobject/
.. _GStreamer: http://www.gstreamer.net/
.. _PEP8: http://www.python.org/dev/peps/pep-0008/
.. _TwistedManual: http://twistedmatrix.com/projects/core/documentation/howto/index.html
.. _GStreamerManual: http://gstreamer.freedesktop.org/data/doc/gstreamer/head/gstreamer/html/
.. _KiwiHowto: http://www.async.com.br/projects/kiwi/howto/
.. _Glade2Tutorial: http://www.kplug.org/glade_tutorial/glade2_tutorial/glade2_introduction.html
.. _PyGTKManual: http://www.pygtk.org/docs/pygtk/
.. _GtkManual: http://library.gnome.org/devel/gtk/stable/
.. _Moods: https://code.flumotion.com/trac/browser/flumotion/doc/random/moods

============================================
 Developer introduction guide for Flumotion
============================================

This guide is written for people who wishes to participate and
contribute to the Flumotion project.


Getting started
===============

This section describes how you'll get started as a developer. It means fetching the sources, 
building, and running.

Getting your git environment configured
---------------------------------------

Once you have installed git, you need to set your committer's name and email in git's global configuration.

  - Set commiter name and email:::

    $ git config --global user.name "Your Name Comes Here"
    $ git config --global user.email you@flumotion.com

You should also configure the following options and aliases to help you in the development.

  - Get a colored diff by default, both in the console and the UI::

    $ git config --global color.ui auto
    $ git config --global color.diff auto

  - Only push the tracking branch: ::

    $ git config --global push.default tracking

  - Always rebase instead of mergins for pulls in branches tracking other branches::

    $ git config --global branch.autosetuprebase always

  - Aliases::

    $ git config --global alias.l "log --oneline --decorate --graph"
    $ git config --global alias.d "diff --color--words"
    $ git config --global alias.s "status --short"
    $ git config --global alias.a "add -u"
    $ git config --global alias.c "commit"

Getting your development environment installed
----------------------------------------------

Once you have gstreamer installed on an uninstalled directory, you need to install flumotion the
same way. This time though, you get the code from git directly as this is the most 
up to date code. So, let's start. create a folder and check it out::

   git clone ssh://git@code.flumotion.com/~/flumotion.git

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

This will do a bunch of stuff, one of them is creating a script called **env** that 
is a small shell script which prepares the environment to run flumotion properly.

So, once make is finished, type::

  $HOME/workdir/flumotion/env

and your environment is set up.


If you want to check out an installed flumotion, use the instructions found in the 
JHBuildWiki_ wiki page.

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

How to setup external projects
------------------------------
If you have external projects (such as flumotion-dvb), you have to set up an additional variable, 
that is the FLU_PROJECT_PATH, that should contain your project directory, for example::

  FLU_PROJECT_PATH=path/to/directory/

This way the components of the project will be available on the manager and workers. 

Flowtester
----------

Flowtester is a tool to easily test flumotion flows.
Flows can be handwritten or created by the configuration assistant.
The code lives in the "flumotion-flowtester" module::

  git clone ssh://git@code.flumotion.com/~/flumotion-flowtester.git

To run flowtester, just type::

  bin/flumotion-flowtester

From the build after checking out.
The main interface is a list of flows and buttons to create process and import different flows.
The idea is that the tool is used to maintain a large amount of flows which can be easily started.
The testing (QA) is done by the developer/user of the program by connecting to the stream and
verify that the stream is correct. A URL is provided to the stream which can be used to point
a web browser or a media player to.

Changing the mood of a component
--------------------------------

Components have different moods, see `Moods`_ for a complete description.

Some times you want a component to be in a specific mood for testing purposes. Here are a couple
of tricks on how to change the mood of a component:

- **sad**: send a SIGSEV (11) signal
- **lost**: send a SIGSTOP (17) signal
- **sleeping**: send a SIGTERM (15) signal
- **hungry**: make the component to the right side lost

In order to know the pid of the job that is running the component, you have two options:
1. Open the admin and look the pid column on the UI interface.
2. Do a "ps aux | grep flumotion-job" and find out which is the process you want to send a signal.

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
GLib_ and GObject_ provides the foundation to both Gtk_ and GStreamer_.
Things which are important to understand here are:

- signal connection and callbacks
- property access and modification
- general event loop understanding (idle, timeout, io input)


Gtk
---

Gtk_ is a graphical toolkit, mainly known from the GNOME desktop environment.
It's used as the graphical interface for Flumotion.

- Boxing model from gtk+, vbox/hbox/table/alignment
- Dialogs/MessageDialogs
- UIManager/ActionGroup/Action
- FileChooser
- Packing
- Mnemonics/Keyboard accelerators
- Label/Pango Markup Stock icons
- Treeview (model, view, columns, cellrenderers)
- Textview (buffers, iters)

Use the PyGTKManual_ and the GtkManual_ as the main sources for information.

GStreamer
---------

- Elements
- Pipeline
- parse launch syntax
- Playing states
- Bus + Messages

The GStreamerManual_ explains this pretty good, while it is aimed at the C API it can
easily be reused by python programmers as the Python bindings are straight-forward.

Glade 
------
Defining signals. Avoiding hardcoding of width/height
Reading the HIG and applying it consistently within the project

Check out the Glade2Tutorial_ for some help to get started.

Kiwi
----
Proxy/View/Delegate

The KiwiHowto_ is pretty good here, even though it might be a bit outdated.

Twisted
-------
Twisted_ is an asynchronous framework for Python.
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

The TwistedManual_ explains most, if not all of these concepts.

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

Resources and Tools
===================

Git
---
The source code of Flumotion is stored in a Git repository.
You need to be able to use Git properly.

The Git Community book is a good introduction to Git.

Understand and query information from the web frontend.


Trac
----
Trac is web interface and a central point of the development process.
The most important parts of the trac are:

- Timeline: `Timeline`_
- Code browser: `Code Browser`_
- Reporting a new ticket: `Open a new Ticket`_
- Searching for existing tickets: `Existing tickets`_
- Wiki: Wiki_

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

Pastebin
--------
Pastebin is an online collaboration tool.
It allows you to easily distribute a piece of code to other developers so they can quickly
review it.
If you use ubuntu or debian it's strongly recommended that you install the package pastebinit
which can accept data from a pipe. Eg, to send a diff of your changes to pastebin it for review,
issue the following command:

  git diff | pastebinit

Which will output an url point to its pastebin entry.

Code Review
-----------
Codereview, or Reitveld is a free web tool for reviewing and discussion of a patch.
It requires a Google account for both uploader and reviewer. There's a script in the flumotion 
module which facilities this.
To upload your changes in the current git directory, issue the following command::

  python tools/codereview-upload.py

It will prompt you for your Google account information and a topic for the patch.
After that go to http://codereview.appspot.com and find the url for the patch.

API documentation
-----------------
Newly written code should be documented in the form of doc strings.
Check the API DOCS section of the `Style Guide`_ for more information.

The API documentation requires the use of epydoc and is generated during
a normal build if epydoc is installed.


Source code analysis 
--------------------
There are mainly two different tools which are analyzing the source to improve
quality and provide consistency across the code base.
PEP8_ is a Python document explaining the python coding style, it is generally
adopted in the whole Python community and as it is deemed important to write code
that follows it a test and a pre-commit verifying the consistency is used.
If you want to invoke it manually you can type the following::

  make check-local-pep8

PEP8 doesn't do any analysis of the code itself, instead another tool called
PyChecker is used for that. It is important that you have a recent version installed as
there are often improvements coming directly from the flumotion developers.

To run a pychecker test on your source code, type the following::

  make pycheck

See more info at the `pychecker homepage <http://pychecker.sourceforge.net/>`_.

Flumotion documentation
-----------------------
In the git flumotion project there is a random docs directory. Some info there is very useful and
some may be outdated. You can read it from your checkout directory or online from `here
<http://code.flumotion.com/cgit/flumotion/tree/doc/random>`_.

Also, you could checkout the flumotion-doc project and build the most up to date documentation
yourself (by using autogen.sh and make, as usual)::

  git clone ssh://git@code.flumotion.com/~/flumotion-doc.git

Development process
===================

Creating a ticket
-----------------

If you found a problem or if you already fixed a problem you should create a new ticket.
Before opening a ticket remember to check if there is any existing tickets open already.
  
Links: `Open a new Ticket`_

Generating a patch
------------------
To generate a patch, first review carefully your changes using the git diff command::

  git diff --color --word-diff

If you have created new files, remember to add them to the index::

  git add new_file

Stage your changes and review what's going to be committed::

  git add -u .
  git diff --staged --color --word-diff

Once everything is ready, commit your work::

  git commit

And finally, generate a patch in e-mail format with the commit::

  git format-patch HEAD~1

Committing
----------

When you have your code reviewed you're ready to push it to the origin repository.
First check which commits are going to be pushed from your local 'master' branch::

  git cherry -v oring/master

You can double check all the changes that are going to pushed to the remote repository::

  git diff -p oring/master

Finnaly, push your commits to the remote repository::

  git push origin master




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

  LANG=xx_YY.ZZ flumotion-admin

Where xx_YY is code combined of:

- xx: the language (ISO-639)
- YY: the geographical providing (ISO-3166)
- ZZ: the encoding, usually UTF-8

Some common examples:

- ca_ES: Catalan (as spoken in Spain)
- en_US: English (as spoken in USA), the default
- es_ES: Spanish (as spoken in Spain)
- sv_SE: Swedish (as spoken in Sweden)

Running unittests
-----------------
Flumotion comes with set of unit tests that are automatically run by BuildBot_ upon
each commit. It's highly recommended that you run all the tests before committing,
to avoid being embarrassed at buildbot when he complains that your checkin broke the build.

The tool to run unittests in python is called Trial_, and is a part of the twisted framework.

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

Note, some tests cannot be run under the default (select) reactor, since they
depend on the integration of the glib/gtk eventloop. If the test you tried
to run cannot be run, you need to specify the reactor, for instance::

  trial -r gtk2 flumotion.test.test_component_disker

Debugging
---------

All flumotion projects include plenty of debug messages, these are under normal conditions suppressed, but
can be enabled by setting an environment variable::

  export FLU_DEBUG=level

Where level is a number between 1 and 5. The higher the level, the more messages will be printed.
Debug level 1 will only output errors and 5 everything, including debug messages

In order to write to the debug, make sure that you subclass Logger.
Then you can just call::

  self.debug(message)

For a debugging message, or for an info message::

  self.info(message)
