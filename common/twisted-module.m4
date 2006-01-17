dnl twisted-module.m4
dnl m4 macro to check for twisted modules

dnl By Andy Wingo

# TWISTED_MODULE([module-name])

# Checks for a module of the given name. If it's not there, given the
# user a nice message asking them to bake cookies for the hackers, and
# possibly install the correct package.

AC_DEFUN([TWISTED_MODULE],
 [
AS_PYTHON_IMPORT([$1],
  []
  ,
  AC_MSG_ERROR([$1 not found.

Your distribution appears to have separated $1 from the rest
of twisted. Please install the package providing $1 and try
again.])
)
])  
