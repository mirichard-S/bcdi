# -*- coding: utf-8 -*-

# BCDI: tools for pre(post)-processing Bragg coherent X-ray diffraction imaging data
#   (c) 07/2017-06/2019 : CNRS UMR 7344 IM2NP
#   (c) 07/2019-05/2021 : DESY PHOTON SCIENCE
#   (c) 06/2021-present : DESY CFEL
#       authors:
#         Jerome Carnis, carnis_jerome@yahoo.fr

"""
Detector classes.

These classes handles the detector config used for data acquisition. The available
detectors are:

- Maxipix
- Eiger2M
- Eiger4M
- Timepix
- Merlin
- Dummy

"""

from abc import ABC, abstractmethod
import numpy as np
from numbers import Real
import os

from bcdi.utils import validation as valid


def create_detector(name, **kwargs):
    """
    Create a Detector instance depending on the detector.

    :param name: str, name of the detector
    :return:  the corresponding diffractometer instance
    """
    if name == "Maxipix":
        return Maxipix(name=name, **kwargs)
    if name == "Eiger2M":
        return Eiger2M(name=name, **kwargs)
    if name == "Eiger4M":
        return Eiger4M(name=name, **kwargs)
    if name == "Timepix":
        return Timepix(name=name, **kwargs)
    if name == "Merlin":
        return Merlin(name=name, **kwargs)
    if name == "Dummy":
        return Dummy(name=name, **kwargs)
    raise NotImplementedError(f"No implementation for the {name} detector")


