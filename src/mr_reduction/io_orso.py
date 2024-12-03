# standard imports

# third party imports

# mr_reduction imports


def write_orso(ws_list, output_path, cross_section):
    r"""
    Write out reflectivity output (usually from autoreduction, as file REF_M_*_autoreduce.dat).

    This function generates and writes reflectivity data (typically as a result of an autoreduction process)
    to an output file in ORSO ASCII which can be loaded by SasView. The output file is usually named in the format
    `REF_M_*_autoreduce.dat`.

    Parameters
    ----------
    ws_list : list
        A list of workspace objects containing reflectivity data.
    output_path : str
        The path where the output file will be written. Must have .ort extension.
    cross_section : str
        The cross-section information to be included in the output file.
    """
    print(ws_list, cross_section)
    if not output_path.endswith(".ort"):
        raise ValueError("Output file must have .ort extension")
    with open(output_path, "w") as file_handle:
        file_handle.seek(0)
        pass
