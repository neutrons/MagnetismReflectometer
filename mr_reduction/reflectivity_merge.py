#pylint: disable=bare-except, invalid-name, too-many-arguments
"""
    Merging tools for REF_M
"""
from __future__ import (absolute_import, division, print_function)
import sys
import time
import pandas
import numpy as np
import mantid
from mantid.simpleapi import *


def match_run_for_cross_section(run, ipts, cross_section):
    """
        Return a list of matching runs to be stitched

        @param run: run to start with
        @param ipts: experiment identifier
        @param cross_section: polarization entry
    """
    _previous_q_min = 0
    _previous_q_max = 0

    logger.notice("Matching for IPTS-%s r%s [%s]" % (ipts, run, cross_section))
    matched_runs = []
    for i in range(10):
        i_run = run - i
        file_path = "/SNS/REF_M/IPTS-%s/shared/autoreduce/REF_M_%s_%s_autoreduce.dat" % (ipts, i_run, cross_section)
        if os.path.isfile(file_path):
            ref_data = pandas.read_csv(file_path, delim_whitespace=True,
                                       comment='#', names=['q','r','dr','dq', 'a'])
            q_min = min(ref_data['q'])
            q_max = max(ref_data['q'])
            logger.notice("%s: [%s %s]" % (i_run, q_min, q_max))

            if (q_max < _previous_q_max and q_max > _previous_q_min ) or _previous_q_max == 0:
                _previous_q_max = q_max
                _previous_q_min = q_min
                matched_runs.insert(0, str(i_run))
            else:
                # The series stops here
                break
    return matched_runs

def compute_scaling_factors(matched_runs, ipts, cross_section):
    _previous_ws = None
    running_scale = 1.0
    data_buffer = ""
    direct_beam_info = ""
    data_info = ""

    direct_beam_count = 0
    run_count = 0
    scaling_factors = [1.0]

    for i_run in matched_runs:
        file_path = "/SNS/REF_M/IPTS-%s/shared/autoreduce/REF_M_%s_%s_autoreduce.dat" % (ipts, i_run, cross_section)
        if os.path.isfile(file_path):
            _run_info = open(file_path, 'r')
            ref_data = pandas.read_csv(_run_info,
                                       delim_whitespace=True, comment='#', names=['q','r','dr','dq', 'a'])

            ws = CreateWorkspace(DataX=ref_data['q'], DataY=ref_data['r'], DataE=ref_data['dr'])
            ws = ConvertToHistogram(ws)
            if _previous_ws is not None:
                _, scale = Stitch1D(_previous_ws, ws)
                running_scale *= scale
                scaling_factors.append(running_scale)
            _previous_ws = CloneWorkspace(ws)

            # Rewind and get meta-data
            _run_info.seek(0)
            _direct_beams_started = 0
            _data_runs_started = 0
            for line in _run_info.readlines():

                # If we are in the data run block, copy the data we need
                if _data_runs_started == 1 and line.find(str(i_run)) > 0:
                    toks = ["%8s" % t for t in line.split()]
                    if len(toks)>10:
                        toks[1] = "%8g" % scaling_factors[run_count]
                        run_count += 1
                        toks[14] = "%8s" % str(run_count)
                        _line = '  '.join(toks).strip() + '\n'
                        data_info += _line.replace("# ", "#")

                # Find out whether we started the direct beam block
                if line.find("Data Runs") > 0:
                    _direct_beams_started = 0
                    _data_runs_started = 1

                # Get the direct beam info
                if _direct_beams_started == 2:
                    toks = ["%8s" % t for t in line.split()]
                    if len(toks)>10:
                        direct_beam_count += 1
                        toks[1] = "%8g" % direct_beam_count
                        _line = '  '.join(toks).strip() + '\n'
                        direct_beam_info += _line.replace("# ", "#")

                # If we are in the direct beam block, we need to skip the column info line
                if _direct_beams_started == 1 and line.find("DB_ID") > 0:
                    _direct_beams_started = 2

                # Find out whether we started the direct beam block
                if line.find("Direct Beam Runs") > 0:
                    _direct_beams_started = 1

            for i in range(len(ref_data['q'])):
                data_buffer += "%12.6g  %12.6g  %12.6g  %12.6g  %12.6g\n" % (ref_data['q'][i],
                                                                             running_scale*ref_data['r'][i],
                                                                             running_scale*ref_data['dr'][i],
                                                                             ref_data['dq'][i],
                                                                             ref_data['a'][i],
                                                                            )

    return scaling_factors, direct_beam_info, data_info, data_buffer

def apply_scaling_factors(matched_runs, ipts, cross_section, scaling_factors):
    data_buffers = []
    for xs in ['Off_Off', 'On_Off', 'Off_On', 'On_On']:
        # Skip the cross section that we computed the scaling factors with
        # since we havce that data already
        if xs == cross_section:
            continue
        data_buffer = ""

        for j, i_run in enumerate(matched_runs):
            file_path = "/SNS/REF_M/IPTS-%s/shared/autoreduce/REF_M_%s_%s_autoreduce.dat" % (ipts, i_run, xs)
            if os.path.isfile(file_path):
                _run_info = open(file_path, 'r')
                ref_data = pandas.read_csv(_run_info,
                                           delim_whitespace=True, comment='#', names=['q','r','dr','dq', 'a'])

                for i in range(len(ref_data['q'])):
                    data_buffer += "%12.6g  %12.6g  %12.6g  %12.6g  %12.6g\n" % (ref_data['q'][i],
                                                                                 scaling_factors[j]*ref_data['r'][i],
                                                                                 scaling_factors[j]*ref_data['dr'][i],
                                                                                 ref_data['dq'][i],
                                                                                 ref_data['a'][i],
                                                                                )

        data_buffers.append((xs, data_buffer))
    return data_buffers

