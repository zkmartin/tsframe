from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import tensorflow as tf

from tframe.core.function import Function
from tframe.core.decorators import init_with_graph
from tframe.layers.layer import Layer
from tframe.layers.layer import single_input

from tframe.utils import get_scale

from tensorflow.python.layers.convolutional import Conv1D as _Conv1D
from tensorflow.python.layers.convolutional import Conv2D as _Conv2D
from tensorflow.python.layers.convolutional import Deconv2D as _Deconv2D


class _Conv(Layer):
  is_nucleus = True
  abbreviation = 'conv'

  @init_with_graph
  def __init__(self, *args, **kwargs):
    super(Function, self).__init__(*args, **kwargs)

  @single_input
  def __call__(self, input_=None, **kwargs):
    assert isinstance(input_, tf.Tensor)
    # TODO: too violent ?
    output = super(Function, self).__call__(input_, scope=self.full_name)
    self.neuron_scale = get_scale(output)
    return output


# The tensorflow class is next to Function in the __mro__ list of the
#  classes below

class Conv1D(_Conv, _Conv1D):
  full_name = 'convolutional1d'


class Conv2D(_Conv, _Conv2D):
  full_name = 'convolutional2d'


class Deconv2D(_Conv, _Deconv2D):
  full_name = 'deconvolutional2d'
  abbreviation = 'deconv'

