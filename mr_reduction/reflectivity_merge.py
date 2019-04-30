#pylint: disable=bare-except, invalid-name, too-many-arguments
"""
    Merging tools for REF_M
"""
from __future__ import (absolute_import, division, print_function)
import sys
import os
import pytz
import json
import time
import datetime
import pandas
import numpy as np
import mantid
import mantid.simpleapi as api

from .settings import AR_OUT_DIR_TEMPLATE, DATA_DIR_TEMPLATE
from .script_output import write_reduction_script, write_tunable_reduction_script


def match_run_for_cross_section(run, ipts, cross_section):
    """
        Return a list of matching runs to be stitched

        @param run: run to start with
        @param ipts: experiment identifier
        @param cross_section: polarization entry
    """
    _previous_q_min = 0
    _previous_q_max = 0

    api.logger.notice("Matching for IPTS-%s r%s [%s]" % (ipts, run, cross_section))
    matched_runs = []
    for i in range(10):
        i_run = run - i
        output_dir = AR_OUT_DIR_TEMPLATE % dict(ipts=ipts)
        file_path = os.path.join(output_dir, "REF_M_%s_%s_autoreduce.dat" % (i_run, cross_section))
        if os.path.isfile(file_path):
            ref_data = pandas.read_csv(file_path, delim_whitespace=True,
                                       comment='#', names=['q','r','dr','dq', 'a'])
            q_min = min(ref_data['q'])
            q_max = max(ref_data['q'])
            api.logger.notice("%s: [%s %s]" % (i_run, q_min, q_max))

            if (q_max < _previous_q_max and q_max > _previous_q_min ) or _previous_q_max == 0:
                _previous_q_max = q_max
                _previous_q_min = q_min
                matched_runs.insert(0, str(i_run))
            else:
                # The series stops here
                break
    return matched_runs

def _extract_sequence_id(file_path):
    """
        Extract the sequence id from a data file
        @param str file_path: file to process
    """
    run_number = None
    group_id = None
    lowest_q = None
    if os.path.isfile(file_path):
        with open(file_path, 'r') as fd:
            for line in fd.readlines():
                if line.startswith("# sequence_id"):
                    try:
                        group_id = int(line[len("# sequence_id"):].strip())
                    except:
                        api.logger.error("Could not extract group id from line: %s" % line)
                if line.startswith("# Input file indices:"):
                    try:
                        run_number = int(line[len("# Input file indices:"):].strip())
                    except:
                        api.logger.error("Could not extract run number from line: %s" % line)
                if not line.startswith("#") and len(line.strip()) > 0:
                    try:
                        toks = line.split()
                        lowest_q = float(toks[0])
                    except:
                        api.logger.error("Could not extract lowest q from line: %s" % line)
                if run_number is not None and group_id is not None and lowest_q is not None:
                    return run_number, group_id, lowest_q
    return run_number, group_id, lowest_q

def match_run_with_sequence(run, ipts, cross_section):
    """
        Return a list of matching runs to be stitched

        #TODO: order the runs wth increasing Q.

        @param run: run to start with
        @param ipts: experiment identifier
        @param cross_section: polarization entry
    """
    api.logger.notice("Matching sequence for IPTS-%s r%s [%s]" % (ipts, run, cross_section))
    data_dir = AR_OUT_DIR_TEMPLATE % dict(ipts=ipts)

    # Check to see if we have the sequence information
    file_path = os.path.join(data_dir, "REF_M_%s_%s_autoreduce.dat" % (run, cross_section))
    _, group_id, _ = _extract_sequence_id(file_path)

    # If we don't have a group id, just group together runs of increasing q-values
    if group_id is None:
        return match_run_for_cross_section(run, ipts, cross_section)

    # Start with the run matching the sequence id
    matched_runs = []
    _lowest_q_available = True
    for item in os.listdir(data_dir):
        if item.endswith("%s_autoreduce.dat" % cross_section):
            _run, _group_id, lowest_q = _extract_sequence_id(os.path.join(data_dir, item))
            if _group_id == group_id:
                matched_runs.append([str(_run), lowest_q])
                _lowest_q_available = _lowest_q_available and lowest_q is not None
    if _lowest_q_available:
        match_series = [item[0] for item in sorted(matched_runs, key=lambda a:a[1])]
        return match_series
    return sorted(matched_runs)

