#Want C(abcspectra, metaframe)

from pandas import Series, DataFrame
import pyuvvis.core.utilities as pvutils
import pyuvvis.config as pvconfig
from pyuvvis.pandas_utils.metadframe import _MetaLocIndexer
import numpy as np

# Exceptions
# ----------

class SpecError(Exception):
   """ """
   
class SpecIndexError(SpecError):
   """ For indexing operations in particular."""   


# Primary Object
# --------------

class ABCSpectra(object):
   """ Generic methods shared by all pyuvvis spectra objects.  For example,
   printing out html orientation, and defining the "nearby" slicer.  The goal
   is to separate out methods that are intended to be customized, but might
   be buried on the already heavy Spectra object.
   """

   def __repr__(self, *args, **kwargs):
      
      header = self._header
      return ''.join(header)+'\n'+self._frame.__repr__()+'   ID: %s' % id(self)    

   def _repr_html_(self, *args, **kwargs):
      """ Ipython Notebook HTML appearance basically.  This only generates
      the colored header; under the hood, self._frame._repr_html_ calculates
      the table, including the proper size for optimal viewing and so on.
      """
      # Change output based on Spectra vs. Spectrum
      obj = self._frame
      if isinstance(obj, Series):
         obj = DataFrame(obj, columns=[self.specifier])
   
      # Call DataFrame _repr_html
      dfhtml = obj._repr_html_(*args, **kwargs)
      return ('<h4>%s</h4>' % ''.join(self._header_html)) +'<br>'+ dfhtml
   

   @property
   def _header(self):
      """ Header for string printout """
      delim = pvconfig.HEADERDELIM
      
      # Certain methods aren't copying this correctly.  Delete later if fix
      full_specunit = pvutils.hasgetattr(self, 'full_specunit', 'invalid')
      full_varunit = pvutils.hasgetattr(self, 'full_varunit', 'invalid')
      specunit = pvutils.hasgetattr(self, 'specunit', 'invalid')
      varunit = pvutils.hasgetattr(self, 'varunit', 'invalid')
   
   
      header = "*%s*%sSpectral unit:%s%sPerturbation unit:%s\n" % \
            (self.name, delim, full_specunit, delim, full_varunit)
      
      return header
      
      
   @property
   def _header_html(self):
      """ Header for html printout """
      
      delim = pvconfig.HEADERHTMLDELIM
   
      if self.ndim > 1:
         colorshape = '<font color="#0000CD">(%s X %s)</font>' % (self.shape)
      else:
         colorshape = '<font color="#0000CD"> (%s)</font>' % (self.shape)
   
      #Color iunit if referenced or not
      if not self.iunit:
         countstring = 'Iunit:&nbsp<font color="#197519">%s</font>' % self.full_iunit
      else: #orange
         countstring = 'Iunit:&nbsp<font color="#FF3300">%s</font>' % self.full_iunit
   
      ftunit = getattr(self, 'full_varunit', 'None')
      spunit = getattr(self, 'full_specunit', 'None')
   
      header = "%s&nbsp%s%s [%s X %s] %s %s\n" % \
         (self.name, 
          colorshape,
          delim,
          ftunit,
          spunit,
          delim,
          countstring)   
      
      return header
        

   
   @property  #Make log work with this eventually?
   def full_name(self):
      """ Timespectra:name or Timespectra:unnamed.  Useful for scripts mostly """
      outname = getattr(self, 'name', 'unnamed')
      return '%s:%s' % (self.__class__.__name__, self.name)

   # Indexer
   _nearby=None

   @property
   def nearby(self, *args, **kwargs):      	
      """ Slicers similiar to loc that allows for nearby value slicing.
      It also would be posslbe to define operations on this through bool
      logic like df[(x<50) & (X>50), but that requires creating a new
      indexer]"""
      if self._nearby is None:
         try:
            self._nearby=_NearbyIndexer(self)
         # New versions of _IXIndexer require "name" attribute.
         except TypeError as TE:
            self._nearby=_NearbyIndexer(self, 'nearby')
      return self._nearby    


