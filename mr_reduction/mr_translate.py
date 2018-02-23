#pylint: disable=line-too-long,unused-variable, exec-used
"""
    Translator to be used to process filtered event data and produce
    nexus files readable by QuickNXS.
    This translator will be part of the post-processing once REFM moves to Epics.

    For reference, these are the states recognized by QuickNXS

MAPPING_FULLPOL=(
                 (u'++', u'entry-Off_Off'),
                 (u'--', u'entry-On_On'),
                 (u'+-', u'entry-Off_On'),
                 (u'-+', u'entry-On_Off'),
                 )
MAPPING_HALFPOL=(
                 (u'+', u'entry-Off_Off'),
                 (u'-', u'entry-On_Off'),
                 )
MAPPING_UNPOL=(
               (u'x', u'entry-Off_Off'),
               )

    TODO: Use PolarizerLabel and AnalyzerLabel PVs to make sure Off is +
"""
from __future__ import (absolute_import, division, print_function)
import os
import nxs
from nxs import NXfield, NXgroup
import numpy as np
from . import mr_filter_events


def translate_entry(raw_event_file, filtered_file, entry_name, histo=True):
    """
        Create a nexus entry from a filtered data set
        :param str raw_event_file: name of the original event nexus file
        :param str filtered_file: Mantid processed event file (filtered)
        :param str entry_name: name of the entry to be created
    """
    # Read in processed file
    tree_processed = nxs.load(filtered_file, 'r')

    # Read in raw file
    tree_raw = nxs.load(raw_event_file)

    # Create a QuickNXS file
    nx_quick = create_structure(entry_name)

    # For testing purposes, the raw file may have the four cross-section
    # entries, so if that's the case we have to open the Off_Off entry
    entry_ = 'entry'
    if 'entry-Off_Off' in tree_raw.keys():
        entry_ = 'entry-Off_Off'

    nx_quick.start_time = tree_raw[entry_].start_time
    nx_quick.end_time = tree_raw[entry_].end_time

    # DAS logs
    for key, nx_object in tree_processed.NXentry[0].logs.items():
        item_out = key
        toks = key.split(':')
        if len(toks)>1:
            item_out = "%s_%s" % (toks[-2], toks[-1])

        if not hasattr(nx_object, 'value'):
            continue
        if isinstance(nx_object.value.dtype, str):
            continue

        exec("nx_quick.DASlogs.%s = NXgroup(name='%s', nxclass='NXlog')" % (item_out, item_out))
        log_value = nx_object.value.nxdata
        exec("nx_quick.DASlogs.%s.value = NXfield(name='value', dtype='float64', value=log_value)" % item_out)
        if hasattr(nx_object, 'time'):
            log_time = nx_object.time.nxdata
            exec("nx_quick.DASlogs.%s.time = NXfield(name='time', dtype='float64', value=log_time)" % item_out)

    # Proton charge from Mantid is in uAh. In the raw file it's pC.
    nx_quick.proton_charge = NXfield(name='proton_charge', dtype='float64',
                                     value=tree_processed.NXentry[0].logs.gd_prtn_chrg.value.nxdata/2.778e-10)

    nx_quick.duration = NXfield(name='duration', dtype='float64', value=tree_processed.NXentry[0].logs.duration.value.nxdata)

    # Instrument
    nx_quick.instrument.SNSgeometry_file_name = NXfield(name='SNSgeometry_file_name', value='')

    nx_quick.instrument.aperture1.distance = -2.599
    nx_quick.instrument.aperture2.distance = -2.019
    nx_quick.instrument.aperture3.distance = -0.714

    # Bank1 data
    nx_quick.instrument.bank1.origin = NXgroup(name='origin', nxclass='NXGroup')
    nx_quick.instrument.bank1.origin.shape = NXgroup(name='shape', nxclass='NXGroup')
    nx_quick.instrument.bank1.origin.shape.size = NXfield(name='size', value=[0.212800, 0.179200])
    
    nx_quick.experiment_identifier = tree_raw[entry_].experiment_identifier
    nx_quick.run_number = tree_raw[entry_].run_number
    
    nx_quick.SNSproblem_log_geom = NXgroup(name='SNSproblem_log_geom', nxclass='NXGroup')
    nx_quick.SNSproblem_log_geom.data = NXfield(name='data', value='')

    if histo:
        create_histo(tree_processed, nx_quick)
    else:
        create_events(tree_processed, nx_quick)

    if tree_processed.NXentry[0].logs.gd_prtn_chrg.value.nxdata>0:
        return create_links(nx_quick)
    else:
        return nx_quick

