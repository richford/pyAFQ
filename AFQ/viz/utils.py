from collections import OrderedDict
import os.path as op
import logging
import tempfile

import numpy as np
import pandas as pd
from palettable.tableau import Tableau_20
import imageio as io
import IPython.display as display
import matplotlib.pyplot as plt

import nibabel as nib
from dipy.io.streamline import load_tractogram
from dipy.tracking.utils import transform_tracking_output
from dipy.io.stateful_tractogram import StatefulTractogram, Space

import AFQ.utils.volume as auv
import AFQ.registration as reg

__all__ = ["Viz", "visualize_tract_profiles", "visualize_gif_inline"]

viz_logger = logging.getLogger("AFQ.viz")
tableau_20_rgb = np.array(Tableau_20.colors) / 255 - 0.0001

COLOR_DICT = OrderedDict({"ATR_L": tableau_20_rgb[0],
                          "ATR_R": tableau_20_rgb[1],
                          "CST_L": tableau_20_rgb[2],
                          "CST_R": tableau_20_rgb[3],
                          "CGC_L": tableau_20_rgb[4],
                          "CGC_R": tableau_20_rgb[5],
                          "HCC_L": tableau_20_rgb[6],
                          "HCC_R": tableau_20_rgb[7],
                          "FP": tableau_20_rgb[8],
                          "FA": tableau_20_rgb[9],
                          "IFO_L": tableau_20_rgb[10],
                          "IFO_R": tableau_20_rgb[11],
                          "ILF_L": tableau_20_rgb[12],
                          "ILF_R": tableau_20_rgb[13],
                          "SLF_L": tableau_20_rgb[14],
                          "SLF_R": tableau_20_rgb[15],
                          "UNC_L": tableau_20_rgb[16],
                          "UNC_R": tableau_20_rgb[17],
                          "ARC_L": tableau_20_rgb[18],
                          "ARC_R": tableau_20_rgb[19]})

POSITIONS = OrderedDict({"ATR_L": (1, 0), "ATR_R": (1, 4),
                         "CST_L": (1, 1), "CST_R": (1, 3),
                         "CGC_L": (3, 1), "CGC_R": (3, 3),
                         "FP": (4, 2), "FA": (0, 2),
                         "IFO_L": (4, 1), "IFO_R": (4, 3),
                         "ILF_L": (3, 0), "ILF_R": (3, 4),
                         "SLF_L": (2, 1), "SLF_R": (2, 3),
                         "ARC_L": (2, 0), "ARC_R": (2, 4),
                         "UNC_L": (0, 1), "UNC_R": (0, 3)})

MAT_2_PYTHON = OrderedDict(
    {'Right Corticospinal': 'CST_R', 'Left Corticospinal': 'CST_L',
     'Right Uncinate': 'UNC_R', 'Left Uncinate': 'UNC_L',
     'Left IFOF': 'IFO_L', 'Right IFOF': 'IFO_R',
     'Right Arcuate': 'ARC_R', 'Left Arcuate': 'ARC_L',
     'Right Thalamic Radiation': 'ATR_R', 'Left Thalamic Radiation': 'ATR_L',
     'Right Cingulum Cingulate': 'CGC_R', 'Left Cingulum Cingulate': 'CGC_L',
     'Right Cingulum Hippocampus': 'HCC_R',
     'Left Cingulum Hippocampus': 'HCC_L',
     'Callosum Forceps Major': 'FP', 'Callosum Forceps Minor': 'FA',
     'Right ILF': 'ILF_R', 'Left ILF': 'ILF_L',
     'Right SLF': 'SLF_R', 'Left SLF': 'SLF_L'})


def viz_import_msg_error(module):
    """Alerts user to install the appropriate viz module """
    msg = f"To use {module.upper()} visualizations in pyAFQ, you will need "
    msg += f"to have {module.upper()} installed. "
    msg += f"You can do that by installing pyAFQ with "
    msg += f"`pip install AFQ[{module.lower()}]`, or by "
    msg += f"separately installing {module.upper()}: "
    msg += f"`pip install {module.lower()}`."
    return msg


