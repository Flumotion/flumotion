/*
 * _proctitle.c
 * 		
 * Python 2.X module to allow direct access to the
 * actual argv[] of the Python Process.
 * Used to display status, clear a password, etc
 * in /proc (ps) output. 
 * 
 * Copyright 2002 - 'Diesel' Dave 'Kill a Cop' Cinege <dcinege@psychosis.com>
 * GPL2 - Copyright notice may not be altered. 
 */

// This verison has only been tested on Linux. Please report your
// experiences with other OS's so portability changes may be added.

/*
 * How Linux works
 * A process's arguments are saved as strings in contiguous
 * memory. Each element is terminated by a 0. (Proper string array.)
 * During display by utils like 'ps' the 0's are converted into a
 * space. It is safe to over right and continue beyond
 * the end of all argvc's except the last.
 * 
 * For (possibly) better portability however the below functions
 * never write a string longer then the argv space allocated.
 * (Incase the memory is not contiguous)
 *
 * Strings shorter then the argv space are padded with 0's.
 * It instead spans the string to the next argv. (This is
 * actually done by proctitle.py when it splits a string into a list.)
 * 
 * IE: 
 *  p r o g r a m   a r g 1   a r g 2
 * | | | | | | | |0| | | | |0| | | | |0|
 * 
 *  O u r N e w B i g S t r i n g ! !
 * | | | | | | | | | | | | | | | | | |0|
 * 
 * The function will write this as:
 * 	argv[0] = "OurNewBi"
 * 	argv[1] = "gStri"
 * 	argv[2] = "ng!!"
 */


#include <Python.h>

static char **argv;
static int argc, argvlengths[1000], argvpositions[1000];	//FIX ME dc: How do we `argvlengths[argc]` or atleast pick a better array size?

extern void Py_GetArgcArgv(int *argc, char ***argv);

static void
_argv_lengths(void)
{	// Saves sizes of each argv to argvlengths[] and PyO_argvlen
	//
	// Argv length == strlen + 1. The zero byte can safely(?) be over
	// written *between* argv's to allow continguous lines.
	// This appears to be sane in Linux. If anything breaks across
	// platforms, this will likely be it.
	int i;
	char *p;

	for (i = 0; i < argc; i++) {
		p = argv[i];
		argvlengths[i] = 1;
		while (*p++) argvlengths[i]++;
		
		if (i > 0)
			argvpositions[i] = argvpositions[i - 1] + argvlengths[i - 1];
		else
			argvpositions[i] = 0;
	}
	argvlengths[--i]--;	// Trim the 0 off the last argv, lest we overflow.
}

static void
_argv_set(char **s, int start, int end)
{	// Fill entire argv range with string | zeros.
	int i, j;
	char *p = 0;

	for (i = start; i < end; i++) {
		p = *s; s++;
		for (j = 0; j < argvlengths[i]; j++)
			if (*p == 0)
				argv[i][j] = 0;
			else
				argv[i][j] = *p++;
	}
}

static PyObject *
argvlen(PyObject *self, PyObject *args)
{
	int i;
	PyObject *PyO_argvlen = PyList_New(argc);
	PyObject *PyO_argvpos = PyList_New(argc);
	PyObject *PyO_return = PyList_New(2);
	
	if (!PyArg_ParseTuple(args, ""))
		return NULL;   

	for (i = 0; i < argc; i++) {
	        PyList_SetItem(PyO_argvlen, i, Py_BuildValue("i", argvlengths[i] ));
		PyList_SetItem(PyO_argvpos, i, Py_BuildValue("i", argvpositions[i] ));
	}

	PyList_SetItem(PyO_return, 0, Py_BuildValue("O", PyO_argvlen));
	PyList_SetItem(PyO_return, 1, Py_BuildValue("O", PyO_argvpos));
	
	return PyO_return;
}
static char argvlen_doc[] =
"argvlen()\n\
\n\
Return a tuple of allocated space for each argv.";

static PyObject *
argvset(PyObject *self, PyObject *args)
{
	int start = 0, end, amt, i;
	char *sa[argc];
	
	PyObject *PyO_argvlist;

	if (!PyArg_ParseTuple(args, "O|i", &PyO_argvlist, &start))
		return NULL;   

	if (!PyList_Check(PyO_argvlist)) {
		PyErr_SetString(PyExc_ValueError, "object is not list type");
		return NULL;
	}

	amt = PyList_Size(PyO_argvlist);
	
	if ((amt + start) > argc)	// Never run beyond last allocated element
		amt = (argc - start);
	end = start + amt;	

	for (i = 0; i < amt; i++) {
		sa[i] = PyString_AsString(PyList_GetItem(PyO_argvlist,i));
	}

	_argv_set(sa,start,end);

	return Py_None;
}
static char argvset_doc[] =
"argvset(list,[start])\n\
\n\
Replace argv range with list. Optionally begin at element <start>";

static PyObject *
argvget(PyObject *self, PyObject *args)
{
	int start = 0, end = 0, amt = argc, i, j = 0;
	char s[1024];	// FIX ME dc:
	PyObject *PyO_argv;
	
	if (!PyArg_ParseTuple(args, "|ii", &start, &amt))
		return NULL; 

	if ((amt + start) > argc)	// Never run beyond last allocated element
		amt = (argc - start);
	end = start + amt;

	PyO_argv = PyList_New(amt);
	
	for (i = start; i < end; i++) {
		// Since we might have killed the \0 at the end of an argv
		// string we do this for sane results
		strncpy(s,argv[i],argvlengths[i]);
		s[argvlengths[i]] = 0;
	        PyList_SetItem(PyO_argv, j++, Py_BuildValue("s", s ));
		
	}

	return PyO_argv;
}
static char argvget_doc[] =
"argvget(void)\n\
\n\
Return a tuple of all argv's.";

static PyMethodDef _proctitle_methods[] = {
	{"argvlen", argvlen, METH_VARARGS, argvlen_doc},
	{"argvset", argvset, METH_VARARGS, argvset_doc},
	{"argvget", argvget, METH_VARARGS, argvget_doc},	
	{ NULL, NULL }
};

void
init_proctitle( void )
{
	Py_InitModule( "_proctitle", _proctitle_methods );

	Py_GetArgcArgv(&argc,&argv);

	_argv_lengths();
}

