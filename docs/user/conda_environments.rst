.. conda_environments

Conda Environments
==================

Three conda environments are available in the analysis nodes, beamline machines, as well as the
jupyter notebook severs. On a terminal:

.. code-block:: bash

   $> conda activate <environment>

where `<environment>` is one of `mr_reduction`, `mr_reduction-qa`, and `mr_reduction-dev`

mr_reduction Environment
------------------------
Activates the latest stable release of `mr_reduction`. Typically users will reduce their data in this environment.

mr_reduction-qa Environment
---------------------------
Activates a release-candidate environment.
Instrument scientists and computational instrument scientists will carry out testing on this environment
to prevent bugs being introduce in the next stable release.

mr_reduction-dev Environment
----------------------------
Activates the environment corresponding to the latest changes in the source code.
Instrument scientists and computational instrument scientists will test the latest changes to `mr_reduction` in this
environment.