def create_histo(tree_processed, nx_quick):
    """
        Create a histogram file that can be read by QuickNXS
    """
    # Data input
    # Axis 1 are the TOF bins
    axis_1 = tree_processed.NXentry[0].workspace.axis1.nxdata

    # Axis 2 is for the pixels (304 x 256 = 77824)
    # axis_2 = tree_processed.NXentry[0].workspace.axis2.nxdata
    values = tree_processed.NXentry[0].workspace['values'].nxdata

    # Data output (304 x 256 x TOF bins)
    data = values.reshape([304, 256, values.shape[1]])

    nx_quick.instrument.bank1.data = NXfield(name='data', dtype='uint32',
                                             attrs=dict(axes='x_pixel_offset,y_pixel_offset,time_of_flight', signal=1), value=data)
    nx_quick.instrument.bank1.time_of_flight = NXfield(name='time_of_flight', dtype='float64', attrs=dict(axis=3, primary=1), value=axis_1)

    # Data integrated over TOF
    nx_quick.instrument.bank1.data_x_y = NXfield(name='data_x_y', dtype='uint32',
                                                              attrs=dict(axes='x_pixel_offset,y_pixel_offset', signal=2),
                                                              value=np.sum(data, axis=2))
    # X pixel data (304 x TOF bins)
    nx_quick.instrument.bank1.data_x_time_of_flight = NXfield(name='data_x_time_of_flight', dtype='uint32',
                                                              attrs=dict(axes='x_pixel_offset,time_of_flight', signal=3),
                                                              value=np.sum(data, axis=1))
    # Y pixel data (256 x TOF bins)
    nx_quick.instrument.bank1.data_y_time_of_flight = NXfield(name='data_y_time_of_flight', dtype='uint32',
                                                              attrs=dict(axes='y_pixel_offset,time_of_flight', signal=4),
                                                              value=np.sum(data, axis=0))
    # In the raw SNS nexus file, event_id is a pixel ID
    nx_quick.total_counts = NXfield(name='total_counts', dtype='uint64', value=np.sum(data))
    nx_quick.bank1.data = nx_quick.instrument.bank1.data
    nx_quick.bank1.data_x_time_of_flight = nx_quick.instrument.bank1.data_x_time_of_flight
    nx_quick.bank1.data_y_time_of_flight = nx_quick.instrument.bank1.data_y_time_of_flight
    nx_quick.bank1.time_of_flight = nx_quick.instrument.bank1.time_of_flight

def create_events(tree_processed, nx_quick):
    """
        Create an event file that can be read by QuickNXS
    """
    nx_quick.bank1_events = NXgroup(name='bank1_events', nxclass='NXevent_data')
    nx_quick.bank1_events.event_time_offset = NXfield(name='event_time_offset', dtype='float64',
                                                      value=tree_processed.NXentry[0].event_workspace.tof.nxdata)
    # The events are assigned to pixels through an array of indices in Mantid nexus files.
    # All the events for a given pixel are stored in a block in the tof array above.
    # The array indices in that block go from indices[i] to indices[i+1], where i is the ith pixel.
    indices = tree_processed.NXentry[0].event_workspace.indices.nxdata
    event_ids = []
    for i in range(len(indices)-1):
        n_events = int(indices[i+1]-indices[i])
        event_ids.extend(n_events*[i])

    # In the raw SNS nexus file, event_id is a pixel ID
    if len(event_ids) == 0:
        nx_quick.bank1_events.event_id =  NXfield(name='event_id', dtype='uint32', value=0)
    else:
        nx_quick.bank1_events.event_id =  NXfield(name='event_id', dtype='uint32', value=event_ids)
    nx_quick.total_counts = NXfield(name='total_counts', dtype='uint64', value=len(event_ids))
    # Empty detector counts
    nx_quick.instrument.bank1.data_x_y = NXfield(name='data_x_y', dtype='uint32',
                                                 attrs=dict(axes='x_pixel_offset,y_pixel_offset', signal=2),
                                                 value=np.zeros([304, 256], dtype='uint32'))

def create_structure(entry_name):
    """
        Create empty structure that we will fill out with data.
    """
    nx_quick = nxs.NXentry(name=entry_name)
    nx_quick.DASlogs = NXgroup(name='DASlogs', nxclass='NXcollection')
    nx_quick.sample = NXgroup(name='sample', nxclass='NXsample')
    nx_quick.bank1 = NXgroup(name='bank1', nxclass='NXdata')
    nx_quick.instrument = NXgroup(name='instrument', nxclass='NXinstrument')
    nx_quick.instrument.analyzer = NXgroup(name='analyzer', nxclass='NXpolarizer')
    nx_quick.instrument.polarizer = NXgroup(name='polarizer', nxclass='NXpolarizer')
    nx_quick.instrument.aperture1 = NXgroup(name='aperture1', nxclass='NXaperture')
    nx_quick.instrument.aperture2 = NXgroup(name='aperture2', nxclass='NXaperture')
    nx_quick.instrument.aperture3 = NXgroup(name='aperture3', nxclass='NXaperture')
    nx_quick.instrument.moderator = NXgroup(name='moderator', nxclass='NXmoderator')
    nx_quick.instrument.bank1 = NXgroup(name='bank1', nxclass='NXdetector')

    return nx_quick

