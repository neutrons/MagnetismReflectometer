.. conda_environments

Conda Environments
==================

Three conda environments are available in the analysis nodes (analysis.sns.gov), beamline machines, as well as the
jupyter notebook severs (jupyter.sns.gov). On a terminal:

.. code-block:: bash

   $> conda activate <environment>

where `<environment>` is one of `mr_reduction`, `mr_reduction-qa`, and `mr_reduction-dev`

mr_reduction Environment
------------------------
Activates the latest production release of `mr_reduction`. Users will typically reduce their data in this environment.

mr_reduction-qa Environment
---------------------------
Activates the latest candidate release environment.
Instrument scientists and computational instrument scientists will carry out testing on this environment
to prevent bugs being introduce in the next production release.

mr_reduction-dev Environment
----------------------------
Activates the environment corresponding to the latest changes in the source code.
Instrument scientists and computational instrument scientists will test the latest features and bugfixes
introduced in `mr_reduction`.