def bundle_selector(bundle_dict, colors, b):
    """
    Selects bundle and color
    from the given bundle dictionary and color informaiton
    Helper function

    Parameters
    ----------
    bundle_dict : dict, optional
        Keys are names of bundles and values are dicts that should include
        a key `'uid'` with values as integers for selection from the trk
        metadata. Default: bundles are either not identified, or identified
        only as unique integers in the metadata.

    bundle : str or int, optional
        The name of a bundle to select from among the keys in `bundle_dict`
        or an integer for selection from the trk metadata.

    colors : dict or list
        If this is a dict, keys are bundle names and values are RGB tuples.
        If this is a list, each item is an RGB tuple. Defaults to a list
        with Tableau 20 RGB values

    Returns
    -------
    RGB tuple and str
    """
    b_name = str(b)
    if bundle_dict is None:
        # We'll choose a color from a rotating list:
        if isinstance(colors, list):
            color = colors[np.mod(len(colors), int(b))]
        else:
            color_list = colors.values()
            color = color_list[np.mod(len(colors), int(b))]
    else:
        # We have a mapping from UIDs to bundle names:
        for b_name_iter, b_iter in bundle_dict.items():
            if b_iter['uid'] == b:
                b_name = b_name_iter
                break
        color = colors[b_name]
    return color, b_name


def tract_generator(sft, affine, bundle, bundle_dict, colors):
    """
    Generates bundles of streamlines from the tractogram.
    Only generates from relevant bundle if bundle is set.
    Uses bundle_dict and colors to assign colors if set.
    Otherwise, returns all streamlines.

    Helper function

    Parameters
    ----------
    sft : Stateful Tractogram, str
        A Stateful Tractogram containing streamline information
        or a path to a trk file

    affine : ndarray
       An affine transformation to apply to the streamlines.

    bundle : str or int
        The name of a bundle to select from among the keys in `bundle_dict`
        or an integer for selection from the trk metadata.

    bundle_dict : dict, optional
        Keys are names of bundles and values are dicts that should include
        a key `'uid'` with values as integers for selection from the sft
        metadata. Default: bundles are either not identified, or identified
        only as unique integers in the metadata.

    colors : dict or list
        If this is a dict, keys are bundle names and values are RGB tuples.
        If this is a list, each item is an RGB tuple. Defaults to a list
        with Tableau 20 RGB values

    Returns
    -------
    Statefule Tractogram streamlines, RGB numpy array, str
    """

    if isinstance(sft, str):
        viz_logger.info("Loading Stateful Tractogram...")
        sft = load_tractogram(sft, 'same', Space.VOX, bbox_valid_check=False)

    if affine is not None:
        viz_logger.info("Transforming Stateful Tractogram...")
        sft = StatefulTractogram.from_sft(
            transform_tracking_output(sft.streamlines, affine),
            sft,
            data_per_streamline=sft.data_per_streamline)

    streamlines = sft.streamlines
    viz_logger.info("Generating colorful lines from tractography...")

    if colors is None:
        # Use the color dict provided
        colors = COLOR_DICT

    if list(sft.data_per_streamline.keys()) == []:
        # There are no bundles in here:
        yield streamlines, [0.5, 0.5, 0.5], "all_bundles"

    else:
        # There are bundles:
        if bundle is None:
            # No selection: visualize all of them:

            for b in np.unique(sft.data_per_streamline['bundle']):
                idx = np.where(sft.data_per_streamline['bundle'] == b)[0]
                these_sls = streamlines[idx]
                color, b_name = bundle_selector(bundle_dict, colors, b)
                yield these_sls, color, b_name

        else:
            # Select just one to visualize:
            if isinstance(bundle, str):
                # We need to find the UID:
                uid = bundle_dict[bundle]['uid']
            else:
                # It's already a UID:
                uid = bundle

            idx = np.where(sft.data_per_streamline['bundle'] == uid)[0]
            these_sls = streamlines[idx]
            color, b_name = bundle_selector(bundle_dict, colors, uid)
            yield these_sls, color, b_name


