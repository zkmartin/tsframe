from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import os
import re
import six

import numpy as np

from tframe import pedia
from tframe import console
from tframe.data.dataset import DataSet

import tframe.utils.misc as misc

try:
  import tkinter as tk
  from tkinter import filedialog
  from PIL import Image as Image_
  from PIL import ImageTk
except:
  print('!! ImageViewer is disabled, install pillow and tkinter to enable it')


class ImageViewer(object):
  """Image Viewer for TFData
     Features:
     (1) One-hot labels will be converted automatically (done by TFData)
     (2) Support save and load
  """
  MIN_WIDTH = 260
  MIN_HEIGHT = 260

  def __init__(self, dataset=None):
    # Variables
    self.filename = None
    self.image_height = self.MIN_HEIGHT
    self.image_width = self.MIN_WIDTH

    # Create interface root
    self.form = tk.Tk()

    # Create frames and widgets
    self.top_frame = tk.Frame(self.form, bg='white')
    self.canvas = tk.Canvas(self.form, bg='white', highlightthickness=0)
    self.bottom_frame = tk.Frame(self.form, bg='white')
    self.image_info = tk.Label(self.top_frame, bd=0, bg='white')
    self.details = tk.Label(self.bottom_frame, bd=0, bg='white')

    # Create layout
    self._create_layout()

    # Data set
    self._cursor = 0
    self.data_set = None
    self.labels = None
    self.set_data(dataset)
    self._update_title()

  # region : Properties

  @property
  def screen_size(self):
    assert isinstance(self.form, tk.Tk)
    return self.form.winfo_screenheight(), self.form.winfo_screenwidth()

  @property
  def height(self):
    label_height = (self.top_frame.winfo_height() +
                    self.bottom_frame.winfo_height())
    return label_height + self.image_height

  @property
  def width(self):
    return self.image_width

  @property
  def last_dir(self):
    if self.filename is None:
      return os.getcwd()
    else:
      paths = re.split(r'/|\\', self.filename)
      return '/'.join(paths[:-1])

  @property
  def sample_can_be_displayed(self):
    assert self.data_set is not None
    sample_shape = self.data_set.features[0].shape
    return len(sample_shape) > 1

  # endregion : Properties

  # region : Public Methods

  def set_data(self, data_set):
    if data_set is not None:
      # If a path is given
      if isinstance(data_set, six.string_types):
        data_set = DataSet.load(data_set)
      if not isinstance(data_set, DataSet):
        raise TypeError('!! Data set must be an instance of tframe DataSet')
      if not data_set.is_regular_array:
        data_set = data_set.stack
      self.data_set = data_set
      self._set_cursor(0)
      if self.data_set.targets is not None:
        self.labels = misc.convert_to_dense_labels(self.data_set.targets)
      console.show_status('Data set set to ImageViewer')

      # Refresh image viewer
      self.refresh()

  def show(self):
    assert isinstance(self.form, tk.Tk)
    self.form.after(20, self._move_to_center)
    self.form.mainloop()

  # endregion : Public Methods

  # region : Private Methods

  def _set_cursor(self, index=None, step=None):
    assert isinstance(self.data_set, DataSet)
    if step is not None:
      assert step in (-1, 1)
      index = self._cursor + step
    assert index is not None
    self._cursor = np.mod(index, self.data_set.size)

  def _create_layout(self):
    # Form properties
    self.form.title('Image Viewer')
    # self.form.resizable(width=False, height=False)

    # Widgets
    self.top_frame.pack(side=tk.TOP, fill=tk.X)
    self.bottom_frame.pack(side=tk.BOTTOM, fill=tk.X)
    self.canvas.pack(side=tk.TOP, fill=tk.BOTH)

    self.image_info.pack(side=tk.LEFT, padx=5)
    self.details.pack(side=tk.LEFT, padx=5)

    # Key binds
    self.form.bind('<Key>', self._on_key_press)
    self.form.bind('<Control-s>', self.save_data_set)
    self.form.bind('<Control-l>', self.load_data_set)

  def _move_to_center(self):
    sh, sw = self.screen_size
    x = sw // 2 - self.width // 2
    y = sh // 2 - self.height // 2
    self.form.geometry('{}x{}+{}+{}'.format(self.width, self.height, x, y))

  def _on_key_press(self, event):
    assert isinstance(event, tk.Event)

    flag = False
    if event.keysym == 'Escape':
      self.form.quit()
    elif event.keysym == 'j':
      flag = self._move_cursor(1)
    elif event.keysym == 'k':
      flag = self._move_cursor(-1)
    elif event.keysym == 'quoteleft':
      console.show_status('Widgets sizes:')
      for k in self.__dict__.keys():
        item = self.__dict__[k]
        if isinstance(item, tk.Widget) or k == 'form':
          str = '[{}] {}: {}x{}'.format(
            item.__class__, k, item.winfo_height(), item.winfo_width())
          console.supplement(str)
    elif event.keysym == 'Tab':
      if self.data_set is None: return
      assert isinstance(self.data_set, DataSet)
      data = self.data_set.data_dict
      data[pedia.features] = self.data_set.features
      if self.data_set.targets is not None:
        data[pedia.targets] = self.data_set.targets
      console.show_status('Data:', '::')
      for k, v in data.items():
        if not hasattr(v, 'shape'): continue
        console.supplement('{}: {}'.format(k, v.shape))
      for k, v in self.data_set.properties.items():
        console.supplement('{}: {}'.format(k, v))
    elif event.keysym == 'space':
      self._resize()
    else:
      # console.show_status(event.keysym)
      pass

    # If needed, refresh image viewer
    if flag: self.refresh()

  def _move_cursor(self, step):
    assert step in [-1, 1]
    flag = False
    if self.data_set is not None:
      assert isinstance(self.data_set, DataSet)
      if self.data_set.size == 0: return False
      self._set_cursor(step=step)
      flag = True
    return flag

  def refresh(self):
    self._update_info()
    self._update_image()
    self._update_details()
    self._resize()

  def _update_title(self):
    filename = 'New Data Set'
    if self.filename is not None:
      # Hide directory information
      paths = re.split(r'/|\\]', self.filename)
      filename = paths[-1]
      # Hide extension 'cause it provides no information
      filename = filename[:-4]
    title = 'Image Viewer - {}'.format(filename)
    self.form.title(title)

  def _update_info(self):
    if self.data_set is not None:
      assert isinstance(self.data_set, DataSet)
      cursor = self._cursor
      info = ''
      if self.labels is not None:
        label = self.labels[cursor]
        label = self._get_class_string(label)
        info = 'Label: {}'.format(label)
      self.image_info.config(fg='Black', text='[{} / {}] {}'.format(
        cursor + 1, self.data_set.size, info))
    else:
      self.image_info.config(text='No data set found', fg='grey')

  def _update_image(self):
    if self.data_set is not None:
      assert isinstance(self.data_set, DataSet)
      cursor = self._cursor
      image = np.squeeze(self.data_set.features[cursor])
      if not self.sample_can_be_displayed:
        self.canvas.config(bg='light grey')
        return

      # Convert image data type
      if np.max(image) <= 1.0:
        image = np.around(image * 255)
      # IMPORTANT!
      image = image.astype('uint8')

      # Adjust canvas size
      shape = image.shape
      width = max(shape[1], self.MIN_WIDTH)
      height = int(np.round(1.0 * width / shape[1] * shape[0]))
      self.canvas.config(width=width, height=height)
      self.image_height = height
      self.image_width = width
      # Draw image
      mode = 'RGB' if len(shape) == 3 else None
      image = Image_.fromarray(image, mode)
      image = image.resize((width, height))
      self.photo = ImageTk.PhotoImage(image=image)

      self.canvas.create_image(0, 0, anchor=tk.NW, image=self.photo)
    else:
      self.canvas.config(bg='light grey')

  def _update_details(self):
    assert isinstance(self.data_set, DataSet)
    # Try to get predictions
    try: predictions = self.data_set[pedia.predictions]
    except: predictions = None
    if predictions is not None:
      predictions = misc.convert_to_dense_labels(predictions)
      cursor = self._cursor
      prediction = predictions[cursor]
      if isinstance(prediction, np.ndarray): prediction = prediction[0]
      info = 'Prediction: {}'.format(self._get_class_string(prediction))
      color = 'black'
      if self.labels is not None:
        color = 'green' if self.labels[cursor] == prediction else 'red'
      self.details.config(text=info, fg=color)
    else:
      self.details.config(text='No details', fg='grey')

  def _get_class_string(self, label):
    classes = self.data_set.properties.get('CLASSES', None)
    if classes is not None: label = classes[label]
    return '{}'.format(label)

  def _resize(self):
    self.form.geometry('{}x{}'.format(self.width, self.height))

  def save_data_set(self, _):
    if self.data_set is None:
      # console.show_status('No data set found')
      return
    filename = filedialog.asksaveasfilename(
      initialdir=self.last_dir, title='Save data set',
      filetypes=(("TFData files", '*.tfd'),))
    if filename == '':
      return
    if filename[-4:] != '.tfd':
      filename = '{}.tfd'.format(filename)

    self.data_set.save_model(filename)
    # Print status
    self.filename = filename
    print(">> Data set saved to '{}'".format(filename))
    self._update_title()

  def load_data_set(self, _):
    filename = filedialog.askopenfilename(
      initialdir=self.last_dir, title='Load data set',
      filetypes=(("TFData files", '*.tfd'),))
    if filename == '':
      return

    self.filename = filename
    self.set_data(DataSet.load(filename))
    self._update_title()

    # Print status
    print(">> Loaded data set '{}'".format(filename))

  # endregion : Private Methods

  '''For some reasons, do not remove this line'''


if __name__ == '__main__':
  data_set = None
  viewer = ImageViewer(data_set)
  viewer.show()
