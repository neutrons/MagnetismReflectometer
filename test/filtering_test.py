"""
    Simple script to run the automated reduction on a data file
"""
from __future__ import (absolute_import, division, print_function)
import sys
sys.path.append('..')

import mr_reduction.mr_reduction as mr

data_dir = "/SNS/REF_M/shared/ADARA.Test.Data.2018/"

adara_file = data_dir+'REF_M_28142.nxs.h5'
trans_file = data_dir+'translation_output/REF_M_28142_event.nxs'
legacy_file = '/SNS/REF_M/IPTS-18659/0/28142/NeXus/REF_M_28142_event.nxs'

processor = mr.ReductionProcess(data_run=adara_file, output_dir='.')
processor.pol_state = 'SF1'
processor.ana_state = 'SF2'
processor.pol_veto = ''
processor.ana_veto = ''
processor.reduce()