# worker/main.py: main function of flumotion-worker

import optparse
import os

from twisted.internet import reactor

from flumotion.utils import log
from flumotion.worker import worker

def main(args):
    parser = optparse.OptionParser()

    group = optparse.OptionGroup(parser, "Worker options")
    group.add_option('-m', '--manager-host',
                     action="store", type="string", dest="host",
                     default="localhost",
                     help="Manager to connect to [default localhost]")
    group.add_option('-p', '--manager-port',
                     action="store", type="int", dest="port",
                     default=8890,
                     help="Manager port to connect to [default 8890]")
    group.add_option('-u', '--username',
                     action="store", type="string", dest="username",
                     default="",
                     help="Username to use")
    group.add_option('-d', '--password',
                     action="store", type="string", dest="password",
                     default="",
                     help="Password to use, - for interactive")
    
    parser.add_option_group(group)
    group = optparse.OptionGroup(parser, "Job options")
    group.add_option('-j', '--job',
                     action="store", type="string", dest="job",
                     help="Run job")
    group.add_option('-w', '--worker',
                     action="store", type="string", dest="worker",
                     help="Worker unix socket to connect to")
    parser.add_option_group(group)
    
    log.debug('manager', 'Parsing arguments (%r)' % ', '.join(args))
    options, args = parser.parse_args(args)

    if options.job:
        # we were started from the worker as a job
        _start_job(options)
    else:
        # we are the main worker
        _start_worker(options)

def _start_job(options):
    from flumotion.worker import job
    job_client_factory = job.JobClientFactory(options.job)
    reactor.connectUNIX(options.worker, job_client_factory)
    log.debug('job', 'Starting reactor')
    reactor.run()
    log.debug('job', 'Reactor stopped')

def _start_worker(options):
    log.debug('worker', 'Connecting to manager %s:%d' % (options.host, options.port))

    # create a brain and have it remember the manager to direct jobs to
    brain = worker.WorkerBrain(options.host, options.port)

    # connect the brain to the manager
    reactor.connectTCP(options.host, options.port, brain.worker_client_factory)
    brain.login(options.username, options.password or '')

    log.debug('worker', 'Starting reactor')
    reactor.run()

    log.debug('worker', 'Reactor stopped, shutting down jobs')
    # XXX: Is this really necessary
    brain.job_heaven.shutdown()

    pids = [kid.getPid() for kid in brain.kindergarten.getKids()]
    
    log.debug('worker', 'Waiting for jobs to finish')
    while pids:
        pid = os.wait()[0]
	# FIXME: properly catch OSError: [Errno 10] No child processes
        pids.remove(pid)

    log.debug('worker', 'All jobs finished, closing down')
