from __future__ import absolute_import

import six

import tensorflow as tf


def cross_entropy(labels, logits):
  # Convert labels and logits to 2-D tensors
  tensors = [labels, logits]
  for i, tensor in enumerate(tensors):
    shape = tensor.shape.as_list()
    # Handle potential RNN batches
    if len(shape) == 3: tensor = tf.reshape(tensor, (-1, shape[-1]))
    else: assert len(shape) == 2
    # Put tensor back to list
    tensors[i] = tensor
  # Calculate average cross-entropy
  with tf.name_scope('cross_entropy'): return tf.reduce_mean(
      tf.nn.softmax_cross_entropy_with_logits_v2(
        labels=tensors[0], logits=tensors[1]))


def mean_squared_error(y_true, y_predict):
  return tf.reduce_mean(tf.square(tf.abs(y_true - y_predict)))


def euclidean(y_true, y_predict):
  distances = tf.norm(y_true - y_predict)
  return tf.reduce_mean(distances)


def get(identifier):
  if callable(identifier):
    return identifier
  elif isinstance(identifier, six.string_types):
    identifier = identifier.lower()
    if identifier in ['mean_squared', 'mean_squared_error', 'mse']:
      return mean_squared_error
    elif identifier in ['cross_entropy']:
      return cross_entropy
    elif identifier in ['euclid', 'euclidean']:
      return euclidean
    else:
      raise ValueError('Can not resolve "{}"'.format(identifier))
  else:
    raise TypeError('identifier must be a function or a string')

