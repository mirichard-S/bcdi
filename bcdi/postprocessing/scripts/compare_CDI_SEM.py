# -*- coding: utf-8 -*-

# BCDI: tools for pre(post)-processing Bragg coherent X-ray diffraction imaging data
#   (c) 07/2017-06/2019 : CNRS UMR 7344 IM2NP
#   (c) 07/2019-present : DESY PHOTON SCIENCE
#       authors:
#         Jerome Carnis, carnis_jerome@yahoo.fr

import json
import matplotlib.pyplot as plt
from numbers import Real
import numpy as np
import os
import pathlib
from scipy.interpolate import interp1d
from scipy.ndimage.measurements import center_of_mass
from scipy.signal import correlate
from scipy.stats import pearsonr
import sys
import tkinter as tk
from tkinter import filedialog
sys.path.append('D:/myscripts/bcdi/')
import bcdi.graph.graph_utils as gu
import bcdi.utils.utilities as util
import bcdi.utils.validation as valid

helptext = """
This script can be used to compare the lateral sizes of an object measured by CDI and scanning electron micrscopy. Two
dictionary should be provided as input (one for each technique). The dictionary should contain the following items:
{'threshold': 1D array-like values of thresholds,
 'angles':D array-like values of angles 
 'ang_width_threshold': 2D array-like values (one row for each threshold, the row is the width vs angle of the linecut)}

These dictionaries can be produced by the script angular_profile.py

After aligning the traces of the width vs angle (e.g. if the object was slightly rotated in one of the measurements),
the traces are overlaid in order to determine which threshold is correct.     
"""

datadir = "D:/data/P10_2nd_test_isosurface_Dec2020/data_nanolab/dataset_1/PtNP1_00128/result/linecuts/"
# "D:/data/P10_2nd_test_isosurface_Dec2020/data_nanolab/dataset_1/PtNP1_00128/result/"  # data folder
savedir = "D:/data/P10_2nd_test_isosurface_Dec2020/data_nanolab/dataset_1/PtNP1_00128/result/linecuts/"
# results will be saved here, if None it will default to datadir
index_sem = 2  # index of the threshold to use for the SEM profile. Leave None to print the available thresholds.
# Leave None to print the available thresholds.
comment = '_upsampled_5'  # string to add to the filename when saving, should start with "_"
##################################
# end of user-defined parameters #
##################################

###############################
# list of colors for the plot #
###############################
colors = ('b', 'g', 'r', 'c', 'm', 'y', 'k')
markers = ('.', 'v', '^', '<', '>')

#########################
# check some parameters #
#########################
savedir = savedir or datadir
pathlib.Path(savedir).mkdir(parents=True, exist_ok=True)

########################
# load the SEM profile #
########################
plt.ion()
root = tk.Tk()
root.withdraw()
file_path = filedialog.askopenfilename(initialdir=datadir, title='select the dictionary containing SEM profiles',
                                       filetypes=[("JSON", "*.json"), ("NPZ", "*.npz")])

_, ext = os.path.splitext(file_path)
if ext == '.json':
    with open(file_path, 'r') as f:
        json_string = f.read()
    sem_dict = json.loads(json_string, object_hook=util.decode_json)
else:
    raise ValueError(f'expecting as JSON file, got a {ext}')

#########################
# load the BCDI profile #
#########################
plt.ion()
root = tk.Tk()
root.withdraw()
file_path = filedialog.askopenfilename(initialdir=datadir, title='select the dictionary containing BCDI profiles',
                                       filetypes=[("JSON", "*.json"), ("NPZ", "*.npz")])

_, ext = os.path.splitext(file_path)
if ext == '.json':
    with open(file_path, 'r') as f:
        json_string = f.read()
    bcdi_dict = json.loads(json_string, object_hook=util.decode_json)
else:
    raise ValueError(f'expecting as JSON file, got a {ext}')

try:
    if not np.all(sem_dict['angles'] == bcdi_dict['angles']):
        print('angular steps are not equal:')
        print(f"SEM angles: {sem_dict['angles']}")
        print(f"BCDI angles: {bcdi_dict['angles']}")
        raise NotImplementedError