class Detector(ABC):
    """
    Class to handle the configuration of the detector used for data acquisition.

    :param name: name of the detector in {'Maxipix', 'Timepix', 'Merlin', 'Eiger2M',
     'Eiger4M', 'Dummy'}
    :param datadir: directory where the data files are located
    :param savedir: directory where to save the results
    :param template_imagefile: beamline-dependent template for the data files

     - ID01: 'data_mpx4_%05d.edf.gz' or 'align_eiger2M_%05d.edf.gz'
     - SIXS_2018: 'align.spec_ascan_mu_%05d.nxs'
     - SIXS_2019: 'spare_ascan_mu_%05d.nxs'
     - Cristal: 'S%d.nxs'
     - P10: '_master.h5'
     - NANOMAX: '%06d.h5'
     - 34ID: 'Sample%dC_ES_data_51_256_256.npz'

    :param specfile: template for the log file or the data file depending on the
     beamline
    :param roi: region of interest of the detector used for analysis
    :param sum_roi: region of interest of the detector used for calculated an
     integrated intensity
    :param binning: binning factor of the 3D dataset
     (stacking dimension, detector vertical axis, detector horizontal axis)
    :param kwargs:

     - 'preprocessing_binning': tuple of the three binning factors used in a previous
       preprocessing step
     - 'offsets': tuple or list, sample and detector offsets corresponding to the
       parameter delta in xrayutilities hxrd.Ang2Q.area method
     - 'linearity_func': function to apply to each pixel of the detector in order to
       compensate the deviation of the detector linearity for large intensities.

    """

    def __init__(
        self,
        name,
        rootdir=None,
        datadir=None,
        savedir=None,
        template_file=None,
        template_imagefile=None,
        specfile=None,
        sample_name=None,
        roi=None,
        sum_roi=None,
        binning=(1, 1, 1),
        **kwargs,
    ):
        # the detector name should be initialized first,
        # other properties are depending on it
        self._name = name

        # load the kwargs
        self.preprocessing_binning = kwargs.get("preprocessing_binning") or (1, 1, 1)
        self.offsets = kwargs.get("offsets")  # delegate the test to xrayutilities
        linearity_func = kwargs.get("linearity_func")
        if linearity_func is not None and not callable(linearity_func):
            raise TypeError(
                f"linearity_func should be a function, got {type(linearity_func)}"
            )
        self._linearity_func = linearity_func

        # load other positional arguments
        self.binning = binning
        self.roi = roi
        self.sum_roi = sum_roi
        # parameters related to data path
        self.rootdir = rootdir
        self.datadir = datadir
        self.savedir = savedir
        self.sample_name = sample_name
        self.template_file = template_file
        self.template_imagefile = template_imagefile
        self.specfile = specfile

        # dictionary of keys: beamline_name and values: counter name for the image
        # number in the log file.
        self._counter_table = {}

        # initialize the threshold for saturation, can be overriden in child classes
        self.saturation_threshold = None

    @property
    def binning(self):
        """
        Binning factor of the dataset.

        Tuple of three positive integers corresponding to the binning of the data used
        in phase retrieval (stacking dimension, detector vertical axis, detector
        horizontal axis). To declare an additional binning factor due to a previous
        preprocessing step, use the kwarg 'preprocessing_binning' instead.
        """
        return self._binning

    @binning.setter
    def binning(self, value):
        valid.valid_container(
            value,
            container_types=(tuple, list),
            length=3,
            item_types=int,
            min_excluded=0,
            name="Detector.binning",
        )
        self._binning = value

    def counter(self, beamline):
        """
        Name of the counter in the log file for the image number.

        :param beamline: str, name of the beamline
        """
        if not isinstance(beamline, str):
            raise TypeError("beamline should be a string")
        return self._counter_table.get(beamline)

    @property
    def datadir(self):
        """Name of the data directory."""
        return self._datadir

    @datadir.setter
    def datadir(self, value):
        valid.valid_container(
            value,
            container_types=str,
            min_length=1,
            allow_none=True,
            name="Detector.datadir",
        )
        self._datadir = value

    @property
    def name(self):
        """Name of the detector."""
        return self._name

    @property
    def nb_pixel_x(self):
        """
        Horizontal number of pixels of the detector.

        It takes into account an eventual preprocessing binning (useful when
        reloading a already preprocessed file).
        """
        return self.unbinned_pixel_number[1] // self.preprocessing_binning[2]

    @property
    def nb_pixel_y(self):
        """
        Vertical number of pixels of the detector.

        It takes into account an eventual preprocessing binning (useful when
        reloading a already preprocessed file).
        """
        return self.unbinned_pixel_number[0] // self.preprocessing_binning[1]

    @property
    def params(self):
        """Return a dictionnary with all parameters."""
        return {
            "Class": self.__class__.__name__,
            "name": self.name,
            "unbinned_pixel_size_m": self.unbinned_pixel_size,
            "nb_pixel_x": self.nb_pixel_x,
            "nb_pixel_y": self.nb_pixel_y,
            "binning": self.binning,
            "roi": self.roi,
            "sum_roi": self.sum_roi,
            "preprocessing_binning": self.preprocessing_binning,
            "rootdir": self.rootdir,
            "datadir": self.datadir,
            "scandir": self.scandir,
            "savedir": self.savedir,
            "sample_name": self.sample_name,
            "template_file": self.template_file,
            "template_imagefile": self.template_imagefile,
            "specfile": self.specfile,
        }

    @property
    def pixelsize_x(self):
        """Horizontal pixel size of the detector after taking into account binning."""
        return (
            self.unbinned_pixel_size[1]
            * self.preprocessing_binning[2]
            * self.binning[2]
        )

    @property
    def pixelsize_y(self):
        """Vertical pixel size of the detector after taking into account binning."""
        return (
            self.unbinned_pixel_size[0]
            * self.preprocessing_binning[1]
            * self.binning[1]
        )

    @property
    def preprocessing_binning(self):
        """
        Preprocessing binning factor of the data.

        Tuple of three positive integers corresponding to the binning factor of the
        data used in a previous preprocessing step (stacking dimension, detector
        vertical axis, detector horizontal axis).
        """
        return self._preprocessing_binning

    @preprocessing_binning.setter
    def preprocessing_binning(self, value):
        valid.valid_container(
            value,
            container_types=(tuple, list),
            length=3,
            item_types=int,
            min_excluded=0,
            name="Detector.preprocessing_binning",
        )
        self._preprocessing_binning = value

    @property
    def roi(self):
        """
        Region of interest of the detector to be used.

        Convention: [y_start, y_stop, x_start, x_stop]
        """
        return self._roi

    @roi.setter
    def roi(self, value):
        if not value:  # None or empty list/tuple
            value = [0, self.nb_pixel_y, 0, self.nb_pixel_x]
        valid.valid_container(
            value,
            container_types=(tuple, list),
            length=4,
            item_types=int,
            name="Detector.roi",
        )
        self._roi = value

    @property
    def rootdir(self):
        """Name of the root directory, which englobes all scans."""
        return self._rootdir

    @rootdir.setter
    def rootdir(self, value):
        valid.valid_container(
            value,
            container_types=str,
            min_length=1,
            allow_none=True,
            name="Detector.rootdir",
        )
        self._rootdir = value

    @property
    def sample_name(self):
        """Name of the sample."""
        return self._sample_name

    @sample_name.setter
    def sample_name(self, value):
        valid.valid_container(
            value,
            container_types=str,
            min_length=1,
            allow_none=True,
            name="Detector.sample_name",
        )
        self._sample_name = value

    @property
    def savedir(self):
        """Name of the saving directory."""
        return self._savedir

    @savedir.setter
    def savedir(self, value):
        valid.valid_container(
            value,
            container_types=str,
            min_length=1,
            allow_none=True,
            name="Detector.savedir",
        )
        self._savedir = value

    @property
    def scandir(self):
        """Path of the scan, typically it is the parent folder of the data folder."""
        if self.datadir:
            dir_path = os.path.abspath(os.path.join(self.datadir, os.pardir)) + "/"
            return dir_path.replace("\\", "/")

    @property
    def sum_roi(self):
        """
        Region of interest of the detector used for integrating the intensity.

        Convention: [y_start, y_stop, x_start, x_stop]
        """
        return self._sum_roi

    @sum_roi.setter
    def sum_roi(self, value):
        if not value:  # None or empty list/tuple
            if not self.roi:
                value = [0, self.nb_pixel_y, 0, self.nb_pixel_x]
            else:
                value = self.roi
        valid.valid_container(
            value,
            container_types=(tuple, list),
            length=4,
            item_types=int,
            name="Detector.sum_roi",
        )
        self._sum_roi = value

    @property
    def template_file(self):
        """Template that can be used to generate template_imagefile."""
        return self._template_file

    @template_file.setter
    def template_file(self, value):
        valid.valid_container(
            value,
            container_types=str,
            min_length=0,
            allow_none=True,
            name="Detector.template_file",
        )
        self._template_file = value

    @property
    def template_imagefile(self):
        """Name of the data file."""
        return self._template_imagefile

    @template_imagefile.setter
    def template_imagefile(self, value):
        valid.valid_container(
            value,
            container_types=str,
            min_length=0,
            allow_none=True,
            name="Detector.imagefile",
        )
        self._template_imagefile = value

    @property
    @abstractmethod
    def unbinned_pixel_number(self):
        """
        Define the number of pixels of the unbinned detector.

        Convention: (vertical, horizontal)
        """

    @property
    @abstractmethod
    def unbinned_pixel_size(self):
        """Pixel size (vertical, horizontal) of the unbinned detector in meters."""

    def __repr__(self):
        """Representation string of the Detector instance."""
        return (
            f"{self.__class__.__name__}(name='{self.name}', "
            f"unbinned_pixel_size={self.unbinned_pixel_size}, "
            f"nb_pixel_x={self.nb_pixel_x}, "
            f"nb_pixel_y={self.nb_pixel_y}, "
            f"binning={self.binning},\n"
            f"roi={self.roi}, "
            f"sum_roi={self.sum_roi}, "
            f"preprocessing_binning={self.preprocessing_binning}, "
            f"rootdir = {self.rootdir},\n"
            f"datadir = {self.datadir},\n"
            f"scandir = {self.scandir},\n"
            f"savedir = {self.savedir},\n"
            f"sample_name = {self.sample_name},"
            f" template_file = {self.template_file}, "
            f"template_imagefile = {self.template_imagefile},"
            f" specfile = {self.specfile},\n"
        )

    @staticmethod
    def _background_subtraction(data, background):
        """
        Apply background subtraction to the data.

        :param data: a 2D numpy ndarray
        :param background: None or a 2D numpy array
        :return: the corrected data array
        """
        if not isinstance(data, np.ndarray):
            raise TypeError("data should be a numpy array")
        if data.ndim != 2:
            raise ValueError("data should be a 2D array")
        if background is not None:
            if not isinstance(background, np.ndarray):
                raise TypeError("background should be a numpy array")
            if background.shape != data.shape:
                raise ValueError(
                    "background and data must have the same shape"
                    f"background is {background.shape} while data is {data.shape}"
                )
            return data - background
        return data

    @staticmethod
    def _flatfield_correction(data, flatfield):
        """
        Apply flatfield correction to the data.

        :param data: a 2D numpy ndarray
        :param flatfield: None or a 2D numpy array
        :return: the corrected data array
        """
        if not isinstance(data, np.ndarray):
            raise TypeError("data should be a numpy array")
        if data.ndim != 2:
            raise ValueError("data should be a 2D array")
        if flatfield is not None:
            if not isinstance(flatfield, np.ndarray):
                raise TypeError("flatfield should be a numpy array")
            if flatfield.shape != data.shape:
                raise ValueError(
                    "flatfield and data must have the same shape"
                    f"flatfield is {flatfield.shape} while data is {data.shape}"
                )
            return np.multiply(flatfield, data)
        return data

    @staticmethod
    def _hotpixels_correction(data, mask, hotpixels):
        """
        Apply hotpixels correction to the data and update the mask.

        :param data: a 2D numpy ndarray
        :param hotpixels: None or a 2D numpy array, 1 if the pixel needs to be masked,
         0 otherwise
        :return: the corrected data array
        """
        if not isinstance(data, np.ndarray):
            raise TypeError("data should be a numpy array")
        if not isinstance(mask, np.ndarray):
            raise TypeError("mask should be a numpy array")
        if data.ndim != 2:
            raise ValueError("data should be a 2D array")
        if mask.ndim != data.ndim:
            raise ValueError(
                "mask and data must have the same shape"
                f"mask is {mask.shape} while data is {data.shape}"
            )
        if hotpixels is not None:
            if not isinstance(hotpixels, np.ndarray):
                raise TypeError("hotpixels should be a numpy array")
            if hotpixels.shape != data.shape:
                raise ValueError(
                    "hotpixels and data must have the same shape"
                    f"hotpixels is {hotpixels.shape} while data is {data.shape}"
                )
            if ((hotpixels == 0).sum() + (hotpixels == 1).sum()) != hotpixels.size:
                raise ValueError("hotpixels should be an array of 0 and 1")

            data[hotpixels == 1] = 0
            mask[hotpixels == 1] = 1

        return data, mask

    def _linearity_correction(self, data):
        """
        Apply a correction to data if the detector response is not linear.

        :param data: a 2D numpy array
        :return: the corrected data array
        """
        if not isinstance(data, np.ndarray):
            raise TypeError("data should be a numpy array")
        if data.ndim != 2:
            raise ValueError("data should be a 2D array")
        data = data.astype(float)
        if self._linearity_func is not None:
            nby, nbx = data.shape
            return self._linearity_func(data.flatten()).reshape((nby, nbx))
        return data

    def mask_detector(
        self, data, mask, nb_frames=1, flatfield=None, background=None, hotpixels=None
    ):
        """
        Mask data measured with a 2D detector.

        It can apply flatfield correction, background subtraction, masking of hotpixels
        and detector gaps.

        :param data: the 2D data to mask
        :param mask: the 2D mask to be updated
        :param nb_frames: number of frames summed to yield the 2D data
         (e.g. in a series measurement), used when defining the threshold for hot pixels
        :param flatfield: the 2D flatfield array to be multiplied with the data
        :param background: a 2D array to be subtracted to the data
        :param hotpixels: a 2D array with hotpixels to be masked
         (1=hotpixel, 0=normal pixel)
        :return: the masked data and the updated mask
        """
        if not isinstance(data, np.ndarray) or not isinstance(mask, np.ndarray):
            raise TypeError("data and mask should be numpy arrays")
        if data.ndim != 2 or mask.ndim != 2:
            raise ValueError("data and mask should be 2D arrays")

        if data.shape != mask.shape:
            raise ValueError(
                "data and mask must have the same shape\n data is ",
                data.shape,
                " while mask is ",
                mask.shape,
            )

        # linearity correctiondata
        if self._linearity_func is not None:
            data = self._linearity_func(data)

        # flatfield correction
        data = self._flatfield_correction(data=data, flatfield=flatfield)

        # remove the background
        data = self._background_subtraction(data=data, background=background)

        # mask hotpixels
        data, mask = self._hotpixels_correction(
            data=data, mask=mask, hotpixels=hotpixels
        )
        # mask detector gaps
        data, mask = self._mask_gaps(data, mask)

        # remove saturated pixels
        data, mask = self._saturation_correction(data, mask, nb_frames=nb_frames)

        return data, mask

    @staticmethod
    def _mask_gaps(data, mask):
        """
        Mask the gaps between sensors in the detector.

        :param data: a 2D numpy array
        :param mask: a 2D numpy array of the same shape as data
        :return:

         - the masked data
         - the updated mask

        """
        if not isinstance(data, np.ndarray):
            raise TypeError("data should be a numpy array")
        if not isinstance(mask, np.ndarray):
            raise TypeError("mask should be a numpy array")
        if data.ndim != 2:
            raise ValueError("data should be a 2D array")
        if mask.ndim != data.ndim:
            raise ValueError(
                "mask and data must have the same shape"
                f"mask is {mask.shape} while data is {data.shape}"
            )
        return data, mask

    def _saturation_correction(self, data, mask, nb_frames):
        """
        Mask pixels above a certain threshold.

        This is detector dependent.

        :param data: a 2D numpy array
        :param mask: a 2D numpy array of the same shape as data
        :param nb_frames: int, number of frames concatenated to obtain the 2D data array
        :return:

         - the masked data
         - the updated mask

        """
        if self.saturation_threshold is not None:
            if not isinstance(data, np.ndarray):
                raise TypeError("data should be a numpy array")
            if not isinstance(mask, np.ndarray):
                raise TypeError("mask should be a numpy array")
            if data.ndim != 2:
                raise ValueError("data should be a 2D array")
            if mask.ndim != data.ndim:
                raise ValueError(
                    "mask and data must have the same shape"
                    f"mask is {mask.shape} while data is {data.shape}"
                )
            valid.valid_item(
                nb_frames, allowed_types=int, min_excluded=0, name="nb_frames"
            )
            mask[data > self.saturation_threshold * nb_frames] = 1
            data[data > self.saturation_threshold * nb_frames] = 0
        return data, mask


