/*
 * Flumotion - a streaming media server
 * Copyright (C) 2004,2005,2006,2007,2008,2009 Fluendo, S.L.
 * Copyright (C) 2010,2011 Flumotion Services, S.A.
 * All rights reserved.
 *
 * This file may be distributed and/or modified under the terms of
 * the GNU Lesser General Public License version 2.1 as published by
 * the Free Software Foundation.
 * This file is distributed without any warranty; without even the implied
 * warranty of merchantability or fitness for a particular purpose.
 * See "LICENSE.LGPL" in the source distribution for more information.
 *
 * Headers in this file shall remain intact.
 */

/* fdpass.c:
 *
 * Simple python extension module to wrap sendmsg()/recvmsg() for sending
 * and receiving file descriptors over sockets.
 *
 * Several such extensions exist; they all seem to wrap the wrong subset of
 * these syscalls, or have incompatible licenses.
 *
 * Receive a socket message on fd 'socket', containing one or more fds and a
 * message buffer. Limited to receiving MAX_RECEIVED_FDS fds. Reads a message
 * of up to 'size' bytes.
 * ([fd], buffer) = fdpass.readfds(socket, size)
 *
 * Write a socket message on fd 'socket', containing one or more fds and a
 * message buffer.
 * fdpass.writefds(socket, [fd], buffer)
 */

#include <Python.h>

#include <sys/types.h>
#include <sys/socket.h>

#define MAX_RECEIVED_FDS 32

static PyObject *
readfds(PyObject *self, PyObject *args)
{
  int sockfd, fd, size;
  PyObject *fdobj, *list = NULL, *ret = NULL;
  struct msghdr msg;
  struct iovec iov[1];
  struct cmsghdr *msgptr;
  int n;

  if (!PyArg_ParseTuple (args, "ii", &sockfd, &size))
    return NULL;

  /* Stevens: Unix Network Programming, 3rd Ed. p 426. */
  msg.msg_controllen = CMSG_SPACE (sizeof (int) * MAX_RECEIVED_FDS);
  msg.msg_control = malloc (msg.msg_controllen);
  if (msg.msg_control == NULL) {
    return PyErr_NoMemory();
  }

  msg.msg_name = NULL;
  msg.msg_namelen = 0;

  iov[0].iov_len = size;
  iov[0].iov_base = malloc (iov[0].iov_len);
  if (iov[0].iov_base == NULL) {
    free (msg.msg_control);
    return PyErr_NoMemory();
  }

  msg.msg_iov = iov;
  msg.msg_iovlen = 1;

  Py_BEGIN_ALLOW_THREADS
  n = recvmsg (sockfd, &msg, 0);
  Py_END_ALLOW_THREADS

  if (n < 0) {
    ret = PyErr_SetFromErrno(PyExc_OSError);
    goto done;
  }

  list = PyList_New (0);

  msgptr = CMSG_FIRSTHDR (&msg);
  while (msgptr != NULL) {
    if (msgptr->cmsg_len != CMSG_LEN (sizeof (int)) ||
        msgptr->cmsg_level != SOL_SOCKET ||
        msgptr->cmsg_type != SCM_RIGHTS)
    {
      /* Unexpected control message. Bail out */
      PyErr_SetString(PyExc_TypeError, "Unexpected control message");
      goto done;
    }

    fd = *((int *) CMSG_DATA (msgptr));

    fdobj = PyInt_FromLong ((long)fd);
    PyList_Append (list, fdobj);
    Py_DECREF (fdobj);

    msgptr = CMSG_NXTHDR (&msg, msgptr);
  }

  ret = Py_BuildValue ("(Os#)", list, iov[0].iov_base, n);

done:
  if (list) {
    Py_DECREF (list);
  }

  free (msg.msg_control);
  free (iov[0].iov_base);

  return ret;
}

static PyObject *
writefds(PyObject *self, PyObject *args)
{
  int sockfd;
  char *message;
  int msglen;
  PyObject *list;
  int numfds;
  int ret;

  if (!PyArg_ParseTuple (args, "iOs#", &sockfd, &list, &message, &msglen))
    return NULL;

  if (!PyList_Check (list))
    return NULL;

  numfds = PyList_Size (list);

  /* Stevens: Unix Network Programming, 3rd Ed. p 428.
   *
   * The UNIX socket APIs are really messy. Anyway, here goes... Note that this
   * doesn't implement a version for Unixes with no msg.msg_control (see Stevens
   * if we need to implement that later, it's pretty easy)
   */
  {
    struct msghdr msg;
    struct iovec iov[1];
    struct cmsghdr *msgptr;
    PyObject *fdobj;
    int fd, i;

    msg.msg_controllen = CMSG_SPACE (sizeof (int) * numfds);
    msg.msg_control = malloc (msg.msg_controllen);
    if (msg.msg_control == NULL) {
      return PyErr_NoMemory();
    }

    msgptr = CMSG_FIRSTHDR (&msg);
    for (i = 0; i < numfds; i++)
    {
      msgptr->cmsg_len = CMSG_LEN (sizeof(int));
      msgptr->cmsg_level = SOL_SOCKET;
      /* The control message type for FD-passing is called SCM_RIGHTS for some
       * reason */
      msgptr->cmsg_type = SCM_RIGHTS;

      /* And the actual data: a single int, our passed fd. Convert from python
       * first, checking that it's valid.
       */
      fdobj = PyList_GetItem (list, i);
      if (!PyInt_Check (fdobj))
      {
        PyErr_SetString(PyExc_TypeError, "List value is not an integer");
        free (msg.msg_control);
        return NULL;
      }
      fd = (int) PyInt_AsLong (fdobj);

      *((int *) CMSG_DATA (msgptr)) = fd;

      msgptr = CMSG_NXTHDR (&msg, msgptr);
    }

    /* These are used for sending control messages on unconnected sockets; we
     * don't need them here */
    msg.msg_name = NULL;
    msg.msg_namelen = 0;

    /* Our I/O vector (this API allows for scatter-gather type messages)
     * contains just a single entry - the message to pass along with our
     * control data (which is the fds themselves
     */
    iov[0].iov_base = message;
    iov[0].iov_len = msglen;
    msg.msg_iov = iov;
    msg.msg_iovlen = 1;

    Py_BEGIN_ALLOW_THREADS
    ret = sendmsg (sockfd, &msg, 0);
    Py_END_ALLOW_THREADS

    free (msg.msg_control);
  }

  if (ret < 0) {
    /* Failure. Throw an appropriate Python exception */
    return PyErr_SetFromErrno(PyExc_OSError);
  }

  return Py_BuildValue("i", ret);
}

static PyMethodDef methods[] =
{
    {"readfds", readfds, METH_VARARGS,
        "Read a message over a socket, along with one or more FDs"},
    {"writefds", writefds, METH_VARARGS,
        "Write a message over a socket, along with one or more FDs"},
    {NULL, NULL, 0, NULL},
};

PyMODINIT_FUNC
initfdpass(void)
{
  Py_InitModule ("fdpass", methods);
}