def select_cross_section(run, ipts):
    best_xs = None
    best_error = None

    for xs in ['Off_Off', 'On_Off', 'Off_On', 'On_On']:
        file_path = "/SNS/REF_M/IPTS-%s/shared/autoreduce/REF_M_%s_%s_autoreduce.dat" % (ipts, run, xs)
        if os.path.isfile(file_path):
            ref_data = pandas.read_csv(file_path,
                                       delim_whitespace=True, comment='#', names=['q','r','dr','dq', 'a'])
            relative_error = np.sum(ref_data['dr'] * ref_data['dr']) / np.sum(ref_data['r'])
            if best_xs is None or relative_error < best_error:
                best_xs = xs
                best_error = relative_error
    return best_xs

def write_reflectivity_cross_section(run, ipts, cross_section, matched_runs, direct_beam_info, data_info, data_buffer):
    direct_beam_options=['DB_ID', 'P0', 'PN', 'x_pos', 'x_width', 'y_pos', 'y_width',
                         'bg_pos', 'bg_width', 'dpix', 'tth', 'number', 'File']
    dataset_options=['scale', 'P0', 'PN', 'x_pos', 'x_width', 'y_pos', 'y_width',
                     'bg_pos', 'bg_width', 'fan', 'dpix', 'tth', 'number', 'DB_ID', 'File']
    cross_sections={'Off_Off': '++', 'On_Off': '-+', 'Off_On': '+-', 'On_On': '--'}

    pol_state = 'x'
    if cross_section in cross_sections:
        pol_state = cross_sections[cross_section]

    file_path = "/SNS/REF_M/IPTS-%s/shared/autoreduce/REF_M_%s_%s_combined.dat" % (ipts, run, cross_section)
    fd = open(file_path, 'w')
    fd.write("# Datafile created by QuickNXS 1.0.32\n")
    fd.write("# Datafile created by Mantid %s\n" % mantid.__version__)
    fd.write("# Date: %s\n" % time.strftime(u"%Y-%m-%d %H:%M:%S"))
    fd.write("# Type: Specular\n")
    fd.write("# Input file indices: %s\n" % ','.join(matched_runs))
    fd.write("# Extracted states: %s\n" % pol_state)
    fd.write("#\n")
    fd.write("# [Direct Beam Runs]\n")
    toks = ['%8s' % item for item in direct_beam_options]
    fd.write("# %s\n" % '  '.join(toks))
    fd.write(direct_beam_info)
    fd.write("#\n")
    fd.write("# [Data Runs]\n")
    toks = ['%8s' % item for item in dataset_options]
    fd.write("# %s\n" % '  '.join(toks))
    fd.write(data_info)
    fd.write("#\n")
    fd.write("# [Global Options]\n")
    fd.write("# name           value\n")
    fd.write("# sample_length  10\n")
    fd.write("#\n")
    fd.write("# [Data]\n")
    toks = [u'%12s' % item for item in [u'Qz [1/A]', u'R [a.u.]', u'dR [a.u.]', u'dQz [1/A]', u'theta [rad]']]
    fd.write(u"# %s\n" % '  '.join(toks))
    fd.write(data_buffer)
    fd.close()

def plot_combined(matched_runs, scaling_factors, ipts, publish=True):
    data_names = []
    data_list = []
    for i, run in enumerate(matched_runs):
        for xs in ['Off_Off', 'On_Off', 'Off_On', 'On_On']:
            file_path = "/SNS/REF_M/IPTS-%s/shared/autoreduce/REF_M_%s_%s_autoreduce.dat" % (ipts, run, xs)
            if os.path.isfile(file_path):
                ref_data = pandas.read_csv(file_path,
                                           delim_whitespace=True, comment='#', names=['q','r','dr','dq', 'a'])
                data_list.append([ref_data['q'], scaling_factors[i]*ref_data['r'], scaling_factors[i]*ref_data['dr']])
                data_names.append("r%s [%s]" % (run, xs))

    try:
        # Depending on where we run, we might get our publisher from
        # different places, or not at all.
        try: # version on autoreduce
            from postprocessing.publish_plot import plot1d
        except ImportError: # version on instrument computers
            from .web_report import plot1d
        if data_names:
            return plot1d(matched_runs[-1], data_list, data_names=data_names, instrument='REF_M',
                          x_title=u"Q (1/\u212b)", x_log=True,
                          y_title="Reflectivity", y_log=True, show_dx=False, publish=publish)
        else:
            logger.notice("Nothing to plot")
    except:
        logger.error(str(sys.exc_value))
        logger.error("No publisher module found")
    return None

def combined_curves(run, ipts):
    """
    """
    # Select the cross section with the best statistics
    high_stat_xs = select_cross_section(run, ipts)

    # Match the given run with previous runs if they are overlapping in Q
    matched_runs = match_run_for_cross_section(run, ipts, high_stat_xs)

    # Compute scaling factors for this cross section
    scaling_factors, direct_beam_info, data_info, data_buffer = compute_scaling_factors(matched_runs, ipts, high_stat_xs)

    xs_buffers = apply_scaling_factors(matched_runs, ipts, high_stat_xs, scaling_factors)
    xs_buffers.append((high_stat_xs, data_buffer))

    for item in xs_buffers:
        if item[1]:
            write_reflectivity_cross_section(matched_runs[0], ipts, item[0], matched_runs,
                                             direct_beam_info, data_info, item[1])

    return matched_runs, scaling_factors