def gif_from_pngs(tdir, gif_fname, n_frames,
                  png_fname="tgif", add_zeros=False):
    """
        Helper function
        Stitches together gif from screenshots
    """
    if add_zeros:
        fname_suffix10 = "00000"
        fname_suffix100 = "0000"
        fname_suffix1000 = "000"
    else:
        fname_suffix10 = ""
        fname_suffix100 = ""
        fname_suffix1000 = ""
    angles = []
    for i in range(n_frames):
        if i < 10:
            angle_fname = f"{png_fname}{fname_suffix10}{i}.png"
        elif i < 100:
            angle_fname = f"{png_fname}{fname_suffix100}{i}.png"
        else:
            angle_fname = f"{png_fname}{fname_suffix1000}{i}.png"
        angles.append(io.imread(op.join(tdir, angle_fname)))

    io.mimsave(gif_fname, angles)


def prepare_roi(roi, affine_or_mapping, static_img,
                roi_affine, static_affine, reg_template):
    """
    Load the ROI
    Possibly perform a transformation on an ROI
    Helper function

    Parameters
    ----------
    roi : str or Nifti1Image
        The ROI information.
        If str, ROI will be loaded using the str as a path.

    affine_or_mapping : ndarray, Nifti1Image, or str
       An affine transformation or mapping to apply to the ROI before
       visualization. Default: no transform.

    static_img: str or Nifti1Image
        Template to resample roi to.

    roi_affine: ndarray

    static_affine: ndarray

    reg_template: str or Nifti1Image
        Template to use for registration.

    Returns
    -------
    ndarray
    """
    viz_logger.info("Preparing ROI...")
    if not isinstance(roi, np.ndarray):
        if isinstance(roi, str):
            roi = nib.load(roi).get_fdata()
        else:
            roi = roi.get_fdata()

    if affine_or_mapping is not None:
        if isinstance(affine_or_mapping, np.ndarray):
            # This is an affine:
            if (static_img is None or roi_affine is None
                    or static_affine is None):
                raise ValueError("If using an affine to transform an ROI, "
                                 "need to also specify all of the following",
                                 "inputs: `static_img`, `roi_affine`, ",
                                 "`static_affine`")
            roi = reg.resample(roi, static_img, roi_affine, static_affine)
        else:
            # Assume it is  a mapping:
            if (isinstance(affine_or_mapping, str)
                    or isinstance(affine_or_mapping, nib.Nifti1Image)):
                if reg_template is None or static_img is None:
                    raise ValueError(
                        "If using a mapping to transform an ROI, need to ",
                        "also specify all of the following inputs: ",
                        "`reg_template`, `static_img`")
                affine_or_mapping = reg.read_mapping(affine_or_mapping,
                                                     static_img,
                                                     reg_template)

            roi = auv.patch_up_roi(affine_or_mapping.transform_inverse(
                                   roi,
                                   interpolation='nearest')).astype(bool)
    return roi


def load_volume(volume):
    """
    Load a volume
    Helper function

    Parameters
    ----------
    volume : ndarray or str
        3d volume to load.
        If string, it is used as a file path.
        If it is an ndarray, it is simply returned.

    Returns
    -------
    ndarray
    """
    viz_logger.info("Loading Volume...")
    if isinstance(volume, str):
        return nib.load(volume).get_fdata()
    else:
        return volume


