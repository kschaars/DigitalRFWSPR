from __future__ import absolute_import, division, print_function

import os
import tempfile

import numpy as np
from pathlib import Path
import multiprocessing
import time
import warnings
from copy import copy
from fractions import Fraction
from math import ceil
import digital_rf as drf
import numpy as np
import scipy.signal as sig
import sys
import os
out_dir_prot = "/data/captures/plutoTestFolder/data/chD" 

out_proto = out_dir_prot + "/" + str(os.listdir(out_dir_prot)[1])
print(out_proto)
startTime = os.listdir(out_proto)[0]
print(startTime)
startTime = startTime[3:13]
startTime = int(startTime)
print(startTime)

#dmr = drf.DigitalMetadataReader("/home/kschaars/test1kHz4Min/metadata")
#print(dmr)
#fields = dmr.get_fields()

