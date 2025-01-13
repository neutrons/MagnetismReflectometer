"""This is a script that use the package as a module."""
# PYTHON_ARGCOMPLETE_OK

# standard imports
import argparse

# third party imports
import argcomplete
from mantid.simpleapi import LoadNexusProcessed

# mr_reduction imports
from mr_reduction.io_orso import write_orso


def main():
    parser = argparse.ArgumentParser(description="Convert a Nexus file resulting from autoreduction to *.ort ORSO")
    parser.add_argument("--nexus", required=True, help="Path to the input Nexus file")
    parser.add_argument("--ort", required=True, help="Path to the output *.ort ORSO file")
    argcomplete.autocomplete(parser)
    args = parser.parse_args()

    # Load the Nexus file
    reflectivity_workspace = LoadNexusProcessed(args.nexus)

    # Write the ORSO file
    write_orso([reflectivity_workspace], args.ort)


if __name__ == "__main__":
    main()
