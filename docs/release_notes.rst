.. _release_notes:

Release Notes
=============

Notes for major and minor releases. Notes for patch releases are referred to the next minor release.

..
   v2.10.0
   -------
   (date of release, format YYYY-MM-DD)

   **Of interest to the User:**

   - PR #

   **Of interest to the Developer:**

   - PR #
..


v2.9.0
------
2025-16-01

**Of interest to the User:**

- PR #

**Of interest to the Developer:**

- PR #73: merge deploy and testing

v2.8.0
------
2025-07-01

**Of interest to the User:**

- PR #69 Removes `Show 2D Plots` option and instead always generates them. Displays a message on errors.

**Of interest to the Developer:**

- PR #70 use of mantidworkbench conda package is replaced with mantid


v2.7.0
------
2025-06-24

**Of interest to the User:**

- PR #68 Informative exception raised when a file with an insufficient number of events is attempted to be reduced


v2.6.0
------
2025-06-17

**Of interest to the User:**

- PR #66 X-TOF plot now shows up second and axes are flipped


v2.5.0
------
2025-06-10

**Of interest to the User:**

- PR #

**Of interest to the Developer:**

- PR #64 Remove `is_polarized_dataset` from `io_orso.py`


v2.4.0
------
2025-06-03

**Of interest to the User:**

- PR #60: Update local reduction tool with ROI-related documentation
- PR #59: Incorporate ROI3 and ROI4 to the reduction workflow

**Of interest to the Developer:**

- PR #57: ROI1 is used for peak, and ROI2 for background
- PR #55: Refactor MRInspectData as module inspect_data
- PR #55: Refactor MRInspectData as module inspect_data


v2.3.0
------
2025-05-13

**Of interest to the User:**

- PR #54: Update the documentation with the possible configurations when using ROI1* and ROI2*
- PR #51: Autoreduction will not save the current "REF_M_*_combined.py" script anymore
- PR #41: bugfix for runs containing logs with time entries predating the start of the run

**Of interest to the Developer:**

- PR #52: Convert Mantid algorithm MRFilterCrossSections to a module of mr_reduction
- PR #50: Purge the cross-section filtering table of negative relative times to the start of the run
- PR #45: Document how to deploy updates to the live reduction service
- PR #44: Documentation on how to use StartLiveData algorithm
- PR #43: Update livereduce.conf file
- PR #41: MRFilterCrossections defined as Mantid python algorithm in the source code


v2.2.0
------
2025-04-15

**Of interest to the User**:

- PR #39 Update mantid version to 6.12
- PR #38: Live reduction integration

**Of interest to the Developer:**

- PR #37 Introduce ORSO-saving functionality in the autoreduction workflow

v2.1.0
------
2025-04-01

**Of interest to the User**:

- PR #36 Saving all cross-sections for the combined profiles in one ORSO-formatted file
- PR #33 Saving all cross-sections for one run in one ORSO-formatted file

**Of interest to the Developer:**

- PR #35 Reduce figure size in the web report by eliminating non-significant data

v2.0.0
------
2025-03-18

**Of interest to the User**:

- PR #31 Save the spin selection state in the ORSO file
- PR #30 Documentation on how the ROI's in the sample logs are used
- PR #28 Ability to manually set the Y-Pixel (low resolution) range for the peaks
- PR #26 Fix extracting the run number in the autoreduction template
- PR #25 Converter from Nexus to ORSO.ort for autoreduced files
- PR #9 Add the capability to autoreduce two peaks from the same run

**Of interest to the Developer:**

- PR #29 Documentation for troubleshooting autoreduction
- PR #24 Class ReflectedBeamOptions to reuse when saving to diferent file formats
- PR #23 Class DirectBeamOptions to reuse when saving to diferent file formats
- PR #22 SampleLogs class to reduce boilerplate code and make the code more pythonic
- PR #21 Enum DataType substitutes expressions involving integer values to improved understanding of the source
- PR #16 transition from pip to conda when installing dependency finddata
- PR #15 increase gunicorn timeout for workers to prevent them being killed before finishing the reduction
- PR #12 switch from mantid to mantidworkbench conda package
- PR #8 add finddata dependency
- PR #5 modernize the repo in accordance with the python project template


1.0.0
-----
2024-03-26

This is the original state of the repository when adopted by the Neutron Data Project,
before any modernizations were carried out.