class Maxipix(Detector):
    """Implementation of the Maxipix detector."""

    def __init__(self, name, **kwargs):
        super().__init__(name=name, **kwargs)
        self._counter_table = {"ID01": "mpx4inr"}  # useful if the same type of detector
        # is used at several beamlines
        self.saturation_threshold = 1e6

    @staticmethod
    def _mask_gaps(data, mask):
        """
        Mask the gaps between sensors in the detector.

        :param data: a 2D numpy array
        :param mask: a 2D numpy array of the same shape as data
        :return:

         - the masked data
         - the updated mask

        """
        if not isinstance(data, np.ndarray):
            raise TypeError("data should be a numpy array")
        if not isinstance(mask, np.ndarray):
            raise TypeError("mask should be a numpy array")
        if data.ndim != 2:
            raise ValueError("data should be a 2D array")
        if mask.ndim != data.ndim:
            raise ValueError(
                "mask and data must have the same shape"
                f"mask is {mask.shape} while data is {data.shape}"
            )
        data[:, 255:261] = 0
        data[255:261, :] = 0

        mask[:, 255:261] = 1
        mask[255:261, :] = 1
        return data, mask

    @property
    def unbinned_pixel_number(self):
        """
        Define the number of pixels of the unbinned detector.

        Convention: (vertical, horizontal)
        """
        return 516, 516

    @property
    def unbinned_pixel_size(self):
        """Pixel size (vertical, horizontal) of the unbinned detector in meters."""
        return 55e-06, 55e-06


