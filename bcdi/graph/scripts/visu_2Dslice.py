# -*- coding: utf-8 -*-

# BCDI: tools for pre(post)-processing Bragg coherent X-ray diffraction imaging data
#   (c) 07/2017-06/2019 : CNRS UMR 7344 IM2NP
#   (c) 07/2019-present : DESY PHOTON SCIENCE
#       authors:
#         Jerome Carnis, carnis_jerome@yahoo.fr

import numpy as np
import matplotlib
matplotlib.use("Qt5Agg")
import matplotlib.pyplot as plt
import tkinter as tk
from tkinter import filedialog
import sys
sys.path.append('D:/myscripts/bcdi/')
import bcdi.graph.graph_utils as gu
import bcdi.utils.utilities as util

helptext = """
Graphical interface to visualize 2D slices through a 3D dataset in an easy way.
"""

datadir = "D:/data/P10_August2019/data/magnetite_A2_new_00013/pynxraw/"
savedir = datadir  # "D:/data/CH5309/S614/test/"
scale = 'log'  # 'linear' or 'log', scale of the 2D plots
field = None  # data field name. Leave it to None for default.
# It will take abs() for 'modulus', numpy.angle() for 'angle'
grey_background = True
background_plot = '0.5'  # in level of grey in [0,1], 0 being dark. For visual comfort
vmin = None  # lower boundary of the colorbar, leave it to None for default
vmax = None  # higher boundary of the colorbar, leave it to None for default


def press_key(event):
    """
    Interact with a plot for masking parasitic diffraction intensity or detector gaps

    :param event: button press event
    :return: updated controls
    """
    global data, dim, idx, vmin, max_colorbar, scale, savedir

    try:
        max_colorbar, idx, exit_flag = \
            gu.loop_thru_scan(key=event.key, data=data, figure=fig_loop, scale=scale, dim=dim, idx=idx, vmin=vmin,
                              vmax=max_colorbar, savedir=savedir)

        if exit_flag:
            plt.close(fig_loop)

    except AttributeError:  # mouse pointer out of axes
        pass


###################
# define colormap #
###################
if grey_background:
    bad_color = '0.7'
else:
    bad_color = '1.0'  # white background
colormap = gu.Colormap(bad_color=bad_color)
my_cmap = colormap.cmap

if field == 'angle' or field == 'modulus':
    scale = 'linear'

#############
# load data #
#############
root = tk.Tk()
root.withdraw()
file_path = filedialog.askopenfilename(initialdir=datadir, filetypes=[("NPZ", "*.npz"), ("NPY", "*.npy"),
                                                                      ("CXI", "*.cxi"), ("HDF5", "*.h5")])
nbfiles = len(file_path)
plt.ion()

data, extension = util.load_file(file_path, fieldname=field)

if data.max() <= 0:
    scale = 'linear'

if vmin is None:
    if scale == 'linear':
        vmin = data.min()
    else:  # 'log'
        vmin = max(data.min(), 0)
        vmin = max(np.log10(vmin), 0)
if vmax is None:
    if scale == 'linear':
        vmax = data.max()
    else:  # 'log', we are sure that data.max() is > 0
        vmax = np.log10(data.max())
#########################
# loop through the data #
#########################
plt.ioff()
nz, ny, nx = np.shape(data)
max_colorbar = vmax
print('Init', vmin, vmax)
# in XY
dim = 0
fig_loop = plt.figure()
idx = 0
original_data = np.copy(data)
if scale == 'linear':
    plt.imshow(data[idx, :, :], vmin=vmin, vmax=max_colorbar, cmap=my_cmap)
else:  # 'log'
    plt.imshow(np.log10(data[idx, :, :]), vmin=vmin, vmax=max_colorbar, cmap=my_cmap)
plt.title("Frame " + str(idx + 1) + "/" + str(nz) + "\n"
          "q quit ; u next frame ; d previous frame ; p unzoom\n"
          "right darker ; left brighter ; r save 2D frame")
plt.colorbar()
plt.connect('key_press_event', press_key)
fig_loop.set_facecolor(background_plot)
plt.show()
del dim, fig_loop

# in XZ
dim = 1
fig_loop = plt.figure()
idx = 0
if scale == 'linear':
    plt.imshow(data[:, idx, :], vmin=vmin, vmax=max_colorbar, cmap=my_cmap)
else:  # 'log'
    plt.imshow(np.log10(data[:, idx, :]), vmin=vmin, vmax=max_colorbar, cmap=my_cmap)
plt.title("Frame " + str(idx + 1) + "/" + str(ny) + "\n"
          "q quit ; u next frame ; d previous frame ; p unzoom\n"
          "right darker ; left brighter ; r save 2D frame")
plt.colorbar()
plt.connect('key_press_event', press_key)
fig_loop.set_facecolor(background_plot)
plt.show()
del dim, fig_loop

# in YZ
dim = 2
fig_loop = plt.figure()
idx = 0
if scale == 'linear':
    plt.imshow(data[:, :, idx], vmin=vmin, vmax=max_colorbar, cmap=my_cmap)
else:  # 'log'
    plt.imshow(np.log10(data[:, :, idx]), vmin=vmin, vmax=max_colorbar, cmap=my_cmap)
plt.title("Frame " + str(idx + 1) + "/" + str(nx) + "\n"
          "q quit ; u next frame ; d previous frame ; p unzoom\n"
          "right darker ; left brighter ; r save 2D frame")
plt.colorbar()
plt.connect('key_press_event', press_key)
fig_loop.set_facecolor(background_plot)
plt.show()