def compute_scaling_factors(matched_runs, ipts, cross_section):
    _previous_ws = None
    running_scale = 1.0
    data_buffer = ""
    direct_beam_info = ""
    data_info = ""
    _cross_section_label = cross_section

    direct_beam_count = 0
    run_count = 0
    scaling_factors = [1.0]

    for i_run in matched_runs:
        output_dir = AR_OUT_DIR_TEMPLATE % dict(ipts=ipts)
        file_path = os.path.join(output_dir, "REF_M_%s_%s_autoreduce.dat" % (i_run, cross_section))
        if os.path.isfile(file_path):
            _run_info = open(file_path, 'r')
            ref_data = pandas.read_csv(_run_info,
                                       delim_whitespace=True, comment='#', names=['q','r','dr','dq', 'a'])

            ws = api.CreateWorkspace(DataX=ref_data['q'], DataY=ref_data['r'], DataE=ref_data['dr'])
            ws = api.ConvertToHistogram(ws)
            if _previous_ws is not None:
                _, scale = api.Stitch1D(_previous_ws, ws)
                running_scale *= scale
                scaling_factors.append(running_scale)
            _previous_ws = api.CloneWorkspace(ws)

            # Rewind and get meta-data
            _run_info.seek(0)
            _direct_beams_started = 0
            _data_runs_started = 0
            for line in _run_info.readlines():
                # Look for cross-section label
                if line.find("Extracted states:") > 0:
                    toks = line.split(':')
                    if len(toks) > 1:
                        _cross_section_label = toks[1].strip()

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

    return scaling_factors, direct_beam_info, data_info, data_buffer, _cross_section_label

def apply_scaling_factors(matched_runs, ipts, cross_section, scaling_factors):
    data_buffers = []
    for xs in ['Off_Off', 'On_Off', 'Off_On', 'On_On']:
        # Skip the cross section that we computed the scaling factors with
        # since we havce that data already
        if xs == cross_section:
            continue
        data_buffer = ""

        for j, i_run in enumerate(matched_runs):
            output_dir = AR_OUT_DIR_TEMPLATE % dict(ipts=ipts)
            file_path = os.path.join(output_dir, "REF_M_%s_%s_autoreduce.dat" % (i_run, xs))
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
        output_dir = AR_OUT_DIR_TEMPLATE % dict(ipts=ipts)
        file_path = os.path.join(output_dir, "REF_M_%s_%s_autoreduce.dat" % (run, xs))
        if os.path.isfile(file_path):
            api.logger.notice("Found: %s" % file_path)
            ref_data = pandas.read_csv(file_path,
                                       delim_whitespace=True, comment='#', names=['q','r','dr','dq', 'a'])
            relative_error = np.sum(ref_data['dr'] * ref_data['dr']) / np.sum(ref_data['r'])
            if best_xs is None or relative_error < best_error:
                best_xs = xs
                best_error = relative_error
        else:
            api.logger.notice("NOT found: %s" % file_path)
    return best_xs

def write_reflectivity_cross_section(run, ipts, cross_section, matched_runs, direct_beam_info, data_info, data_buffer, xs_label):
    direct_beam_options=['DB_ID', 'P0', 'PN', 'x_pos', 'x_width', 'y_pos', 'y_width',
                         'bg_pos', 'bg_width', 'dpix', 'tth', 'number', 'File']
    dataset_options=['scale', 'P0', 'PN', 'x_pos', 'x_width', 'y_pos', 'y_width',
                     'bg_pos', 'bg_width', 'fan', 'dpix', 'tth', 'number', 'DB_ID', 'File']

    output_dir = AR_OUT_DIR_TEMPLATE % dict(ipts=ipts)
    file_path = os.path.join(output_dir, "REF_M_%s_%s_combined.dat" % (run, cross_section))
    fd = open(file_path, 'w')
    fd.write("# Datafile created by QuickNXS 1.0.32\n")
    fd.write("# Datafile created by Mantid %s\n" % mantid.__version__)
    fd.write("# Date: %s\n" % time.strftime(u"%Y-%m-%d %H:%M:%S"))
    fd.write("# Type: Specular\n")
    fd.write("# Input file indices: %s\n" % ','.join(matched_runs))
    fd.write("# Extracted states: %s\n" % xs_label)
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
    return file_path

