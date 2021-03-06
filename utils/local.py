from __future__ import absolute_import

import os
import re
import six

import tensorflow as tf

from tframe import hub
from . import console


def check_path(*paths, create_path=True):
  assert len(paths) > 0
  if len(paths) == 1:
    paths = re.split(r'/|\\', paths[0])
    if paths[0] in ['.', '']:
      paths.pop(0)
    if paths[-1] == '':
      paths.pop(-1)
  path = ""
  for p in paths:
    path += ('/' if len(path) > 0 else '') + p
    if not os.path.exists(path):
      if hub.should_create_path and create_path:
        os.mkdir(path)
      else: raise AssertionError('!! directory {} does not exist'.format(path))

  return path


def clear_paths(paths):
  if len(paths) == 0: return
  if isinstance(paths, six.string_types):
    paths = [paths]

  console.show_status('Cleaning path ...')
  for path in paths:
    # Delete all files in path
    for root, dirs, files in os.walk(path, topdown=False):
      # Remove directories
      for folder in dirs:
        clear_paths(os.path.join(root, folder))
      # Delete files
      for file in files:
        os.remove(os.path.join(root, file))

    # Show status
    console.supplement('Directory "{}" has been cleared'.format(path))


def load_checkpoint(path, session, saver):
  console.show_status("Access to directory '{}' ...".format(path))
  ckpt_state = tf.train.get_checkpoint_state(path)

  if ckpt_state and ckpt_state.model_checkpoint_path:
    ckpt_name = os.path.basename(ckpt_state.model_checkpoint_path)
    saver.restore(session, os.path.join(path, ckpt_name))
    counter = int(next(re.finditer("(\d+)(?!.*\d)", ckpt_name)).group(0))
    console.show_status("Loaded {}".format(ckpt_name))
    return True, counter
  else:
    if hub.train and hub.save_model:
      console.show_status('New checkpoints will be created ...')
    else:
      console.warning('Can not found model checkpoint')
    return False, 0


def save_checkpoint(path, session, saver, step):
  assert isinstance(saver, tf.train.Saver)
  saver.save(session, path, step)


def write_file(path, content, append=False):
  mode = 'a' if append else 'w'
  f = open(path, mode)
  f.write(content)
  f.close()