class Eiger2M(Detector):
    """Implementation of the Eiger2M detector."""

    def __init__(self, name, **kwargs):
        super().__init__(name=name, **kwargs)
        self._counter_table = {"ID01": "ei2minr"}  # useful if the same type of detector
        # is used at several beamlines
        self.saturation_threshold = 1e6

    @staticmethod
    def _mask_gaps(data, mask):
        """
        Mask the gaps between sensors in the detector.

        :param data: a 2D numpy array
        :param mask: a 2D numpy array of the same shape as data
        :return:

         - the masked data
         - the updated mask

        """
        if not isinstance(data, np.ndarray):
            raise TypeError("data should be a numpy array")
        if not isinstance(mask, np.ndarray):
            raise TypeError("mask should be a numpy array")
        if data.ndim != 2:
            raise ValueError("data should be a 2D array")
        if mask.ndim != data.ndim:
            raise ValueError(
                "mask and data must have the same shape"
                f"mask is {mask.shape} while data is {data.shape}"
            )
        data[:, 255:259] = 0
        data[:, 513:517] = 0
        data[:, 771:775] = 0
        data[0:257, 72:80] = 0
        data[255:259, :] = 0
        data[511:552, :0] = 0
        data[804:809, :] = 0
        data[1061:1102, :] = 0
        data[1355:1359, :] = 0
        data[1611:1652, :] = 0
        data[1905:1909, :] = 0
        data[1248:1290, 478] = 0
        data[1214:1298, 481] = 0
        data[1649:1910, 620:628] = 0

        mask[:, 255:259] = 1
        mask[:, 513:517] = 1
        mask[:, 771:775] = 1
        mask[0:257, 72:80] = 1
        mask[255:259, :] = 1
        mask[511:552, :] = 1
        mask[804:809, :] = 1
        mask[1061:1102, :] = 1
        mask[1355:1359, :] = 1
        mask[1611:1652, :] = 1
        mask[1905:1909, :] = 1
        mask[1248:1290, 478] = 1
        mask[1214:1298, 481] = 1
        mask[1649:1910, 620:628] = 1
        return data, mask

    @property
    def unbinned_pixel_number(self):
        """
        Define the number of pixels of the unbinned detector.

        Convention: (vertical, horizontal)
        """
        return 2164, 1030

    @property
    def unbinned_pixel_size(self):
        """Pixel size (vertical, horizontal) of the unbinned detector in meters."""
        return 75e-06, 75e-06


