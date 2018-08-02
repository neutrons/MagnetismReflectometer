[![TRAVISCI](https://travis-ci.org/mdoucet/MagnetismReflectometer.svg?branch=master)](https://travis-ci.org/mdoucet/MagnetismReflectometer)
[![codecov](https://codecov.io/gh/mdoucet/MagnetismReflectometer/branch/master/graph/badge.svg)](https://codecov.io/gh/mdoucet/MagnetismReflectometer)

# MR automated reduction
Automated reduction code based on Mantid.

 - Code under `mr_reduction` is common reduction code.
 - Code under `autoreduce` is the top-level code used by the post-processing.
 - Code under `livereduce` is the top-level code for live reduction.

# Configuration
The configuration file under `livereduce/livereduce.conf` needs to be place under `/etc` on
the live reduction node.