except KeyError:
    print('missing key angles in one of the dictionary')
    raise

####################################################################
# get the angular shift between SEM and BCDI traces and align them #
####################################################################
if index_sem is None:
    print(f"thresholds SEM: {sem_dict['threshold']}")
    sys.exit()

sem_trace = sem_dict['ang_width_threshold'][index_sem]
bcdi_trace = bcdi_dict['ang_width_threshold'][0]
cross_corr = np.correlate(sem_trace - np.mean(sem_trace), bcdi_trace - np.mean(bcdi_trace), mode="full")
lags = np.arange(-sem_trace.size + 1, bcdi_trace.size)
lag = lags[np.argmax(cross_corr)]

# plot the cross-correlation
plt.figure(figsize=(12, 9))
ax0 = plt.subplot(121)
line, = ax0.plot(sem_trace)
line.set_label("SEM trace")
line, = ax0.plot(bcdi_trace)
line.set_label("BCDI trace")

print(f'lag between the two traces = {lag}')
print('aligning the SEM trace on the BCDI traces')
sem_trace = np.roll(sem_trace, -lag)

line, = ax0.plot(sem_trace)
line.set_label("SEM trace aligned")
ax0.set_xlabel('angle (deg)', fontsize=20)
ax0.set_ylabel('width (nm)', fontsize=20)
ax0.legend(fontsize=14)
ax1 = plt.subplot(122)
ax1.plot(cross_corr)
ax1.set_title("cross-correlated signal", fontsize=14)
plt.tight_layout()  # avoids the overlap of subplots with axes labels

##########################################################################
# plot the aligned BDCI traces for different thresholds vs the SEM trace #
##########################################################################
thres_bcdi = bcdi_dict['threshold']
angles_bcdi = bcdi_dict['angles']
correlation = np.zeros(thres_bcdi.size)
fig = plt.figure(figsize=(12, 9))
ax0 = plt.subplot(121)
line, = ax0.plot(sem_dict['angles'], sem_trace, color=colors[0], marker=markers[0], fillstyle='none',
                 markersize=6, linestyle='-', linewidth=1)
line.set_label(f"SEM thres {sem_dict['threshold'][index_sem]}")

for idx, thres in enumerate(thres_bcdi, start=1):
    bcdi_trace = bcdi_dict['ang_width_threshold'][idx-1]
    cross_corr = np.correlate(sem_trace - np.mean(sem_trace), bcdi_trace - np.mean(bcdi_trace), mode="full")
    lag = lags[np.argmax(cross_corr)]
    sem_trace = np.roll(sem_trace, -lag)
    print(f'bcdi trace {idx}, threshold = {thres}, lag = {lag}')

    correlation[idx-1] = pearsonr(sem_trace, bcdi_trace)[0]
    line, = ax0.plot(angles_bcdi, bcdi_trace, color=colors[idx % len(colors)],
                     marker=markers[(idx // len(colors)) % len(markers)], fillstyle='none', markersize=6,
                     linestyle='-', linewidth=1)
    line.set_label(f'threshold {thres}')

ax0.set_xlabel('angle (deg)', fontsize=20)
ax0.set_ylabel('width (nm)', fontsize=20)
ax0.tick_params(axis='both', which='major', labelsize=16)
ax1 = plt.subplot(122)
line, = ax1.plot(thres_bcdi, correlation, color=colors[0], marker=markers[0], fillstyle='none', markersize=6,
                 linestyle='-', linewidth=1)
ax1.set_xlabel('threshold', fontsize=20)
ax1.set_ylabel('Pearson correlation coeff.', fontsize=20)
ax1.tick_params(axis='both', which='major', labelsize=16)
plt.tight_layout()  # avoids the overlap of subplots with axes labels
fig.savefig(savedir + 'compa_width_vs_ang' + comment + '.png')
ax0.legend(fontsize=14)
fig.savefig(savedir + 'compa_width_vs_ang' + comment + '_legend.png')

plt.ioff()
plt.show()