def create_links(nx_quick):
    """
        Create internal links needed by QuickNXS
    """
    nx_quick.sample.SANGLE = nx_quick.DASlogs.SANGLE

    if "AnalyzerTrans" in nx_quick.DASlogs.keys():
        nx_quick.instrument.analyzer.AnalyzerTrans = nx_quick.DASlogs.AnalyzerTrans
    nx_quick.instrument.analyzer.AnalyzerLift = nx_quick.DASlogs.AnalyzerLift
    nx_quick.instrument.analyzer.AnalyzerRot = nx_quick.DASlogs.AnalyzerRot
    nx_quick.instrument.polarizer.PolLift = nx_quick.DASlogs.PolLift
    nx_quick.instrument.moderator.ModeratorSamDis = nx_quick.DASlogs.ModeratorSamDis
    nx_quick.instrument.aperture1.S1HWidth = nx_quick.DASlogs.S1HWidth
    nx_quick.instrument.aperture2.S2HWidth = nx_quick.DASlogs.S2HWidth
    nx_quick.instrument.aperture3.S3HWidth = nx_quick.DASlogs.S3HWidth

    nx_quick.instrument.bank1.total_counts = nx_quick.total_counts
    nx_quick.instrument.bank1.DANGLE = nx_quick.DASlogs.DANGLE
    nx_quick.instrument.bank1.DANGLE0 = nx_quick.DASlogs.DANGLE0
    nx_quick.instrument.bank1.DIRPIX = nx_quick.DASlogs.DIRPIX
    nx_quick.instrument.bank1.SampleDetDis = nx_quick.DASlogs.SampleDetDis

    #nx_quick.bank1.x_pixel_offset = nx_quick.instrument.bank1.x_pixel_offset
    #nx_quick.bank1.y_pixel_offset = nx_quick.instrument.bank1.y_pixel_offset
    nx_quick.bank1.data_x_y = nx_quick.instrument.bank1.data_x_y

    return nx_quick

def translate(raw_event_file, identifier='quick', events=True, histo=True, sub_dir=None):
    """
        Translate an event nexus file
        :param str raw_event_file: name of the event data file to process
        :param str identifier: suffix for the output data file
    """
    # Create a filtered file
    xs_event_files, xs_histo_files = mr_filter_events.filter_cross_sections(raw_event_file, events=events, histo=histo)
    print(xs_event_files)
    print(xs_histo_files)
    if events:
        process(raw_event_file, xs_event_files, histo=False, sub_dir=sub_dir)
    if histo:
        process(raw_event_file, xs_histo_files, histo=True, sub_dir=sub_dir)

def process(raw_event_file, filtered_files, histo=False, sub_dir=None, identifier='quicknxs'):
    # Assemble the entries
    tree = nxs.NXroot()
    for entry_name, filtered_file in filtered_files.items():
        if filtered_file is None:
            continue
        entry = translate_entry(raw_event_file, filtered_file , entry_name=entry_name, histo=histo)
        tree.insert(entry)

        if os.path.isfile(filtered_file):
            os.remove(filtered_file)

    # Create a name that QuickNXS will recognize
    if raw_event_file.endswith('_event.nxs'):
        if histo:
            output_file = raw_event_file.replace('_event.nxs', '_%s_histo.nxs' % identifier)
        else:
            output_file = raw_event_file.replace('_event.nxs', '_%s_event.nxs' % identifier)
    elif raw_event_file.endswith('.nxs.h5'):
        if histo:
            output_file = raw_event_file.replace('.nxs.h5', '_histo.nxs')
        else:
            output_file = raw_event_file.replace('.nxs.h5', '_event.nxs')

    if sub_dir is not None:
        dir_, file_ = os.path.split(output_file)
        output_file = os.path.join(dir_, sub_dir, file_)

    if os.path.isfile(output_file):
        os.remove(output_file)

    tree.save(output_file)


if __name__ == '__main__':
    import time
    # Test directory: /SNS/REF_M/shared/ADARA.Test.Data.2018

    #translate('/SNS/REF_M/shared/ADARA.Test.Data.2018/REF_M_25631.nxs.h5', histo=False, sub_dir='translation_output')
    #translate('/SNS/REF_M/shared/ADARA.Test.Data.2018/REF_M_28722.nxs.h5', histo=False, sub_dir='translation_output')
    #translate('/SNS/REF_M/shared/ADARA.Test.Data.2018/REF_M_28144.nxs.h5', histo=False, sub_dir='translation_output')
    #translate('/SNS/REF_M/shared/ADARA.Test.Data.2018/REF_M_27800.nxs.h5', histo=False, sub_dir='translation_output')
    translate('/SNS/REF_M/shared/ADARA.Test.Data.2018/REF_M_25636.nxs.h5', histo=False, sub_dir='translation_output2')
    
    if False:
        data_dir = '/SNS/REF_M/shared/ADARA.Test.Data.2018'
        for item in os.listdir(data_dir):
            if os.path.isfile(os.path.join(data_dir, item)) and item.endswith('nxs.h5'):
                print("\n%s\n" % item)
                t_0 = time.time()
                translate(os.path.join(data_dir, item), histo=False, sub_dir='translation_output')
                print("%s: %s sec" % (item, time.time()-t_0))
