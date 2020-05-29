[![TRAVISCI](https://travis-ci.org/neutrons/MagnetismReflectometer.svg?branch=master)](https://travis-ci.org/neutrons/MagnetismReflectometer)
[![codecov](https://codecov.io/gh/neutrons/MagnetismReflectometer/branch/master/graph/badge.svg)](https://codecov.io/gh/neutrons/MagnetismReflectometer)

# MR automated reduction
Automated reduction code based on Mantid.

 - Code under `mr_reduction` is common reduction code.
 - Code under `autoreduce` is the top-level code used by the post-processing.
 - Code under `livereduce` is the top-level code for live reduction.

# Configuration
The configuration file under `livereduce/livereduce.conf` needs to be place under `/etc` on
the live reduction node.
