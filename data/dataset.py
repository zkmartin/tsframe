from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import numpy as np
import pickle

from tframe import checker
from tframe import pedia
from tframe import hub

from tframe.data.base_classes import TFRData
from tframe.data.paral_engine import ParallelEngine


class DataSet(TFRData):
  """"""
  EXTENSION = 'tfd'

  def __init__(self, features=None, targets=None, data_dict=None,
               name='dataset1', in_rnn_format=False, **kwargs):
    """
    A DataSet usually holds a regular numpy array or a list of irregular
    numpy arrays as features (or targets). Raw data or other adjoint data
    can be stored into data_dict for features and targets generation or
    other further processing.
     Properties of a DataSet will be maintained during list merging or data set
     splitting.

    :param features: Features. Can be a regular numpy array or a list of
                      numpy arrays. If not provided, data_dict must not be
                      empty
    :param targets: Targets. If provided, it must be of the same type and size
                      with features.
    :param data_dict: A dictionary which holds raw data or other adjoint data.
                       If is empty, features must be provided
    :param name: The name of this DataSet
    :param kwargs: A dictionary which stores the properties of this DataSet
    """
    # Attributes
    self.features = features
    self.targets = targets
    self.data_dict = {} if data_dict is None else data_dict
    self.properties = kwargs
    self.name = name

    self._stacked_data = None
    self._rnn_data = None

    self.in_rnn_format = in_rnn_format
    self.should_reset_state = False
    self.reset_batch_indices = None
    self.reset_values = None

    # Sanity checks
    self._check_data()

  # region : Properties

  @property
  def should_partially_reset_state(self):
    return self.reset_batch_indices is not None

  @property
  def structure(self):
    assert self.features is not None
    if isinstance(self.features, np.ndarray): features = [self.features]
    else: features = self.features
    result = []
    for x in features:
      assert isinstance(x, np.ndarray)
      result.append(len(x))
    return result

  @property
  def size(self):
    if self.features is None:
      assert len(self.data_dict) > 0
      data_array = list(self.data_dict.values())[0]
      return len(data_array)
    else: return len(self.features)

  @property
  def is_regular_array(self):
    self._check_feature()
    return isinstance(self.features, np.ndarray)

  @property
  def stack(self):
    """Return a numpy array containing all data in this data set"""
    self._check_feature()
    if self.is_regular_array: return self
    if self._stacked_data is not None: return self._stacked_data
    # Stack data
    try:
      x = np.concatenate(self.features, axis=0)
      y = None if self.targets is None else np.concatenate(self.targets, axis=0)
      self._stacked_data = DataSet(x, y, name='{}(stacked)'.format(self.name))
      self._stacked_data.data_dict = self.data_dict
      self._stacked_data.properties = self.properties
      return self._finalize(self._stacked_data)
    except:
      print('!! failed to stack data')
      raise

  @property
  def as_rnn_data(self):
    assert self.is_regular_array
    if self.in_rnn_format: return self
    if self._rnn_data is not None: return self._rnn_data
    x, y = np.reshape(self.features, [1] + list(self.features.shape)), None
    if self.targets is not None:
      y = np.reshape(self.targets, [1] + list(self.targets.shape))
    self._rnn_data = DataSet(features=x, targets=y, in_rnn_format=True)
    return self._rnn_data

  # endregion : Properties

  # region : Overriden Methods

  def __len__(self):
    return self.size

  def __getitem__(self, item):
    if isinstance(item, str):
      if item == pedia.features: return self.features
      elif item == pedia.targets: return self.targets
      elif item in self.data_dict.keys(): return self.data_dict[item]
      elif item in self.properties.keys(): return self.properties[item]
      else: raise KeyError('!! Can not resolve "{}"'.format(item))
    # If item is index array
    features, targets, data_dict = None, None, {}
    # item = np.mod(item, self.size)
    if self.features is not None: features = self.features[item]
    if self.targets is not None: targets = self.targets[item]
    for key, val in self.data_dict.items():
      assert hasattr(val, '__len__')
      # other data array in self.data_dict will be abandoned
      if len(val) == self.size: data_dict[key] = val[item]
    # Return
    return self._finalize(DataSet(
      features, targets, data_dict, self.name, **self.properties))

  # endregion : Overriden Methods

  # region : Basic APIs

  def get_round_length(self, batch_size, num_steps=None):
    """Get round length for training
    :param batch_size: Batch size. For irregular sequences, this value should
                        be set to 1.
    :param num_steps: Step number. If provided, round length will be calculated
                       for RNN model
    :return: Round length for training
    """
    # Make sure features exist
    self._check_feature()
    checker.check_positive_integer(batch_size, 'batch_size')
    if num_steps is None:
      # :: For feed-forward models
      return int(np.ceil(self.stack.size / batch_size))
    else:
      # :: For recurrent models
      checker.check_type(num_steps, int)
      if self.is_regular_array: arrays = [self.features]
      elif self.parallel_on:
        return self._get_pe_round_length(batch_size, num_steps)
      else: arrays = self.features

      len_f = lambda x: x if self.len_f is None else self.len_f
      if num_steps < 0: return len(arrays)
      else: return int(sum([np.ceil(len_f(len(array)) // batch_size / num_steps)
                            for array in arrays]))

  def gen_batches(self, batch_size, shuffle=False):
    """ Generate batches of data
    (1) When data is a regular numpy array:
        Data batches will be extracted along its first dimension in order or
        randomly
    (2) When data is list of sequences:
        Data will be stacked first and extracted as it does in (1)

    :param batch_size: Batch size
    :param shuffle: Whether to shuffle
    :return: A generator producing batches of data
    """
    round_len = self.get_round_length(batch_size)
    for i in range(round_len):
      yield self.stack[
        self._rand_indices(size=batch_size) if shuffle
        else range(i * batch_size, min((i + 1) * batch_size, self.stack.size))]

  def gen_rnn_batches(self, batch_size=1, num_steps=-1, shuffle=False):
    """ Generate data batches with steps
    (1) When data is a regular numpy array:
        The whole data will be regarded as a single sequence and will be
        chopped in order into batches and then chopped in order into step blocks
        with the specified size
    (2) When data is a list of sequences:
        rnn batches will be generated sequence by sequence

    The default parameters are for batch validation

    :param batch_size: Batch size
    :param num_steps: Step number
    :param shuffle: Whether to shuffle
    :return: A generator producing rnn batches of data
    """
    # Sanity check using get_round_length method
    round_len = self.get_round_length(batch_size, num_steps)
    # Put features and targets into lists
    if self.is_regular_array: features = [self.features]
    elif self.parallel_on:
      for batch in self._gen_parallel_batches(batch_size, num_steps, shuffle):
        assert isinstance(batch, DataSet)
        yield batch
      return
    else: features = self.features

    targets = (None,) * self.size if self.targets is None else (
      [self.targets] if self.is_regular_array else self.targets)
    num_sequences = len(features)
    # Generate data sequence by sequence
    for i in range(num_sequences):
      index = self._rand_indices(num_sequences) if shuffle else i
      x, y = features[index], targets[index]
      if self.init_f is not None: x, y = self.init_f(x, y)

      for batch in self._gen_rnn_batches(x, y, batch_size, num_steps):
        assert isinstance(batch, DataSet)
        yield batch
        round_len -= 1
        # TODO: Make sure progress bar works properly
        # if round_len == 0: return

  # endregion : Basic APIs

  # region : Public Methods

  def split(self, *sizes, names=None):
    # Sanity check
    if len(sizes) == 0: raise ValueError('!! split sizes not specified')
    elif len(sizes) == 1 and isinstance(sizes[0], (list, tuple)):
      sizes = sizes[0]
    if names is not None:
      if not isinstance(names, (tuple, list)):
        raise TypeError('!! names must be a tuple or list of strings')
      if len(names) != len(sizes):
        raise ValueError('!! length of name list and sizes list does not match')
    # Check sizes
    sizes, auto_index, total_size = list(sizes), -1, 0
    for i, size in enumerate(sizes):
      if size is None or size < 0:
        if auto_index < 0:
          auto_index = i
          continue
        else: raise ValueError(
          '!! only one split size can be calculated automatically')
      if not isinstance(size, int) and size < 0:
        raise ValueError('!! size must be a non-negative integer')
      total_size += size
    # Calculate size automatically if necessary
    if auto_index >= 0:
      sizes[auto_index] = self.size - total_size
      if sizes[auto_index] <= 0: raise ValueError(
        '!! negative value appears when calculating size automatically')
    elif total_size != self.size: raise ValueError(
      '!! total size does not match size of the data set to split')
    # Split data set
    data_sets, cursor = (), 0
    for i, size in enumerate(sizes):
      if size == 0: continue
      indices = slice(cursor, cursor + size)
      data_set = self[indices]
      if names is not None: data_set.name = names[i]
      data_sets += (data_set,)
      cursor += size

    return data_sets

  # endregion : Public Methods

  # region : Private Methods

  def _finalize(self, data_set):
    assert isinstance(data_set, DataSet)
    data_set.__class__ = self.__class__
    return data_set

  def _check_data(self):
    """Features and data_dict should not be empty at the same time.
       All data array or list provided must have the same length.
       If features (or targets) are provided as a list (or a tuple),
       its elements must be numpy arrays with exactly the same shape (except
       for the first dimension)."""
    # Make sure data_dict is a dictionary
    if not isinstance(self.data_dict, dict):
      raise TypeError('!! data_dict provided must be a dict')
    # Put all data arrays to a single dict for later check
    data_dict = self.data_dict.copy()
    if self.features is not None:
      data_dict[pedia.features] = self.features
      if self.targets is not None:
        # TODO
        # if type(self.features) != type(self.targets):
        #   raise TypeError('!! features and targets must be of the same type')
        data_dict[pedia.targets] = self.targets

    # Make sure at least one data array is provided
    if len(data_dict) == 0:
      raise AssertionError('!! data not found')
    # Make sure all data array have the same size
    size = -1
    for key, val in data_dict.items():
      # Make sure all data arrays are instances of list or ndarray or sth.
      if not hasattr(val, '__len__'):
        raise AttributeError(
          '!! {} data must have __len__ attribute'.format(key))
      if size == -1: size = len(val)
      elif size != len(val):
        raise ValueError('!! all data array must have the same size')

      # Make sure features and targets are (lists of) numpy arrays
      if key in (pedia.features, pedia.targets):
        checker.check_type(val, np.ndarray)
        # If features and targets are stored in a list (or a tuple), check
        # .. the shape of each numpy array
        if not isinstance(val, np.ndarray):
          assert isinstance(val, (list, tuple))
          shape = None
          for array in val:
            assert isinstance(array, np.ndarray)
            if shape is None: shape = array.shape[1:]
            elif shape != array.shape[1:]:
              raise ValueError(
                '!! samples in {} list should have the same shape'.format(key))

  def _check_feature(self):
    if self.features is None: raise AssertionError(
      '!! no features found in {}'.format(self.name))

  def _gen_rnn_batches(self, x, y, batch_size, num_steps):
    checker.check_positive_integer(batch_size, 'batch size')
    checker.check_type(num_steps, int)
    # Get batch partitions
    data_x, L = self._get_batch_partition(x, batch_size)
    if y is not None:
      if len(x) == len(y):
        data_y, Ly = self._get_batch_partition(y, batch_size)
        assert L == Ly
      else:
        assert len(y) == 1
        data_y = y
    # Chop data further
    if num_steps < 0: num_steps = L
    round_len = int(np.ceil(L / num_steps))
    for i in range(round_len):
      batch_x = data_x[:, i * num_steps:min((i + 1) * num_steps, L)]
      batch_y = None
      if y is not None:
        if len(x) == len(y):
          batch_y = data_y[:, i * num_steps:min((i + 1) * num_steps, L)]
        else:
          assert isinstance(y, np.ndarray)
          batch_y = np.tile(y, [batch_x.shape[0], batch_x.shape[1], 1])
      batch = DataSet(batch_x, batch_y, in_rnn_format=True)
      # State should be reset at the beginning of a sequence
      if i == 0: batch.should_reset_state = True
      batch.name = self.name + '_{}'.format(i + 1)
      yield batch

  def _get_batch_partition(self, array, batch_size):
    assert isinstance(array, np.ndarray)
    sample_shape = array[0].shape
    # Get batch partition length
    L = len(array) // batch_size
    data = np.zeros([batch_size, L, *sample_shape])
    for i in range(batch_size):
      data[i] = array[i * L:(i + 1) * L, :]
    # Return result
    return data, L

  def _gen_parallel_batches(self, batch_size, num_steps, shuffle):
    """A beta method used only for RNN training"""
    # Sanity check
    features, targets = self.features, self.targets
    assert isinstance(features, (tuple, list))
    assert isinstance(targets, (tuple, list))
    assert len(features) == len(targets)
    checker.check_positive_integer(batch_size)
    assert isinstance(num_steps, int)
    assert isinstance(shuffle, bool)

    # Initialize parallel engine
    pe = ParallelEngine(batch_size)
    cursor, num_sequences = 0, len(self.features)
    round_len = self._get_pe_round_length(batch_size, num_steps)

    # Start loop
    global_reset = True
    counter = 0
    while True:
      reset_indices = pe.inactive_indices
      reset_values = []

      # Load new sequence to engine if necessary
      while not pe.is_ready:
        if shuffle or cursor < num_sequences:
          index = self._rand_indices() if shuffle else cursor
          x, y = self.features[index], self.targets[index]
          if self.init_f is not None: x, y = self.init_f(x, y)
          cursor += 1
          reset_values.append(0)
        else:
          x, y = None, None
          reset_values.append(None)
        pe.set_sequence(x, y)

      if pe.flameout: break

      # Get features and targets and wrap them into a DataSet
      x, y = pe.emit(num_steps)
      data_batch = DataSet(x, y)
      if len(reset_indices) > 0:
        if global_reset:
          data_batch.should_reset_state = True
          global_reset = False
        assert len(reset_indices) == len(reset_values)
        data_batch.reset_batch_indices = reset_indices
        data_batch.reset_values = (
          reset_values if len([val for val in reset_values if val is None]) > 0
          else None)

      # Yield batch
      yield  data_batch

      counter += 1
      if counter >= round_len: break

    # Check round length
    assert counter == round_len

  def _get_pe_round_length(self, batch_size, num_steps):
    if self.init_f is not None and self.len_f is None: return None
    if self.init_f is None: assert self.len_f is None
    return ParallelEngine.get_round_length(
      batch_size, num_steps, self.structure, len_f=self.len_f)

  def _rand_indices(self, upper_bound=None, size=1):
    if upper_bound is None: upper_bound = self.size
    assert self.features is not None
    if not hub.rand_over_classes:
      indices = np.random.randint(upper_bound, size=size)
    else:
      classes = np.random.randint(self.num_classes, size=size)
      indices = []
      for cls in classes:
        group_index = np.random.randint(len(self.groups[cls]))
        indices.append(self.groups[cls][group_index])

    if len(indices) == 1: return indices[0]
    else: return indices

  # endregion : Private Methods


if __name__ == '__main__':
  features = np.arange(12)
  data_set = DataSet(features)
