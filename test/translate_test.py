"""
    Simple script to run the automated reduction on a data file
"""
import sys
import os
import time
sys.path.append('..')
import mr_reduction.mr_translate as mr


PROCESS_ALL = False

if PROCESS_ALL:
    data_dir = '/SNS/REF_M/shared/ADARA.Test.Data.2018'
    for item in os.listdir(data_dir):
        if os.path.isfile(os.path.join(data_dir, item)) and item.endswith('nxs.h5'):
            print("\n%s\n" % item)
            t_0 = time.time()
            mr.translate(os.path.join(data_dir, item), histo=False, sub_dir='translation_output')
            print("%s: %s sec" % (item, time.time()-t_0))
else:
    mr.translate('/SNS/REF_M/shared/ADARA.Test.Data.v4.2018/nexus/REF_M_25636.nxs.h5',
                 histo=False, sub_dir='translation_output')