class Viz:
    def __init__(self,
                 backend="fury"):
        """
        Set up visualization preferences.

        Parameters
        ----------
            backend : str, optional
                Should be either "fury" or "plotly".
                Default: "fury"
        """
        self.backend = backend
        if backend == "fury":
            try:
                import AFQ.viz.fury_backend
            except ImportError:
                raise ImportError(viz_import_msg_error("fury"))
            self.visualize_bundles = AFQ.viz.fury_backend.visualize_bundles
            self.visualize_roi = AFQ.viz.fury_backend.visualize_roi
            self.visualize_volume = AFQ.viz.fury_backend.visualize_volume
            self.create_gif = AFQ.viz.fury_backend.create_gif
        elif backend == "plotly":
            try:
                import AFQ.viz.plotly_backend
            except ImportError:
                raise ImportError(viz_import_msg_error("plotly"))
            self.visualize_bundles = AFQ.viz.plotly_backend.visualize_bundles
            self.visualize_roi = AFQ.viz.plotly_backend.visualize_roi
            self.visualize_volume = AFQ.viz.plotly_backend.visualize_volume
            self.create_gif = AFQ.viz.plotly_backend.create_gif


def visualize_tract_profiles(tract_profiles, scalar="dti_fa", min_fa=0.0,
                             max_fa=1.0, file_name=None, positions=POSITIONS):
    """
    Visualize all tract profiles for a scalar in one plot

    Parameters
    ----------
    tract_profiles : pandas dataframe
        Pandas dataframe of tract_profiles. For example,
        tract_profiles = pd.read_csv(my_afq.get_tract_profiles()[0])

    scalar : string, optional
       Scalar to use in plots. Default: "dti_fa".

    min_fa : float, optional
        Minimum FA used for y-axis bounds. Default: 0.0

    max_fa : float, optional
        Maximum FA used for y-axis bounds. Default: 1.0

    file_name : string, optional
        File name to save figure to if not None. Default: None

    positions : dictionary, optional
        Dictionary that maps bundle names to position in plot.
        Default: POSITIONS

    Returns
    -------
        Matplotlib figure and axes.
    """

    if (file_name is not None):
        plt.ioff()

    fig, axes = plt.subplots(5, 5)

    for bundle in positions.keys():
        ax = axes[positions[bundle][0], positions[bundle][1]]
        fa = tract_profiles[
            (tract_profiles["bundle"] == bundle)
        ][scalar].values
        ax.plot(fa, 'o-', color=COLOR_DICT[bundle])
        ax.set_ylim([min_fa, max_fa])
        ax.set_yticks([0.2, 0.4, 0.6])
        ax.set_yticklabels([0.2, 0.4, 0.6])
        ax.set_xticklabels([])

    fig.set_size_inches((12, 12))

    axes[0, 0].axis("off")
    axes[0, -1].axis("off")
    axes[1, 2].axis("off")
    axes[2, 2].axis("off")
    axes[3, 2].axis("off")
    axes[4, 0].axis("off")
    axes[4, 4].axis("off")

    if (file_name is not None):
        fig.savefig(file_name)
        plt.ion()

    return fig, axes


