import pygtk
pygtk.require('2.0')

import gobject


class Foo(gobject.GObject):
    __gproperties__ = {'frob': (
        bool, 'frob', 'frob foo', False,
        gobject.PARAM_READWRITE|gobject.PARAM_CONSTRUCT)}

    def __init__(self):
        gobject.GObject.__init__(self)

    def do_get_property(self, prop):
        print self, prop
        return self.properties[prop.name]

    def do_set_property(self, prop, value):
        print self, prop, value
        if not getattr(self, 'properties', None):
            self.properties = {}
        self.properties[prop.name] = value
gobject.type_register(Foo)

x = Foo()

# should return False, instead raises an AttributeError because the
# object the property was set on is not the object we received from the
# constructor. Strange.
print x.get_property('frob')
