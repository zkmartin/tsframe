from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import numpy as np
import six
import tensorflow as tf

from .layer import Layer
from .layer import single_input

from ..utils import get_scale

from .. import activations
from .. import initializers
from .. import regularizers
from .. import pedia


class Activation(Layer):
  """"""
  def __init__(self, identifier, **kwargs):
    self.abbreviation = (identifier if isinstance(identifier, six.string_types)
                         else identifier.__name__)
    self._activation = activations.get(identifier, **kwargs)

  @single_input
  def _link(self, inputs, **kwargs):
    """Group name of Activation layer is decided not in calling
       Function.__call__ but calling self._activation"""
    outputs = self._activation(inputs)
    with tf.name_scope(pedia.summaries):
      act_sum = tf.summary.histogram('activations', tf.abs(outputs))
      pedia.memo[pedia.activation_sum] += [act_sum]
    return outputs

  @staticmethod
  def ReLU():
    return Activation('relu')

  @staticmethod
  def LeakyReLU():
    return Activation('lrelu')


class Dropout(Layer):
  """"""
  abbreviation = 'dropout'

  def __init__(self, train_keep_prob=0.5):
    # Initialize keep probability until while linking to put the
    #   the placeholder in the right name scope
    self._keep_prob = None
    self.train_keep_prob = train_keep_prob

  @single_input
  def _link(self, input_, **kwargs):
    if self._keep_prob is None:
      self._keep_prob = tf.placeholder(tf.float32, name=pedia.keep_prob)
      tf.add_to_collection(pedia.status_tensors, self._keep_prob)
      pedia.memo[self._keep_prob.name] = self.train_keep_prob

    return tf.nn.dropout(input_, self._keep_prob)


class Linear(Layer):
  """Linear transformation layer, also known as fully connected layer or
     dense layer"""
  is_nucleus = True

  full_name = 'linear'
  abbreviation = 'fc'

  def __init__(self, output_dim,
               force_real=False,
               use_bias=True,
               weight_initializer='xavier_uniform',
               bias_initializer='zeros',
               weight_regularizer=None,
               bias_regularizer=None):
    Layer.__init__(self)

    if not np.isscalar(output_dim):
      raise TypeError('output_dim must be a scalar, not {}'.format(
        type(output_dim)))
    self._output_dim = output_dim
    self._force_real = force_real
    self._use_bias = use_bias

    self._weight_initializer = initializers.get(weight_initializer)
    self._bias_initializer = initializers.get(bias_initializer)
    self._weight_regularizer = regularizers.get(weight_regularizer)
    self._bias_regularizer = regularizers.get(bias_regularizer)

    self.weights = None
    self.biases = None

    self.neuron_scale = [output_dim]

  @single_input
  def _link(self, input_, **kwargs):
    assert isinstance(input_, tf.Tensor)

    # If this layer has been linked once, variables should be reused
    if self.weights is not None:
      tf.get_variable_scope().reuse_variables()

    # Get the shape and data type of input
    input_shape = input_.get_shape().as_list()
    dtype = input_.dtype

    weight_shape = (input_shape[-1], self._output_dim)
    bias_shape = (self._output_dim, )

    # Use lambda to make getting variable easier
    get_weight_variable = lambda name, fixed_zero=False: self._get_variable(
      name, weight_shape, fixed_zero, self._weight_initializer,
      self._weight_regularizer)
    get_bias_variable = lambda name, fixed_zero=False: self._get_variable(
      name, bias_shape, fixed_zero, self._bias_initializer,
      self._bias_regularizer)

    # Get variable
    if dtype in [tf.complex64, tf.complex128]:
      # Get complex weights and biases
      self.weights = tf.complex(
        get_weight_variable('weights_real'),
        get_weight_variable('weights_imag', self._force_real),
        name='weights')
      if self._use_bias:
        self.biases = tf.complex(
          get_bias_variable('biases_real'),
          get_bias_variable('biases_imag', self._force_real),
          name='biases')
    else:
      # Get real weights and biases
      self.weights = get_weight_variable('weights')
      if self._use_bias:
        self.biases = get_bias_variable('biases')

    # Calculate output
    output = tf.matmul(input_, self.weights)
    if self._use_bias:
      output += self.biases

    return output


class Reshape(Layer):

  def __init__(self, shape=None):
    """
    Reshape layer. 
    :param shape: list or tuple. Shape of each example, not including 1st
                   dimension
    """
    self.output_shape = shape

  @single_input
  def _link(self, input_, **kwargs):
    name = 'flatten' if self.output_shape is None else 'reshape'
    self.abbreviation = name

    input_shape = input_.get_shape().as_list()
    output_shape = ([-1, np.prod(input_shape[1:])]
                    if self.output_shape is None
                    else [-1] + self.output_shape)

    output = tf.reshape(input_, output_shape, name=name)
    self.neuron_scale = get_scale(output)
    return output


def Input(shape=None, dtype=tf.float32, name='Input'):
  return tf.placeholder(dtype=dtype, shape=shape, name=name)


Flatten = lambda: Reshape()