# Nearby Indexer 
# --------------
class _NearbyIndexer(_MetaLocIndexer):
   """ Index by location, but looks for nearest values.  Warning: not all
   use cases may be handled properly; this is predominantly for range slices
   eg (df.nearby[50.0:62.4]), ie looking at a range of wavelengths.

   For more on various cases of selection by label:
   http://pandas.pydata.org/pandas-docs/stable/indexing.html#indexing-label

   Tries to handle all the cases of loc:
      A single label, e.g. 5 or 'a', (note that 5 is interpreted as a label
      of the index. This use is not an integer position along the index)

      A list or array of labels ['a', 'b', 'c']

      A slice object with labels 'a':'f' (note that contrary to usual
      python slices, both the start and the stop are included!)

      A boolean array
   """   

   def _getitem_axis(self, key, axis=0, validate_iterable=False):
      """ This is the only method that needs overwritten to preserve all
      _LocIndexer functionality.  Just need to change aspects where it
      would fail if key not found in index and replace with a key lookup.

      This is better than overwriting __getitem__ because need axis knowledge
      for slicing like [50:55, 90:95]...
      """

      labels = self.obj._get_axis(axis)
      values = labels.values #Necessary for subtraciton in find_nearest

      def _nearest(v):
         """ Find the neareast value in the Index (cast to array type);
         necessary because diff (ie subtraction) is not defined on Index
         in the way used here.
         """
         vmin, vmax = min(values), max(values)
         if v < vmin:
            raise SpecIndexError("%s is less than Index min value of %s" 
                                 % (v, vmin))
         elif v > vmax:
            raise SpecIndexError("%s is greater than Index max value of %s" 
                                 % (v, vmax))
         return values[(np.abs(values - v)).argmin()]

      if isinstance(key, slice):
         start, stop, step = key.start, key.stop, key.step
         if key.start:
            start = _nearest(key.start)
         if key.stop:
            stop = _nearest(key.stop)
         key = slice(start, stop, key.step)
         self._has_valid_type(key, axis)
         out = self._get_slice_axis(key, axis=axis)

      elif _is_bool_indexer(key):
         raise NotImplementedError('Bool indexing not supported by _Nearby Indexer')
#            return self._getbool_axis(key, axis=axis)

      elif _is_list_like(key):

         # GH 7349
         # possibly convert a list-like into a nested tuple
         # but don't convert a list-like of tuples
         # I Just chose to not support this case work
         if isinstance(labels, MultiIndex):
            raise SpecIndexError("MultiIndex nearby slicing not supported.")

         # an iterable multi-selection (eg nearby[[50, 55, 65]])
         if not (isinstance(key, tuple) and
                 isinstance(labels, MultiIndex)):

            if hasattr(key, 'ndim') and key.ndim > 1:
               raise ValueError('Cannot index with multidimensional key')

            if validate_iterable:
               self._has_valid_type(key, axis)

            # WILL OUTPUT WRONG INDEX STUFF LIKE TIMEINDEX
            # NEED TO FIX
            raise NotImplementedError("See GH #107")
            out = self._getitem_iterable(key, axis=axis)

         # nested tuple slicing
         if _is_nested_tuple(key, labels):
            locs = labels.get_locs(key)
            indexer = [ slice(None) ] * self.ndim
            indexer[axis] = locs
            out = self.obj.iloc[tuple(indexer)]

      # fall thru to straight lookup
      else:
         key = _nearest(key)  
         self._has_valid_type(key, axis)
         out = self._get_label(key, axis=axis)      

      if isinstance(out, DataFrame): #If Series or Series subclass
         out = self.obj._transfer(out) 

      # Hack becase Series aren't generated with these and 
      # self._getitem_lowerdim() will call this recursively
      elif issubclass(out.__class__, Series):
         out.nearby = self.obj.nearby
      return out
   