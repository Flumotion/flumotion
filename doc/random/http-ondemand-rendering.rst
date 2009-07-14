HTTP Ondemand Request Rendering
===============================


From File.render to producing content
-------------------------------------

Read this while looking at the visualisation at the bottom of the
file. The boxes there signify Deferreds. Each box has two sides: the
callback chain is on the left, the errback on the right.

The render method calls _startAuthentication, obtains a Deferred from
it and returns NOT_DONE_YET. _requestAuthenticated is attached as the
callback and _authenticationFailed as the errback.

The _requestAuthenticated method creates a new deferred (observe that
there's a line that goes into a box coming from it), puts
_renderRequest and _terminateRequest in it's callback chain and
_terminateRequest in the errback chain.

_renderRequest in turn calls do_prepareBody, which returns a new
Deferred, with dispatchMethod as the callback and with no errback
handler.

dispatchMethod either returns an empty string (for HEAD requests),
thus ending the processing of the Deferred obtained from
do_prepareBody, or calls _startRequest, that calls _metadataProvider,
that creates another Deferred

The errback for that Deferred swallows potential failures, so the
callback (_configureTransfer) is always fired.

_configureTransfer calls createProducerConsumerProxy, which obtains a
new Deferred (observe the box) and puts attachProxy in the callback
chain.

attachProxy returns NOT_DONE_YET, thus ending the do_prepareBody
Deferred chain. The _requestAuthenticated Deferred chain gets resumed,
and the next callback is called, it being _terminateRequest.

_terminateRequest checks if it got passed NOT_DONE_YET and if so,
assumes the transfer is in progress and does nothing.

Errors in authentication get signalled by the Deferred obtained from
_startAuthentication errbacking. The object doing authentication
already takes care of returning the correct status code to the client,
so the errback handler just swallows the failure.

Errors in starting the request are handled by the _terminateRequest
errback, that in case of getting a failure returns a HTTP 500 status
to the client and finishes the request.


Graphical explanation
---------------------

This abuse of artist-mode tries to visualise how does the request
processing in our http-server work::

          File.render
               |
               |
    httpauth._startAuthentication (returns NOT_DONE_YET)
               |
               | gets a Deferred
  +------------+--------------------------------------------------------------------------------+------------------------------+
  |                                                                                             |                              |
  |     _requestAuthenticated                                                                   |    _authenticationFailed     |
  |            |                                                                                |                              |
  |            | creates a new succesful Deferred                                               |                              |
  |+-----------+-----------------------------------------------------+------------------------+ | (does nothing, the request   |
  ||                                                                 |                        | |  is closed and the 404 is    |
  ||     _renderRequest                                              |   _terminateRequest    | |  written by the object       |
  ||           |                                                     |                        | |  doing authentication)       |
  ||           |                                                     |  (this does nothing    | |                              |
  ||     do_prepareBody                                              |   if it gets           | |                              |
  ||           |                                                     |   NOT_DONE_YET,        | |                              |
  ||           | creates a new Deferred                              |   gives HTTP 500 if    | |                              |
  ||+----------+-------------------------------------+----------- +  |   if gets a failure,   | |                              |
  |||                                                | no handler |  |   writes a string and  | |                              |
  |||                    (HEAD)                      |            |  |   finishes the request | |                              |
  |||    dispatchMethod--------- returns ''          |            |  |   if it gets a string) | |                              |
  |||          |                                     |            |  |                        | |                              |
  |||          | (non-HEAD)                          |            |  |                        | |                              |
  |||          |                                     |            |  |                        | |                              |
  |||          |                                     |            |  |                        | |                              |
  |||    _startRequest                               |            |  |                        | |                              |
  |||          |                                     |            |  |                        | |                              |
  |||          |                                     |            |  |                        | |                              |
  |||   _metadataProvider.getMetadata                |            |  |                        | |                              |
  |||          | (if no metadataProvider,            |            |  |                        | |                              |
  |||          |  defer.succeed())                   |            |  |                        | |                              |
  ||| +--------+--------------+--------------------+ |            |  |                        | |                              |
  ||| |                       |   metadataError    | |            |  |                        | |                              |
  ||| |                       | (swallows Failures)| |            |  |                        | |                              |
  ||| |                       +--------------------+ |            |  |                        | |                              |
  ||| | _configureTransfer                         | |            |  |                        | |                              |
  ||| |        |                                   | |            |  |                        | |                              |
  ||| |        |                                   | |            |  |                        | |                              |
  ||| |        |                                   | |            |  |                        | |                              |
  ||| | _rateController.createProducerConsumerProxy| |            |  |                        | |                              |
  ||| |        |                                   | |            |  |                        | |                              |
  ||| |        | (if no _rateController,           | |            |  |                        | |                              |
  ||| |        |  defer.succeed())                 | |            |  |                        | |                              |
  ||| | +------+-------------------+-------------+ | |            |  |                        | |                              |
  ||| | |   attachProxy            |  no handler | | |            |  |                        | |                              |
  ||| | |  (returns NOT_DONE_YET)  |             | | |            |  |                        | |                              |
  ||| | |                          |             | | |            |  |                        | |                              |
  ||| | +--------------------------+-------------+ | |            |  |                        | |                              |
  ||| +-----------------------+--------------------+ |            |  |                        | |                              |
  |||                                                |            |  |                        | |                              |
  ||+------------------------------------------------+----------- +  |                        | |                              |
  ||                                                                 |                        | |                              |
  ||   _terminateRequest                                             |                        | |                              |
  ||                                                                 |                        | |                              |
  |+-----------------------------------------------------------------+------------------------+ |                              |
  +---------------------------------------------------------------------------------------------+------------------------------+
