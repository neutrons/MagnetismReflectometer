#pylint: disable=too-many-locals, too-many-branches, invalid-name
"""
    Write reflectivity output file
"""
from __future__ import (absolute_import, division, print_function)
import math
import time
import mantid


def write_reflectivity(ws_list, output_path, cross_section):
    """
        Write out reflectivity output
    """
    # Sanity check
    if not ws_list:
        return

    direct_beam_options=['DB_ID', 'P0', 'PN', 'x_pos', 'x_width', 'y_pos', 'y_width',
                         'bg_pos', 'bg_width', 'dpix', 'tth', 'number', 'File']
    dataset_options=['scale', 'P0', 'PN', 'x_pos', 'x_width', 'y_pos', 'y_width',
                     'bg_pos', 'bg_width', 'fan', 'dpix', 'tth', 'number', 'DB_ID', 'File']
    cross_sections={'Off_Off': '++', 'On_Off': '-+', 'Off_On': '+-', 'On_On': '--'}
    pol_state = 'x'
    if cross_section in cross_sections:
        pol_state = cross_sections[cross_section]

    fd = open(output_path, 'w')
    fd.write("# Datafile created by QuickNXS 2.0.0\n")
    fd.write("# Datafile created by Mantid %s\n" % mantid.__version__)
    fd.write("# Autoreduced\n")
    fd.write("# Date: %s\n" % time.strftime(u"%Y-%m-%d %H:%M:%S"))
    fd.write("# Type: Specular\n")
    run_list = [str(ws.getRunNumber()) for ws in ws_list]
    fd.write("# Input file indices: %s\n" % ','.join(run_list))
    fd.write("# Extracted states: %s\n" % pol_state)
    fd.write("#\n")
    fd.write("# [Direct Beam Runs]\n")
    toks = ['%8s' % item for item in direct_beam_options]
    fd.write("# %s\n" % '  '.join(toks))

    # Direct beam section
    i_direct_beam = 0
    for ws in ws_list:
        i_direct_beam += 1
        run_object = ws.getRun()
        normalization_run = run_object.getProperty("normalization_run").value
        if normalization_run == "None":
            continue
        peak_min = run_object.getProperty("norm_peak_min").value
        peak_max = run_object.getProperty("norm_peak_max").value
        bg_min = run_object.getProperty("norm_bg_min").value
        bg_max = run_object.getProperty("norm_bg_max").value
        low_res_min = run_object.getProperty("norm_low_res_min").value
        low_res_max = run_object.getProperty("norm_low_res_max").value
        dpix = run_object.getProperty("normalization_dirpix").value
        filename = run_object.getProperty("normalization_file_path").value
        # In order to make the file loadable by QuickNXS, we have to change the
        # file name to the re-processed and legacy-compatible files.
        # The new QuickNXS can load both.
        if filename.endswith('nxs.h5'):
            filename = filename.replace('nexus', 'data')
            filename = filename.replace('.nxs.h5', '_histo.nxs')

        item = dict(DB_ID=i_direct_beam, tth=0, P0=0, PN=0,
                    x_pos=(peak_min+peak_max)/2.0,
                    x_width=peak_max-peak_min+1,
                    y_pos=(low_res_max+low_res_min)/2.0,
                    y_width=low_res_max-low_res_min+1,
                    bg_pos=(bg_min+bg_max)/2.0,
                    bg_width=bg_max-bg_min+1,
                    dpix=dpix,
                    number=normalization_run,
                    File=filename)

        par_list = ['{%s}' % p for p in direct_beam_options]
        template = "# %s\n" % '  '.join(par_list)
        _clean_dict = {}
        for key in item:
            if isinstance(item[key], (bool, str)):
                _clean_dict[key] = "%8s" % item[key]
            else:
                _clean_dict[key] = "%8g" % item[key]
        fd.write(template.format(**_clean_dict))

    # Scattering data
    fd.write("#\n")
    fd.write("# [Data Runs]\n")
    toks = ['%8s' % item for item in dataset_options]
    fd.write("# %s\n" % '  '.join(toks))
    i_direct_beam = 0

    data_block = ''
    for ws in ws_list:
        i_direct_beam += 1

        run_object = ws.getRun()
        peak_min = run_object.getProperty("scatt_peak_min").value
        peak_max = run_object.getProperty("scatt_peak_max").value
        bg_min = run_object.getProperty("scatt_bg_min").value
        bg_max = run_object.getProperty("scatt_bg_max").value
        low_res_min = run_object.getProperty("scatt_low_res_min").value
        low_res_max = run_object.getProperty("scatt_low_res_max").value
        dpix = run_object.getProperty("DIRPIX").getStatistics().mean
        # For live data, we might not have a file name
        if 'Filename' in run_object:
            filename = run_object.getProperty("Filename").value
            # In order to make the file loadable by QuickNXS, we have to change the
            # file name to the re-processed and legacy-compatible files.
            # The new QuickNXS can load both.
            if filename.endswith('nxs.h5'):
                filename = filename.replace('nexus', 'data')
                filename = filename.replace('.nxs.h5', '_histo.nxs')
        else:
            filename = "live data"
        constant_q_binning = run_object.getProperty("constant_q_binning").value
        scatt_pos = run_object.getProperty("specular_pixel").value
        norm_x_min = run_object.getProperty("norm_peak_min").value
        norm_x_max = run_object.getProperty("norm_peak_max").value
        norm_y_min = run_object.getProperty("norm_low_res_min").value
        norm_y_max = run_object.getProperty("norm_low_res_max").value

        # For some reason, the tth value that QuickNXS expects is offset.
        # It seems to be because that same offset is applied later in the QuickNXS calculation.
        # Correct tth here so that it can load properly in QuickNXS and produce the same result.
        tth = run_object.getProperty("two_theta").value
        det_distance = run_object['SampleDetDis'].getStatistics().mean
        # Check units
        if not run_object['SampleDetDis'].units in ['m', 'meter']:
            det_distance /= 1000.0
        direct_beam_pix = run_object['DIRPIX'].getStatistics().mean

        # Get pixel size from instrument properties
        if ws.getInstrument().hasParameter("pixel-width"):
            pixel_width = float(ws.getInstrument().getNumberParameter("pixel-width")[0]) / 1000.0
        else:
            pixel_width = 0.0007
        tth -= ((direct_beam_pix - scatt_pos) * pixel_width) / det_distance * 180.0 / math.pi

        item = dict(scale=1, DB_ID=i_direct_beam, P0=0, PN=0, tth=tth,
                    fan=constant_q_binning,
                    x_pos=scatt_pos,
                    x_width=peak_max-peak_min+1,
                    y_pos=(low_res_max+low_res_min)/2.0,
                    y_width=low_res_max-low_res_min+1,
                    bg_pos=(bg_min+bg_max)/2.0,
                    bg_width=bg_max-bg_min+1,
                    dpix=dpix,
                    number=str(ws.getRunNumber()),
                    File=filename)

        par_list = ['{%s}' % p for p in dataset_options]
        template = "# %s\n" % '  '.join(par_list)
        _clean_dict = {}
        for key in item:
            if isinstance(item[key], str):
                _clean_dict[key] = "%8s" % item[key]
            else:
                _clean_dict[key] = "%8g" % item[key]
        fd.write(template.format(**_clean_dict))

        x = ws.readX(0)
        y = ws.readY(0)
        dy = ws.readE(0)
        dx = ws.readDx(0)
        tth = ws.getRun().getProperty("SANGLE").getStatistics().mean * math.pi / 180.0
        quicknxs_scale = (float(norm_x_max)-float(norm_x_min)) * (float(norm_y_max)-float(norm_y_min))
        quicknxs_scale /= (float(peak_max)-float(peak_min)) * (float(low_res_max)-float(low_res_min))
        quicknxs_scale *= 0.005 / math.sin(tth)
        for i in range(len(x)):
            data_block += "%12.6g  %12.6g  %12.6g  %12.6g  %12.6g\n" % (x[i],
                                                                        y[i]*quicknxs_scale,
                                                                        dy[i]*quicknxs_scale,
                                                                        dx[i],
                                                                        tth)

    fd.write("#\n")
    fd.write("# [Global Options]\n")
    fd.write("# name           value\n")
    fd.write("# sample_length  10\n")
    fd.write("#\n")
    fd.write("# [Data]\n")
    toks = [u'%12s' % item for item in [u'Qz [1/A]', u'R [a.u.]', u'dR [a.u.]', u'dQz [1/A]', u'theta [rad]']]
    fd.write(u"# %s\n" % '  '.join(toks))
    fd.write(u"# %s\n" % data_block)

    fd.close()