class Eiger4M(Detector):
    """Implementation of the Eiger4M detector."""

    def __init__(self, name, **kwargs):
        super().__init__(name=name, **kwargs)
        self.saturation_threshold = 4000000000

    @staticmethod
    def _mask_gaps(data, mask):
        """
        Mask the gaps between sensors in the detector.

        :param data: a 2D numpy array
        :param mask: a 2D numpy array of the same shape as data
        :return:

         - the masked data
         - the updated mask

        """
        if not isinstance(data, np.ndarray):
            raise TypeError("data should be a numpy array")
        if not isinstance(mask, np.ndarray):
            raise TypeError("mask should be a numpy array")
        if data.ndim != 2:
            raise ValueError("data should be a 2D array")
        if mask.ndim != data.ndim:
            raise ValueError(
                "mask and data must have the same shape"
                f"mask is {mask.shape} while data is {data.shape}"
            )
        data[:, 0:1] = 0
        data[:, -1:] = 0
        data[0:1, :] = 0
        data[-1:, :] = 0
        data[:, 1029:1041] = 0
        data[513:552, :] = 0
        data[1064:1103, :] = 0
        data[1615:1654, :] = 0

        mask[:, 0:1] = 1
        mask[:, -1:] = 1
        mask[0:1, :] = 1
        mask[-1:, :] = 1
        mask[:, 1029:1041] = 1
        mask[513:552, :] = 1
        mask[1064:1103, :] = 1
        mask[1615:1654, :] = 1
        return data, mask

    @property
    def unbinned_pixel_number(self):
        """
        Define the number of pixels of the unbinned detector.

        Convention: (vertical, horizontal)
        """
        return 2167, 2070

    @property
    def unbinned_pixel_size(self):
        """Pixel size (vertical, horizontal) of the unbinned detector in meters."""
        return 75e-06, 75e-06


