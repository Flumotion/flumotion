import gtk

class HTTPStreamerUI:
    def button_click_cb(self, button):
        print 'Button clicked'
        
    def render(self):
        button = gtk.Button('Click me')
        button.connect('clicked', self.button_click_cb)
        button.show()
        return button

GUIClass = HTTPStreamerUI
