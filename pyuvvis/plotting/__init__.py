from pyuvvis.plotting.plot_utils import splot

# Advanced plots has to create plotparser because its plot methods depend on it
# Surely just bad design
from pyuvvis.plotting.advanced_plots import _gen2d3d, spec3d, PLOTPARSER, \
         add_projection

from pyuvvis.plotting.basic_plots import range_timeplot, areaplot, _genplot    

from pyuvvis.plotting.multiplots import quad_plot, six_plot

