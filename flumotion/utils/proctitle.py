#
# proctitle.py 
# Proctitle allows you to manipulate the raw argv[] of the python process.
# 
# Copyright 2002 - 'Diesel' Dave 'Kill a Cop' Cinege <dcinege@psychosis.com>
# GPL2 - Copyright notice may not be altered. 
#

import _proctitle
from types import *

class ProcTitle:
	"""
	Proctitle allows you to manipulate the raw argv[] of the python process.
	"""
	def __init__(self):
		self.argvcopy			= None
		self.argvlen,self.argvpos	= _proctitle.argvlen()
		self.argvlentotal		= reduce(lambda x, y: x+y, self.argvlen)
		self.argc			= len(self.argvlen)
	def __str__(self):
		return str(self.get())
	def __len__(self):
		return self.argc
	def __getitem__(self,slice):
		if type(slice) is IntType:		# Single element
			start = slice
		else:						
			start = slice.start
			amt = min(slice.stop,self.argc)
				
		if start >= self.argc:
			raise IndexError, 'list index out of range'

		if type(slice) == IntType:		# Single element
			return self.get(start,1)[0]
		else:
			return self.get(start,amt)		

	def __setitem__(self,slice,value):
		if type(slice) == IntType:		# Single element
			value = [value]
			start = stop = slice
		else:						
			start = slice.start
			stop = min(slice.stop,self.argc)
		
		if start >= self.argc:
			raise IndexError, 'list index out of range'

		if type(value) is ListType:
			for i in value:
				if type(i) is not StringType:
					raise ValueError, 'list item not string'
		elif type(value) is StringType:
			l = []; s = e = 0
			for i in range(start,stop):	# Slice up string to fit cleanly in available space.
				e = self.argvlen[i] + s
				l += [value[s:e]]	
				s += self.argvlen[i]
			value = l
			del(l)	
		else:
			raise ValueError, 'must assign list or string to slice'
			
		llen = stop - start - len(value)
		if llen > 0:				# List is shorter then range. Pad list.
			value += ['']  * llen

		return self.set(value,start)

	def set(self,l,start = 0):
		return _proctitle.argvset(l,start)
	def get(self,start = 0, amt = None):
		if amt is None:
			amt = self.argc
		return _proctitle.argvget(start,amt)
	def save(self):
		self.argvcopy = self.get()
	def restore(self):
		if self.argvcopy is None:
			raise ValueError, 'you must first save before you can restore.'
		return self.set(self.argvcopy)
