from __future__ import absolute_import

import six

import tensorflow as tf


def relu(input_):
  if input_.dtype in [tf.complex64, tf.complex128]:
    with tf.name_scope("c_relu"):
      eps = 1e-7
      real = tf.real(input_)
      # Handle small value issue
      sign = real / tf.maximum(eps, tf.abs(real))
      mask = tf.maximum(sign, 0)
      mask = tf.complex(mask, tf.zeros_like(mask, dtype=mask.dtype))
      return input_ * mask
  else:
    return tf.nn.relu(input_, name='relu')

def get(identifier, **kwargs):
  if callable(identifier):
    return identifier
  elif isinstance(identifier, six.string_types):
    identifier = identifier.lower()
    if identifier in ['relu']:
      return relu
    else:
      # Try to find activation in tf.nn
      activation = tf.nn.__dict__.get(identifier, None)
      if activation is None:
        raise ValueError('Can not resolve {}'.format(identifier))
      return activation
  else:
    raise TypeError('identifier must be callable or a string')