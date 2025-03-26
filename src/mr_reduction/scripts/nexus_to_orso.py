"""This is a script that use the package as a module."""
# PYTHON_ARGCOMPLETE_OK

# standard imports
import argparse
import os

# third party imports
import argcomplete
from mantid.simpleapi import LoadNexusProcessed

# mr_reduction imports
from mr_reduction.io_orso import save_cross_sections


def main():
    parser = argparse.ArgumentParser(
        description="Convert one or more Nexus files resulting from autoreduction to a *.ort ORSO files"
    )
    parser.add_argument("--nexus", required=True, help="Path to the input Nexus file(s)")
    parser.add_argument("--ort", required=True, help="Path to the output *.ort ORSO file")
    argcomplete.autocomplete(parser)
    args = parser.parse_args()

    # Load the Nexus file(s)
    workspace_list = []
    valid_suffix = "_autoreduce.nxs.h5"
    for nexus_path in args.nexus.split():
        if nexus_path.endswith(valid_suffix) is False:
            raise ValueError(f"Input file {nexus_path} is not a valid Nexus autoreduced file")
        workspace_name = os.path.basename(nexus_path).removesuffix(valid_suffix)
        LoadNexusProcessed(Filename=nexus_path, OutputWorkspace=workspace_name)
        workspace_list.append(workspace_name)

    # Write the ORSO file
    save_cross_sections(workspace_list, args.ort)


if __name__ == "__main__":
    main()
