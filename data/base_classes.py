from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import os
import re
import numpy as np
import pickle

from tframe import console
from tframe import pedia
import tframe.utils.misc as misc


class TFRData(object):
  """Abstract class defining apis for data set classes used in tframe"""
  EXTENSION = 'nonsense'

  GROUPS = 'GROUPS'
  NUM_CLASSES = 'NUM_CLASSES'

  PARALLEL_ON = 'PARALLEL_ON'
  INIT_F = 'INIT_F'
  LEN_F = 'LEN_F'

  name = None
  properties = None

  # region : Properties

  # region : Parallel engine

  @property
  def parallel_on(self):
    assert isinstance(self.properties, dict)
    return self.properties.get(self.PARALLEL_ON, False)

  @property
  def init_f(self):
    """x, y = init_f(x, y) where x, y is numpy arrays"""
    assert isinstance(self.properties, dict)
    f = self.properties.get(self.INIT_F, None)
    if f is not None: assert callable(f)
    return f

  @init_f.setter
  def init_f(self, val):
    assert callable(val)
    self.properties[self.INIT_F] = val

  @property
  def len_f(self):
    """l = len_f(l) where l is an positive integer"""
    assert isinstance(self.properties, dict)
    f = self.properties.get(self.LEN_F, None)
    if f is not None: assert callable(f)
    return f

  @len_f.setter
  def len_f(self, val):
    assert callable(val)
    self.properties[self.LEN_F] = val

  # endregion : Parallel engine

  @property
  def groups(self):
    val = self.properties[self.GROUPS]
    assert isinstance(val, list) and len(val) == self.num_classes
    return val

  @property
  def num_classes(self):
    assert isinstance(self.properties, dict)
    return self.properties.get(self.NUM_CLASSES, None)

  @property
  def structure(self):
    raise NotImplementedError

  @property
  def size(self):
    raise NotImplementedError

  @property
  def is_regular_array(self):
    raise NotImplementedError

  # endregion : Properties

  def get_round_length(self, batch_size, num_steps=None):
    raise NotImplementedError

  def gen_batches(self, batch_size, shuffle=False):
    raise NotImplementedError

  def gen_rnn_batches(self, batch_size=1, num_steps=-1, shuffle=False):
    raise NotImplementedError

  def turn_parallel_on(self, **kwargs):
    assert isinstance(self.properties, dict)
    self.properties[self.PARALLEL_ON] = True

  # region : Load and Save

  def save(self, filename):
    if filename.split('.')[-1] != self.EXTENSION:
      filename += '.{}'.format(self.EXTENSION)
    with open(filename, 'wb') as output:
      pickle.dump(self, output, pickle.HIGHEST_PROTOCOL)

  @classmethod
  def load(cls, filename):
    assert isinstance(filename, str)
    # If file is on the cloud, download to local first
    if filename.startswith('gs://'):
      import subprocess
      tmp_path = './data/tmp.tfd'
      subprocess.check_call(
        ['gsutil', '-m', '-q', 'cp', '-r', filename, tmp_path])
      filename = tmp_path

    extension = filename.split('.')[-1]
    if extension != cls.EXTENSION:
      raise TypeError('!! {} can not load .{} file'.format(
        cls.__name__, extension))
    with open(filename, 'rb') as input_:
      return pickle.load(input_)

  # endregion : Load and Save

