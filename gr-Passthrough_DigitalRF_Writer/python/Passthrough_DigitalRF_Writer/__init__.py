#
# Copyright 2008,2009 Free Software Foundation, Inc.
#
# SPDX-License-Identifier: GPL-3.0-or-later
#

# The presence of this file turns this directory into a Python package

'''
This is the GNU Radio PASSTHROUGH_DIGITALRF_WRITER module. Place your Python package
description here (python/__init__.py).
'''
import os

# import pybind11 generated symbols into the Passthrough_DigitalRF_Writer namespace
try:
    # this might fail if the module is python-only
    from .Passthrough_DigitalRF_Writer_python import *
except ModuleNotFoundError:
    pass

# import any pure python here
from .Passthrough_DigitalRF_Writer import digital_rf_channel_sink
#