def compare_profiles_from_csv(csv_fnames, names, is_mats=False,
                              scalar="dti_fa", mat_scalar="fa",
                              min_scalar=0.0, max_scalar=1.0,
                              mat_scale=1.0,
                              file_name=None,
                              positions=POSITIONS,
                              mat_converter=MAT_2_PYTHON):
    """
    Compare all tract profiles for a scalar from two different CSVs.
    Plots tract profiles for both in one plot.
    Uses contrast index of profiles for comparison if only two CSVs provided.

    Parameters
    ----------
    csv_fnames : list of filenames
        Filenames for the two CSVs containing tract porfiles to compare.
        Will obtain subject list from the first file.

    names : list of strings
       Name to use to identify the data from the corresponding CSV.

    is_mats : bool or list of bools, optional
        Whether or not the csv was generated from Matlab AFQ or pyAFQ.
        Default: False

    scalar : string, optional
       Scalar to use in plots. Default: "dti_fa".

    mat_scalar : string, optional
        Corresponding mAFQ name for the scalar.

    min_scalar : float, optional
        Minimum value used for y-axis bounds. Default: 0.0

    max_scalar : float, optional
        Maximum value used for y-axis bounds. Default: 1.0

    mat_scale : float, optional
        Factor to scale the matlab data by if it is in different units than
        pyAFQ. Default: 1.0

    file_name : string, optional
        If not None, figures will be saved to this file name
        plus the subject ID. If only two CSVs are given,
        a contrast index will be calculated for each bundle / subject
        and saved to this filename plus '_contrast_index' as a csv.
        Default: None

    positions : dictionary, optional
        Dictionary that maps bundle names to position in plot.
        Default: POSITIONS

    mat_converter : dictionary, optional
        Dictionary that maps matlab bundle names to python bundle names.
        Default: MAT_2_PYTHON
    """
    if isinstance(is_mats, bool):
        is_mats = [is_mats] * len(csv_fnames)

    profiles = []
    for csv_filename in csv_fnames:
        profiles.append(pd.read_csv(csv_filename))

    for i, is_mat in enumerate(is_mats):
        profiles[i]['subjectID'] = \
            profiles[i]['subjectID'].apply(
                lambda x: int(
                    ''.join(c for c in x if c.isdigit())
                ) if isinstance(x, str) else x)
        if is_mat:
            profiles[i]['tractID'] = \
                profiles[i]['tractID'].apply(
                    lambda x: mat_converter[x])

    if (file_name is not None):
        plt.ioff()

    subjects = profiles[0]['subjectID'].unique()
    bundles = positions.keys()
    if len(csv_fnames) == 2:
        percent_diffs = pd.DataFrame(index=bundles, columns=subjects)
    for subject in subjects:
        fig, axes = plt.subplots(5, 5)
        plt.tight_layout()
        fig.set_size_inches((12, 12))
        fig.suptitle('Subject ' + str(subject))
        axes[0, 0].axis("off")
        axes[0, -1].axis("off")
        axes[1, 2].axis("off")
        axes[2, 2].axis("off")
        axes[3, 2].axis("off")
        axes[4, 0].axis("off")
        axes[4, 4].axis("off")
        for bundle in bundles:
            both_found = True
            ax = axes[positions[bundle][0], positions[bundle][1]]
            bundle_profiles = [None]*len(csv_fnames)
            for i, is_mat in enumerate(is_mats):
                if is_mat:
                    this_scalar = mat_scalar
                    this_bundle_col = 'tractID'
                    this_scale = mat_scale
                else:
                    this_scalar = scalar
                    this_bundle_col = 'bundle'
                    this_scale = 1.0
                bundle_profiles[i] = profiles[i][
                    (profiles[i]['subjectID'] == subject)
                    & (profiles[i][this_bundle_col] == bundle)
                ][this_scalar].to_numpy()[1:]*this_scale
            ax = axes[positions[bundle][0], positions[bundle][1]]
            for i, name in enumerate(names):
                if (len(bundle_profiles[i]) > 0):
                    ax.plot(bundle_profiles[i])
                else:
                    both_found = False
                    print(
                        'No streamlines found for subject '
                        + str(subject) + ' for bundle '
                        + bundle + ' for CSV ' + name)
            ax.set_title(bundle)
            ax.set_ylim([min_scalar, max_scalar])
            y_ticks = np.asarray([0.2, 0.4, 0.6])*max_scalar
            ax.set_yticks(y_ticks)
            ax.set_yticklabels(y_ticks)
            ax.set_xticklabels([])

            if len(csv_fnames) == 2 and both_found:
                percent_diffs.at[bundle, subject] = \
                    np.mean((bundle_profiles[0] - bundle_profiles[1])
                            / (bundle_profiles[0] + bundle_profiles[1]))

        fig.legend(names, loc='center')
        if (file_name is not None):
            fig.savefig(file_name + str(subject))
            plt.ion()

    percent_diffs.to_csv(file_name, index=False)


def visualize_gif_inline(fname, use_s3fs=False):
    """Display a gif inline, possible from s3fs """
    if use_s3fs:
        import s3fs
        fs = s3fs.S3FileSystem()
        tdir = tempfile.gettempdir()
        fname_remote = fname
        fname = op.join(tdir, "fig.gif")
        fs.get(fname_remote, fname)

    display.display(display.Image(fname))
