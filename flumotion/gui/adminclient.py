import sys
sys.path.insert(0, '../..')

import pygtk
pygtk.require('2.0')

import gobject
import gtk
import gtk.glade

from twisted.internet import gtk2reactor
gtk2reactor.install()

from twisted.internet import reactor
from twisted.spread import pb

from flumotion.twisted import pbutil
from flumotion.server import admin   # Register types

class AdminInterface(pb.Referenceable, gobject.GObject):
    __gsignals__ = {
        'connected' : (gobject.SIGNAL_RUN_FIRST, gobject.TYPE_NONE, ()),
    }

    def __init__(self):
        self.__gobject_init__()
        self.factory = pb.PBClientFactory()
        cb = self.factory.login(pbutil.Username('admin'), client=self)
        cb.addCallback(self.gotPerspective)

    def gotPerspective(self, perspective):
        self.remote = perspective

    def remote_initial(self, clients):
        self.clients = clients
        self.emit('connected')
gobject.type_register(AdminInterface)

class Window:
    def __init__(self, port):
        self.connect(port)
        self.create_ui()
        
    def create_ui(self):
        self.wtree = gtk.glade.XML('../../data/ui/admin.glade')
        window = self.wtree.get_widget('main_window')
        window.connect('delete-event', self.close)
        window.show_all()
        self.component_view = self.wtree.get_widget('component_view')
        self.component_model = gtk.ListStore(str)
        self.component_view.set_model(self.component_model)

        col = gtk.TreeViewColumn('', gtk.CellRendererText(), text=0)
        self.component_view.append_column(col)
        
        self.wtree.signal_autoconnect(self)

    def connected_cb(self, admin):
        for client in admin.clients:
            iter = self.component_model.append()
            self.component_model.set(iter, 0, client.name)
            
    def connect(self, port):
        self.admin = AdminInterface()
        self.admin.connect('connected', self.connected_cb)
        reactor.connectTCP('localhost', port, self.admin.factory)
        
    def menu_quit_cb(self, button):
        self.close()

    def close(self, *args):
        reactor.stop()
        
if __name__ == '__main__':
    port = int(sys.argv[1])
    win = Window(port)
    
    reactor.run()
