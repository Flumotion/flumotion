import sys
import httplib

import gtk

win = gtk.Window()
win.set_title('Gtk Streaming Client')
win.connect('delete-event', lambda *x: sys.exit(0))
image = gtk.Image()
win.add(image)

win.show_all()


def data_get_cb(data):
    #print 'New data', len(data)
    loader = gtk.gdk.PixbufLoader('jpeg')
    loader.write(data)
    loader.close()

    pixbuf = loader.get_pixbuf()
    image.set_from_pixbuf(pixbuf)

d = ''


def readsome(f):
    global d

    data = f.readline()
    if data == '--ThisRandomString\n':
        f.readline()
        f.readline()
        data_get_cb(d)
        d = ''
        return True

    d += data
    return True

if __name__ == '__main__':
    host = sys.argv[1]
    port = sys.argv[2]
    h = httplib.HTTP(host, port)
    h.putrequest('GET', '/')
    h.endheaders()
    code, m, msg = h.getreply()
    f = h.getfile()

    f.readline()
    f.readline()
    f.readline()

    gtk.idle_add(readsome, f)
    gtk.main()
