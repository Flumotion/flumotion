#!/usr/bin/env python

import gobject
gobject.threads_init()

import pygst
pygst.require('0.10')
import gst

import time
import sys

class SlidingWindow:
    def __init__(self, size):
        self._window = [0.0] * size

        self._windowPtr = 0
        self._first = True

        # Maintain the current average, and the max of our current average
        self.max = 0.0
        self.average = 0.0
        self.windowSize = size

    def addValue(self, val):
        self._window[self._windowPtr] = val
        self._windowPtr = (self._windowPtr + 1) % self.windowSize

        if self._first:
            if self._windowPtr == 0:
                self._first = False
            return

        self.average = sum(self._window) / self.windowSize
        if self.average > self.max:
            self.max = self.average

class TheoraBench:
    def __init__(self, filename, outTemplate, width=None, height=None,
        framerate=None):
        self.framerate = None
        self.width = None
        self.height = None
        self.outfileTemplate = outTemplate

        # TODO: What's a reasonable windowSize to use?
        windowSize = 20
        self.window = SlidingWindow(windowSize)
        self.samples = 0
        self.data = ([], [], [])

        self.pipeline = pipeline = gst.Pipeline()

        self.bus = pipeline.get_bus()

        filesrc = gst.element_factory_make("filesrc")
        decodebin = gst.element_factory_make("decodebin")
        self.ffmpegcolorspace = gst.element_factory_make("ffmpegcolorspace")
        videorate = gst.element_factory_make("videorate")
        videoscale = gst.element_factory_make("videoscale")
        self.theoraenc = gst.element_factory_make("theoraenc")
        fakesink = gst.element_factory_make("fakesink")

        filesrc.set_property("location", filename)

        pipeline.add(filesrc, decodebin, self.ffmpegcolorspace, videorate,
                videoscale, self.theoraenc, fakesink)

        filesrc.link(decodebin)
        gst.element_link_many(self.ffmpegcolorspace, videorate, videoscale)
        structure = gst.Structure("video/x-raw-yuv")
        if height:
            structure['height'] = height
        if width:
            structure['width'] = width
        if framerate:
            structure['framerate'] = framerate
        caps = gst.Caps(structure)
        videoscale.link(self.theoraenc, caps)
        self.theoraenc.link(fakesink)

        decodebin.connect("new-decoded-pad", self._pad_added_cb)

    def _eos_cb(self, bus, msg):
        print "Done"
        fn = self.outfileTemplate % (self.width, self.height,
                float(self.framerate))
        print "Writing file: ", fn
        self.writeGraph(fn, self.data,
                "Frame number",
                "CPU Percentage required",
                ("Frame)",
                 "Sliding Average (%d frames)" % self.window.windowSize,
                 "Sliding Average Peak"))
        self.mainloop.quit()

    def writeGraph(self, filename, data, xlabel, ylabel, dataNames):
        # data is ([time], [average], [average_peak]) as percentages (floats)
        #out = open(filename, "w")
        #out.close()
        import matplotlib
        matplotlib.use('Agg')
        from matplotlib  import pylab
        length = len(data[0])
        pylab.plot(xrange(length), data[1])
        pylab.plot(xrange(length), data[2])
        pylab.axis([0, length-1, 0, 110])
        pylab.savefig(filename, dpi=72)
        pass

    def _error_cb(self, bus, msg):
        error = msg.parse_error()
        print "Error: ", error[1]
        self.mainloop.quit()

    def run(self):
        self.mainloop = gobject.MainLoop()
        self.bus.add_signal_watch()
        self.bus.connect("message::eos", self._eos_cb)
        self.bus.connect("message::error", self._eos_cb)

        self.pipeline.set_state(gst.STATE_PLAYING)
        self.mainloop.run()

    def _pad_added_cb(self, decodebin, pad, last):
        structure = pad.get_caps()[0]
        name = structure.get_name()
        if name.startswith('video/x-raw-'):
            sinkpad = self.ffmpegcolorspace.get_pad("sink")
            pad.link(sinkpad)
            #self.framerate = structure['framerate']

            sinkpad = self.theoraenc.get_pad("sink")
            srcpad = self.theoraenc.get_pad("src")

            sinkpad.add_buffer_probe(self._buffer_probe_sink_cb)
            srcpad.add_buffer_probe(self._buffer_probe_src_cb)

    def _buffer_probe_sink_cb(self, pad, buf):
        if not self.framerate:
            self.framerate = buf.get_caps()[0]['framerate']
            self.width = buf.get_caps()[0]['width']
            self.height = buf.get_caps()[0]['height']
        self._last_ts = time.time()
        return True

    def _buffer_probe_src_cb(self, pad, buf):
        processing_time = time.time() - self._last_ts

        self.window.addValue(processing_time)
        self.samples += 1

        if self.samples <= self.window.windowSize:
            return True # Ignore these, our sliding window isn't very smart

        self.data[0].append(processing_time * float(self.framerate) * 100.0)
        self.data[1].append(self.window.average * float(
            self.framerate) * 100.0)
        self.data[2].append(self.window.max * float(self.framerate) * 100.0)
        print "This frame: %.2f: %.2f%%. Average: %.2f%%. Peak: %.2f%%" % (
                processing_time,
                processing_time * float(self.framerate) * 100.0,
                self.window.average * float(self.framerate) * 100.0,
                self.window.max * float(self.framerate) * 100.0)
        return True

if len(sys.argv) == 2:
    framerates = [(30, 1),
                  (25, 1),
                  (25, 2), (None, None)]
    sizes = [(800, 600),
             (400, 300),
             (None, None)] # Other useful sizes here
    for framerate in framerates:
        for size in sizes:
            if framerate[1]:
                fr = gst.Fraction(framerate[0], framerate[1])
            else:
                fr = None
            infile = sys.argv[1]
            outfileTemplate = sys.argv[1] + ".%dx%d@%.2f.png"
            bench = TheoraBench(sys.argv[1], outfileTemplate, size[0],
                size[1], fr)
            bench.run()
else:
    print "Usage: %s filename.ogg" % sys.argv[0]
