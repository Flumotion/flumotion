#include <pygobject.h>

void pytrayicon_register_classes (PyObject *d);
extern PyMethodDef pytrayicon_functions[];

DL_EXPORT(void)
initpytrayicon(void)
{
    PyObject *m, *d;

    init_pygobject ();

    m = Py_InitModule ("pytrayicon", pytrayicon_functions);
    d = PyModule_GetDict (m);

    pytrayicon_register_classes (d);

    if (PyErr_Occurred ()) {
      Py_FatalError ("can't initialise module pytrayicon");
    }
}
