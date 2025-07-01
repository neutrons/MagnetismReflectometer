.. _developing:

Developing
==========

Directory Tree
--------------
 - Code under `mr_reduction/` is common reduction code.
 - Code under `mr_autoreduce/` is the top-level code used by the post-processing.
 - Code under `mr_livereduce/` is the top-level code for live reduction.


Setup Local Development Environment
-----------------------------------

To setup a local development environment, the developers should follow the steps below:

* Install `pixi <https://pixi.sh/latest/installation/>`_
* Clone the repository and make a feature branch based off ``next``.
* Create a new virtual environment with ``pixi install``
* Activate the virtual environment with ``pixi shell``
* Activate the pre-commit hooks with ``pre-commit install``

The ``pyproject.toml`` contains all of the dependencies for both the developer and the build servers.
Update file ``pyproject.toml`` if dependencies are added to the package.


From here, several tasks, such as building the documentation or running tests can be carried out with `pixi` tasks at the top of the repository.
For a list of available pixi tasks, run:

.. code-block:: bash

   $ pixi task list


Development procedure
---------------------

1. A developer is assigned with a task during neutron status meeting and changes the task's status to **In Progress**.
2. The developer creates a branch off *next* and completes the task in this branch.
3. The developer creates a pull request (PR) off *next*.
4. Any new features or bugfixes must be covered by new and/or refactored automated tests.
5. The developer asks for another developer as a reviewer to review the PR.
   A PR can only be approved and merged by the reviewer.
6. The developer changes the task’s status to **Complete** and closes the associated issue.


Using the Data Repository mr_reduction-data
-------------------------------------------

Some of the tests in this repository require access to data files which, due to their size, are stored in the Git LFS repository
`mr_reduction-data <https://code.ornl.gov/sns-hfir-scse/infrastructure/test-data/mr_reduction-data>`_.

To initialize or update the data repository, after installing your pixi environment:

.. code-block:: bash

   $ cd /path/to/MagnetismReflectometer
   $ pixi shell
   $ git submodule update --init

This will either clone `mr_reduction-data` into `/path/to/MagnetismReflectometer/tests/mr_reduction-data` or
bring the `mr_reduction-data`'s refspec in sync with the refspec listed within file `/path/to/mr_reduction/.gitmodules`.

An intro to Git LFS in the context of the Neutron Data Project is found in the
`Confluence pages <https://ornl-neutrons.atlassian.net/wiki/spaces/NDPD/pages/19103745/Using+git-lfs+for+test+data>`_
(login required).


Running tests
-------------

After activating your pixi environment for development, one can run three types of tests with `pytest`:

- tests that do not require any input data files
- tests requiring input data files from the data repository (see above)
- tests requiring input data files from the /SNS and /HFIR file systems

.. code-block:: bash

   $> python -m pytest -vv -m "not datarepo and not sns_mounted" tests/
   $> python -m pytest -vv -m "datarepo" tests/
   $> python -m pytest -vv -m "sns_mounted" tests/

Note that some tests also require Google Chrome to be installed for ``selenium``, a headless browser automation tool used for testing.

Coverage reports
----------------

GitHuh actions create reports for unit and integration tests, then combine into one report and upload it to
`Codecov <https://app.codecov.io/gh/neutrons/mr_reduction>`_.


Building the documentation
--------------------------
A repository webhook is setup to automatically trigger the latest documentation build by GitHub actions.
To build the documentation locally, simply use the included ``pixi`` task:

.. code-block:: bash

   $ cd /path/to/mr_reduction
   $ pixi run build-docs

After this, point your browser to
`file:///path/to/mr_reduction/docs/build/html/index.html`


Creating a stable release
-------------------------
- Follow the `Software Maturity Model <https://ornl-neutrons.atlassian.net/wiki/spaces/NDPD/pages/23363585/Software+Maturity+Model>`_
  for continuous versioning, as well as creating Candidate and Production releases.
- Update the :ref:`Release Notes <release_notes>` with major fixes, updates and additions since last stable release.
