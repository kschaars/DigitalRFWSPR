#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2026 MIT Haystack Observatory.
#
# SPDX-License-Identifier: GPL-3.0-or-later
#

from gnuradio import gr, gr_unittest
# from gnuradio import blocks
from gnuradio.Passthrough_DigitalRF_Writer import Passthrough_DigitalRF_Writer

class qa_Passthrough_DigitalRF_Writer(gr_unittest.TestCase):

    def setUp(self):
        self.tb = gr.top_block()

    def tearDown(self):
        self.tb = None

    def test_instance(self):
        # FIXME: Test will fail until you pass sensible arguments to the constructor
        instance = Passthrough_DigitalRF_Writer()

    def test_001_descriptive_test_name(self):
        # set up fg
        self.tb.run()
        # check data


if __name__ == '__main__':
    gr_unittest.run(qa_Passthrough_DigitalRF_Writer)