class DataAgent(object):
  """A abstract class defines basic APIs for an data agent"""
  DATA_NAME = None
  DATA_URL = None
  TFD_FILE_NAME = None

  PROPERTIES = {}

  # region : Properties

  @classmethod
  def default_file_name(cls):
    assert isinstance(cls.DATA_URL, str)
    return cls.DATA_URL.split('/')[-1]

  # endregion : Properties

  # region : Public Methods

  @classmethod
  def load_as_numpy_arrays(cls, data_dir):
    """Load (features, targets) as numpy arrays"""
    raise NotImplementedError

  @classmethod
  def load_as_tframe_data(cls, data_dir):
    """Load data as TFrame DataSet"""
    raise NotImplementedError

  @classmethod
  def load(cls, data_dir, train_size, validate_size, test_size, **kwargs):
    """Load data"""
    data_set = cls.load_as_tframe_data(data_dir)
    return cls._split_and_return(data_set, train_size, validate_size, test_size)

  @classmethod
  def _split_and_return(cls, data_set, train_size, validate_size, test_size):
    from tframe.data.dataset import DataSet
    assert isinstance(data_set, DataSet)
    data_sets = data_set.split(
      train_size, validate_size, test_size,
      names=('Train set', 'Validation set', 'Test set'))
    # Show data info
    cls._show_data_sets_info(data_sets)
    return data_sets

  # endregion : Public Methods

  # region : Private Methods

  @classmethod
  def _check_raw_data(cls, data_dir, file_name=None, url=None):
    # Get file path
    data_dir = cls._check_path(data_dir, create_path=True)
    file_name = cls.default_file_name() if file_name is None else file_name
    file_path = os.path.join(data_dir, file_name)
    # If data does not exist, download from web
    if not os.path.exists(file_path): cls._download(file_path, url)
    # Return file path
    return file_path

  @classmethod
  def _download(cls, file_path, url=None):
    import time
    from six.moves import urllib
    # Show status
    file_name = cls._split_path(file_path)[-1]
    console.show_status('Downloading {} ...'.format(file_name))
    start_time = time.time()
    def _progress(count, block_size, total_size):
      console.clear_line()
      console.print_progress(count * block_size, total_size, start_time)
    url = cls.DATA_URL if url is None else url
    file_path, _ = urllib.request.urlretrieve(url, file_path, _progress)
    stat_info = os.stat(file_path)
    console.clear_line()
    console.show_status('Successfully downloaded {} ({} bytes).'.format(
      file_name, stat_info.st_size))

  @staticmethod
  def _split_path(path):
    return re.split(r'/|\\', path)

  @staticmethod
  def _check_path(*paths, create_path=True):
    assert len(paths) > 0
    if len(paths) == 1:
      paths = DataAgent._split_path(paths[0])
      if paths[0] in ['.', '']: paths.pop(0)
      if paths[-1] == '': paths.pop(-1)
    path = ""
    for p in paths:
      path = os.path.join(path, p)
      if not os.path.exists(path) and create_path:
        os.mkdir(path)
    # Return path
    return path

  @staticmethod
  def _show_data_sets_info(data_sets):
    from tframe.data.dataset import DataSet
    console.show_status('Data loaded')

    def get_data_info(data, name):
      sample = data if isinstance(data, np.ndarray) else data[0]
      assert isinstance(sample, np.ndarray)
      return 'shape of {}: {}'.format(name, sample.shape[1:])

    for data_set in data_sets:
      assert isinstance(data_set, DataSet)
      console.supplement('{} (size={}):'.format(data_set.name, data_set.size))
      console.supplement(get_data_info(data_set.features, 'features'), level=2)
      if data_set.targets is not None:
        console.supplement(get_data_info(data_set.targets, 'targets'), level=2)

  # endregion : Private Methods


class ImageDataAgent(DataAgent):
  """This class defines some common methods for image data agents"""
  @classmethod
  def load(cls, data_dir, train_size, validate_size, test_size,
           flatten=False, one_hot=True):
    data_set = cls.load_as_tframe_data(data_dir)
    if flatten:
      data_set.features = data_set.features.reshape(data_set.size, -1)
    if one_hot:
      data_set.targets = misc.convert_to_one_hot(
        data_set.targets, data_set[data_set.NUM_CLASSES])

    return cls._split_and_return(data_set, train_size, validate_size, test_size)

  @classmethod
  def load_as_tframe_data(cls, data_dir):
    from .dataset import DataSet
    file_path = os.path.join(data_dir, cls.TFD_FILE_NAME)
    if os.path.exists(file_path): return DataSet.load(file_path)

    # If .tfd file does not exist, try to convert from raw data
    console.show_status('Trying to convert raw data to tframe DataSet ...')
    images, labels = cls.load_as_numpy_arrays(data_dir)
    data_set = DataSet(images, labels, name=cls.DATA_NAME, **cls.PROPERTIES)

    # Generate groups if necessary
    if data_set.num_classes is not None:
      groups = []
      dense_labels = misc.convert_to_dense_labels(labels)
      for i in range(data_set.num_classes):
        # Find samples of class i and append to groups
        samples = list(np.argwhere([j == i for j in dense_labels]).ravel())
        groups.append(samples)
      data_set.properties[data_set.GROUPS] = groups

    # Show status
    console.show_status('Successfully converted {} samples'.format(
      data_set.size))
    # Save DataSet
    console.show_status('Saving data set ...')
    data_set.save(file_path)
    console.show_status('Data set saved to {}'.format(file_path))
    return data_set