class Timepix(Detector):
    """Implementation of the Timepix detector."""

    def __init__(self, name, **kwargs):
        super().__init__(name=name, **kwargs)

    @property
    def unbinned_pixel_number(self):
        """
        Define the number of pixels of the unbinned detector.

        Convention: (vertical, horizontal)
        """
        return 256, 256

    @property
    def unbinned_pixel_size(self):
        """Pixel size (vertical, horizontal) of the unbinned detector in meters."""
        return 55e-06, 55e-06


class Merlin(Detector):
    """Implementation of the Merlin detector."""

    def __init__(self, name, **kwargs):
        super().__init__(name=name, **kwargs)
        self.saturation_threshold = 1e6

    @staticmethod
    def _mask_gaps(data, mask):
        """
        Mask the gaps between sensors in the detector.

        :param data: a 2D numpy array
        :param mask: a 2D numpy array of the same shape as data
        :return:

         - the masked data
         - the updated mask

        """
        if not isinstance(data, np.ndarray):
            raise TypeError("data should be a numpy array")
        if not isinstance(mask, np.ndarray):
            raise TypeError("mask should be a numpy array")
        if data.ndim != 2:
            raise ValueError("data should be a 2D array")
        if mask.ndim != data.ndim:
            raise ValueError(
                "mask and data must have the same shape"
                f"mask is {mask.shape} while data is {data.shape}"
            )
        data[:, 255:260] = 0
        data[255:260, :] = 0

        mask[:, 255:260] = 1
        mask[255:260, :] = 1
        return data, mask

    @property
    def unbinned_pixel_number(self):
        """
        Define the number of pixels of the unbinned detector.

        Convention: (vertical, horizontal)
        """
        return 515, 515

    @property
    def unbinned_pixel_size(self):
        """Pixel size (vertical, horizontal) of the unbinned detector in meters."""
        return 55e-06, 55e-06


