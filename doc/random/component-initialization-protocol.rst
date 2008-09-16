.. contents::

=================================
Component Initialization Protocol
=================================

This file documents the protocol used by the component base classes to
produce initialized components. These descriptions are not the only
tasks that the methods perform, but they are the documented points of
extensibility. An alternate (overridden) implementation of these methods
must perform the named tasks.

For more information on object protocols, see
http://www2.parc.com/csl/groups/sda/publications/papers/Kiczales-OOPSLA92/.


Component creation
==================

A component object gets created using a factory function.
This factory function is called the "entry point" of a component type.
This entry point is declared in the registry section for that component type.

The manager invokes the worker's remote_create() method.
The worker then spawns a job in which to run this component.
It calls the factory function with the config dictionary as the sole argument.

In practice all components in flumotion's repository are set to have the
component class as an entry point. This allows the __init__ in the
BaseComponent class to handle entry point requests. To allow for
extensibility, there is a protocol that __init__ is expected to follow
to initialize the component.

BaseComponent
=============

Implementations
---------------

__init__(self, config)
    This method is expected to produce an initialized component, ready
    to go happy.

    First, the config is set as self.config.

    Then the implementation calls every init() method of any of the
    subclasses in the hierarchy.

    The component's mood should be set to waking, initially.

    After that, plugs are instantiated and started, and self.plugs is
    initalized.

    Invokes all defined do_check methods on the self's class and
    superclasses, in order from least to most specific. The do_check()
    methods may return deferreds; they will be chained.

    After the do_check() methods are invoked, the do_setup() methods
    will be invoked in the same way.

    Any errors encountered during setup should be proxied through state
    messages, and the mood set accordingly.

stop(self)
    Stops a component. Will call do_stop functions in order from most to
    least specific, chaining their maybeDeferred returns. Returns a
    deferred that will fire when the component has stopped.

Interface
---------

init(self)
    Any instance variables needed by a subclass should be declared in
    this method. There is no need to chain up.

check_properties(self, properties, addMessage)
    A helper vmethod called by BaseComponent's do_check() that includes
    the properties in the arguments. The addMessage argument is a
    function that will call self.addMessage, additionally raising an
    exception if the message is of level ERROR.

    This procedure is called with twisted.internet.defer.maybeDeferred, so
    all exceptions thrown by this procedure will be caught, and it is
    acceptable (although not required) to return a deferred.

do_check(self)
    This method has no requirements. It is implementation-specific.
    It can be used to check various requirements, or known bugs in certain
    versions of software.

    If this method adds any error messages to the component state,
    this will automatically trigger a mood change to sad, which will
    eventually raise a ComponentSetupError before the setup stage. If
    there is a fatal problem that can't be expressed with a message,
    this method should go to sad and raise ComponentSetupError itself.

    If there is nothing, or only warnings, the method should return a
    result. After this call, a call to setup() will succeed, in theory.

    There is no need to chain up in a do_check() implementation.

do_setup(self)
    This method has no requirements. It is implementation-specific.
    After this call, the component should have created all resources and
    started all processes.

    Once all do_setup() methods have been called (and their returned Deferred
    fired, if any), setup_completed() will be called.

    There is no need to chain up in a do_setup() implementation.

setup_completed(self)
    This method sets the component mood to happy. Subclasses should override
    if they wish to have other behaviour.


do_stop(self)
    Implementations should make sure that a succesful stop sets the mood to
    sleeping.

    There is no need to chain up in a do_stop() implementation.


Feed components
===============

A feed component is a component that has a pipeline. Its initialization
protocol provides a mechanism for creating and initializing the
pipeline.

Implementations
---------------

do_setup(self)
    This method will instantiate a pipeline and then allow the object a
    chance to do any further initialization after the pipeline is
    created. It does this by calling the following two methods:

      FeedComponent.create_pipeline(self)
      FeedComponent.set_pipeline(self, pipeline)

    Once the pipeline reaches PLAYING, the component mood will be set to happy.

setup_completed(self)
    FeedComponent overrides this method to do nothing; setting the component
    mood to happy is done in reaction to the pipeline reaching PLAYING instead.

provide_master_clock(self, port)
    Export the component's clock on the given UDP port, which may be
    zero to allow random port selection. Returns the ip, port, base_time
    clocking information. May be called at any time.

set_master_clock(self, ip, port, base_time)
    For components that require a clock, but are not selected as the
    master clock, this method will be called to tell the component about
    the clock to slave to; a gst.NetClientClock will be created to
    slave to this master. This call may be made at any time. If the
    component needs a clock, it will not produce data until
    set_master_clock is called once. Calling it again with different
    master clock info will restart the pipeline.

Interface
---------

create_pipeline(self)
    This method should return a GstPipeline object. It is a pure virtual
    method.

set_pipeline(self, pipeline)
    The base implementation of this method will set self.pipeline to
    pipeline and will connect to signals, the bus, etc. Subclass
    implementations should chain up to this method first.

make_message_for_gstreamer_error(self, gerror, debug)
    Make a flumotion error message to show when a GStreamer error occurs.
    The base implementation makes a generic message; a component might want
    to specialize this method to handle certain known errors.
    Implementations should return the new message.


Parse-launch components
=======================

Parse-launch components construct their pipelines via strings. This
protocol provides a mechanism whereby subclasses have a convenient
interface for producing these strings, and for configuring themselves
once the pipeline is created.

Implementation
--------------

create_pipeline(self)
    Calls the following method:

      ParseLaunchComponent.get_pipeline_string(self, properties)

set_pipeline(self, pipeline)
    Chains up to the parent, then calls the following method:

      ParseLaunchComponent.configure_pipeline(self, pipeline, properties)

Interface
---------

get_pipeline_string(self, properties)
    Must return a string, the pipeline template. Properties is a dict from
    self.config['properties'] (i.e., the component properties, without the
    name, type, parent, etc.). Pure virtual.

configure_pipeline(self, pipeline, properties)
    Called so that subclasses can manipulate the pipeline directly if
    needed. Defaults to doing nothing.