def plot_combined(matched_runs, scaling_factors, ipts, publish=True):
    data_names = []
    data_list = []
    for i, run in enumerate(matched_runs):
        for xs in ['Off_Off', 'On_Off', 'Off_On', 'On_On']:
            output_dir = AR_OUT_DIR_TEMPLATE % dict(ipts=ipts)
            file_path = os.path.join(output_dir, "REF_M_%s_%s_autoreduce.dat" % (run, xs))
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
                          x_title=u"Q (1/A)", x_log=True,
                          y_title="Reflectivity", y_log=True, show_dx=False, publish=publish)
        else:
            api.logger.notice("Nothing to plot")
    except:
        api.logger.error(str(sys.exc_value))
        api.logger.error("No publisher module found")
    return None

def combined_curves(run, ipts):
    """
        Produce combined R(q)
    """
    # Select the cross section with the best statistics
    high_stat_xs = select_cross_section(run, ipts)
    api.logger.notice("High xs: %s" % high_stat_xs)

    # Match the given run with previous runs if they are overlapping in Q
    matched_runs = match_run_with_sequence(run, ipts, high_stat_xs)
    api.logger.notice("Matched runs: %s" % str(matched_runs))

    # Compute scaling factors for this cross section
    try:
        scaling_factors, direct_beam_info, data_info, data_buffer, xs_label = compute_scaling_factors(matched_runs, ipts, high_stat_xs)
    except:
        return [str(run),], [1.0,]

    # Write combined python script
    write_reduction_script(matched_runs, scaling_factors, ipts)
    write_tunable_reduction_script(matched_runs, scaling_factors, ipts)

    xs_buffers = apply_scaling_factors(matched_runs, ipts, high_stat_xs, scaling_factors)
    xs_buffers.append((high_stat_xs, data_buffer))

    file_list = []
    for item in xs_buffers:
        if item[1]:
            _file_path = write_reflectivity_cross_section(matched_runs[0], ipts, item[0],
                                                          matched_runs, direct_beam_info,
                                                          data_info, item[1], xs_label)
            file_list.append(_file_path)

    return matched_runs, scaling_factors, file_list

def combined_catalog_info(matched_runs, ipts, output_files, run_number=None):
    """
        Produce cataloging information for reduced data
        :param list matched_runs: list of matched runs
        :param str ipts: experiment name
        :param list output_files: list of output files for this reduction process
        :param str run_number: run number we want to associate this reduction with
    """
    NEW_YORK_TZ = pytz.timezone('America/New_York')
    info = dict(user='auto',
                created=NEW_YORK_TZ.localize(datetime.datetime.now()).isoformat(),
                metadata=dict())

    # List of input files
    input_list = []
    for item in matched_runs:
        data_dir = DATA_DIR_TEMPLATE % dict(ipts=ipts)
        data_file = os.path.join(data_dir, 'REF_M_%s.nxs.h5' % item)
        if os.path.isfile(data_file):
            input_list.append(dict(location=data_file,
                                   type='raw',
                                   purpose='sample-data'))
    info['input_files'] = input_list

    # List of output files
    output_list = []
    for item in output_files:
        output_list.append(dict(location=item,
                                type='processed',
                                purpose='reduced-data',
                                fields=dict()))
    info['output_files'] = output_list

    output_dir = AR_OUT_DIR_TEMPLATE % dict(ipts=ipts)
    if run_number is None:
        run_number = matched_runs[0]
    json_path = os.path.join(output_dir, "REF_M_%s.json" % run_number)
    with open(json_path, 'w') as fd:
        fd.write(json.dumps(info, indent=4))
    return json_path
