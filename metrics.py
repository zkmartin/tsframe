from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import six
import tensorflow as tf
import tframe as tfr


def _truncate(truth, output):
  # TODO: only supported for some metrics
  assert len(truth.shape.as_list()) > 2
  i = tf.cond(tf.get_collection(tfr.pedia.is_training)[0],
              lambda: 0, lambda: tfr.hub.val_preheat)
  return truth[:, i:], output[:, i:]


def accuracy(labels, outputs):
  # Make sure labels and outputs are tensorflow tensors
  assert isinstance(labels, tf.Tensor) and isinstance(outputs, tf.Tensor)
  # Convert labels and outputs to 2-D dense tensors
  tensors = [labels, outputs]
  for i, tensor in enumerate(tensors):
    shape = tensor.shape.as_list()
    # Handle potential RNN batches
    if len(shape) == 3: tensor = tf.reshape(tensor, (-1, shape[-1]))
    else: assert len(shape) == 2
    # Convert one-hot to dense if necessary
    if shape[-1] > 1:
      tensor = tf.argmax(tensor, 1, name='labels' if i == 0 else 'predictions')
    # Put tensor back to list
    tensors[i] = tensor

  correct_prediction = tf.equal(tensors[0], tensors[1], 'correct_prediction')
  return tf.reduce_mean(tf.cast(correct_prediction, tf.float32),
                        name='accuracy')


def generalized_accuracy(truth, output):
  """This metric is first designed for ERG data set, for whom models are
     built always have outputs with shape [1, string_len, symbol_number]"""
  # Sanity check
  assert isinstance(truth, tf.Tensor) and isinstance(output, tf.Tensor)
  truth_shape = truth.shape.as_list()
  output_shape = output.shape.as_list()

  # Assert batch size is 1
  # assert truth_shape[0] == output_shape[0] == 1
  assert len(truth_shape) == len(output_shape) == 3
  # truth = tf.reshape(truth, truth_shape[1:])
  # output = tf.reshape(output, output_shape[1:])

  # Compare distribution
  # TODO: consider tf.nn.top_k or something
  tf_sort = lambda val: tf.contrib.framework.sort(
    val, axis=1, direction='DESCENDING')
  alpha = tf.reduce_sum(tf.multiply(truth, output), axis=2)
  beta = tf.reduce_sum(tf.multiply(tf_sort(truth), tf_sort(output)), axis=2)
  return tf.reduce_mean(tf.cast(tf.equal(alpha, beta), tf.float32))


def delta(truth, output):
  assert isinstance(truth, tf.Tensor) and isinstance(output, tf.Tensor)
  if tfr.hub.val_preheat > 0:
    truth, output = _truncate(truth, output)
  return tf.norm(truth - output)


def norm_error_ratio(truth, output):
  assert isinstance(truth, tf.Tensor) and isinstance(output, tf.Tensor)
  if tfr.hub.val_preheat > 0:
    truth, output = _truncate(truth, output)
  return tf.norm(truth - output) / tf.norm(truth) * 100


def rms_error_ratio(truth, output):
  assert isinstance(truth, tf.Tensor) and isinstance(output, tf.Tensor)
  rms = lambda x: tf.sqrt(tf.reduce_mean(tf.square(x)))
  # TODO: pilot, tfr.hub.val_preheat > 0 only happens in RNN model
  #       thus output.shape is [batch_size, step_num, *target_shape]
  if tfr.hub.val_preheat > 0:
    truth, output = _truncate(truth, output)
  return rms(truth - output) / rms(truth) * 100


def rms_error_in_mv(truth, output):
  assert isinstance(truth, tf.Tensor) and isinstance(output, tf.Tensor)
  rms = lambda x: tf.sqrt(tf.reduce_mean(tf.square(x)))
  return 1000 * rms(truth - output)


def get(identifier):
  if callable(identifier):
    return identifier
  elif isinstance(identifier, six.string_types):
    identifier = identifier.lower()
    if identifier in ['accuracy', 'acc']:
      f = accuracy
    elif identifier in ['delta', 'distance']:
      f = delta
    elif identifier in ['ratio', 'norm_ratio']:
      f = norm_error_ratio
    elif identifier in ['rms_ratio']:
      f = rms_error_ratio
    elif identifier in ['rms_mv']:
      f = rms_error_in_mv
    else:
      raise ValueError('Can not resolve "{}"'.format(identifier))
    return f
  else:
    raise TypeError('identifier must be a function or a string')



