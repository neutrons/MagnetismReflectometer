#!/usr/bin/env python
import logging
import sys, os
import time
#sys.path.append("/opt/mantidnightly/bin")

import warnings
warnings.simplefilter('ignore', RuntimeWarning)

from mr_reduction import mr_reduction as refm
from mr_reduction import mr_translate

if __name__=="__main__":
    """
    Options:
        Use SANGLE:       True
        Use Const-Q:      False
        Fit peak in roi:  False
        Huber X cut:      1.0
        Use bck ROI:      False
        Force peak:       False [154, 178]
        Force background: False [150, 157]
        Use side bck:     False
        Bck width:        5

    Not used yet:
        Const-Q cutoff:   None
    """

    event_file_path=sys.argv[1]
    event_file = os.path.split(event_file_path)[-1]
    outdir=sys.argv[2]
    # The legacy format is REF_L_xyz_event.nxs
    # The new format is REF_L_xyz.nxs.h5
    run_number = event_file.split('_')[2]
    run_number = run_number.replace('.nxs.h5', '')
    red = refm.ReductionProcess(data_run=event_file_path,
                                output_dir=outdir,
                                use_sangle=True,
                                const_q_binning=False,
                                huber_x_cut=1.0,
                                const_q_cutoff=None,
                                update_peak_range=False,
                                use_roi_bck=False,
                                force_peak_roi=False, peak_roi=[154, 178],
                                force_bck_roi=False, bck_roi=[150, 157],
                                use_tight_bck=False, bck_offset=5)
    red.reduce()

    # Translate event data to legacy QuickNXS-compatible files.
    # mr_translate.translate(event_file_path, histo=False)