class Dummy(Detector):
    """
    Implementation of the Dummy detector.

    :param kwargs:
     - 'custom_pixelnumber': (V, H) number of pixels of the unbinned dummy detector, as
       a tuple of two positive integers.
     - 'custom_pixelsize': float, pixel size of the dummy detector in m.

    """

    def __init__(self, name, **kwargs):

        self.custom_pixelsize = kwargs.get("custom_pixelsize")
        valid.valid_item(
            self.custom_pixelsize,
            allowed_types=Real,
            min_excluded=0,
            allow_none=True,
            name="custom_pixelsize",
        )
        self.custom_pixelnumber = kwargs.get("custom_pixelnumber")
        valid.valid_container(
            self.custom_pixelnumber,
            container_types=(list, tuple, np.ndarray),
            length=2,
            item_types=int,
            min_excluded=0,
            allow_none=True,
            name="custom_pixelnumber",
        )
        super().__init__(name=name, **kwargs)

    @property
    def unbinned_pixel_number(self):
        """
        Define the number of pixels of the unbinned detector.

        Convention: (vertical, horizontal)
        """
        if self.custom_pixelnumber is not None and all(
            val is not None for val in self.custom_pixelnumber
        ):
            return self.custom_pixelnumber
        print(f"Defaulting the pixel size to {516, 516}")
        return 516, 516

    @property
    def unbinned_pixel_size(self):
        """Pixel size (vertical, horizontal) of the unbinned detector in meters."""
        if self.custom_pixelsize is not None:
            return self.custom_pixelsize, self.custom_pixelsize
        print(f"Defaulting the pixel size to {55e-06, 55e-06}")
        return 55e-06, 55e-06