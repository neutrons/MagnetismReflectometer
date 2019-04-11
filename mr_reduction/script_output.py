import os
import time

import mantid
import mantid.simpleapi as api

from .settings import AR_OUT_DIR_TEMPLATE
from .reflectivity_output import quicknxs_scaling_factor

def write_reduction_script(matched_runs, scaling_factors, ipts):
    """
        Write a combined reduction script
    """
    script = "# Mantid version %s\n" % mantid.__version__
    script += "# Date: %s\n\n" % time.strftime(u"%Y-%m-%d %H:%M:%S")
    script += "from mantid.simpleapi import *\n\n"
    script += "# Dictionary of workspace names. Each entry is a list of cross-sections\n"
    script += "workspaces =  dict()\n"

    output_dir = AR_OUT_DIR_TEMPLATE % dict(ipts=ipts)
    for i, run in enumerate(matched_runs):
        file_path = os.path.join(output_dir, "REF_M_%s_partial.py" % run)
        if not os.path.isfile(file_path):
            api.logger.notice("Partial script doesn't exist: %s" % file_path)
            continue
        with open(file_path, 'r') as _fd:
            script += "# Run:%s\n" % run
            script += "scaling_factor = %s\n" % scaling_factors[i]
            script += _fd.read() + '\n'

    with open(os.path.join(output_dir, "REF_M_%s_combined.py" % matched_runs[0]), 'w') as fd:
        fd.write(script)

def write_tunable_reduction_script(matched_runs, scaling_factors, ipts):
    """
        Write a combined reduction script
    """
    script = "# Mantid version %s\n" % mantid.__version__
    script += "# Date: %s\n\n" % time.strftime(u"%Y-%m-%d %H:%M:%S")
    script += "from mantid.simpleapi import *\n\n"
    script += "# Dictionary of workspace names. Each entry is a list of cross-sections\n"
    script += "workspaces =  dict()\n"
    script += "parameters = dict()\n\n"

    output_dir = AR_OUT_DIR_TEMPLATE % dict(ipts=ipts)
    reduce_call = "\ndef reduce():\n"
    prepare_call = "def prepare():\n"
    for i, run in enumerate(matched_runs):
        file_path = os.path.join(output_dir, "REF_M_%s_partial.py" % run)
        if not os.path.isfile(file_path):
            api.logger.notice("Partial script doesn't exist: %s" % file_path)
            continue
        script += "\n# Run:%s\n" % run
        script += "parameters['r_%s'] = dict(sf_%s = %s)\n" % (run, run, scaling_factors[i])
        _script = generate_split_script(run, file_path)
        script += _script + "\n"
        reduce_call += "    reduce_%s()\n" % run
        prepare_call += "    prepare_%s()\n" % run

    script += prepare_call
    script += reduce_call
    with open(os.path.join(output_dir, "REF_M_%s_tunable_combined.py" % matched_runs[0]), 'w') as fd:
        fd.write(script)

def write_partial_script(ws_grp):
    script = generate_script_from_ws(ws_grp)
    ipts = ws_grp[0].getRun().getProperty("experiment_identifier").value
    run_number = ws_grp[0].getRunNumber()
    output_dir = AR_OUT_DIR_TEMPLATE % dict(ipts=ipts)
    with open(os.path.join(output_dir, "REF_M_%s_partial.py" % run_number), 'w') as fd:
        fd.write(script)

def generate_script_from_ws(ws_grp):
    if len(ws_grp) == 0:
        return "# No workspace was generated\n"
    ws_name = str(ws_grp)

    xs_list = [str(_ws) for _ws in ws_grp if not str(_ws).endswith('unfiltered')]
    script = "workspaces['%s'] = %s\n" % (ws_name, str(xs_list))

    script_text = api.GeneratePythonScript(ws_grp[0])
    # Skip the header
    lines = script_text.split('\n')
    script_text = '\n'.join(lines[4:])
    script += script_text.replace(', ', ',\n                                ')
    script += '\n'
    qnxs_scale = quicknxs_scaling_factor(ws_grp[0])
    # Scale correction for QuickNXS compatibility
    script += "scaling_factor *= %s\n" % qnxs_scale
    for item in xs_list:
        script += "Scale(InputWorkspace='%s', Operation='Multiply',\n" % str(item)
        script += "      Factor=scaling_factor, OutputWorkspace='%s')\n\n" % str(item)

    return script

def generate_split_script(run_number, partial_script_path):
    """
        Split a reduction script into two parts: one to set up the
        parameters and one to execute the reduction.
        :param int or str run_number: run number
        :param str partial_script_path: path to partial script
        :param float scaling_factor: scaling factor for this run
    """
    red_script = 'def prepare_%s():\n' % run_number
    scale_script = ''

    with open(partial_script_path, 'r') as fd:
        _script_started = False
        _scale_started = False
        _first_line = True
        for line in fd.readlines():
            if line.startswith("MagnetismReflectometryRed"):
                _script_started = True
            elif line.startswith("Scale"):
                _scale_started = True

            if _script_started:
                if _first_line:
                    red_script += '    ' + line
                    _first_line = False
                else:
                    red_script += '                        ' + line.strip() + '\n'
                if line.endswith(')\n'):
                    _script_started = False
            elif _scale_started:
                scale_script += '    ' + line.replace('scaling_factor',
                                                      'parameters["r_%s"]["sf_%s"]' % (run_number, run_number))
            else:
                red_script += '    ' + line.replace('scaling_factor',
                                                    'parameters["r_%s"]["sf_%s"]' % (run_number, run_number))

    red_script = red_script.replace('MagnetismReflectometryReduction', 'params_%s = dict' % run_number)
    red_script = red_script.replace('wsg', 'wsg_%s' % run_number)
    red_script += '    parameters["r_%s"]["params"] = params_%s\n' % (run_number, run_number)

    red_script += '\ndef reduce_%s():\n' % run_number
    red_script += '    MagnetismReflectometryReduction(**parameters["r_%s"]["params"])\n' % run_number
    red_script += scale_script

    return red_script
