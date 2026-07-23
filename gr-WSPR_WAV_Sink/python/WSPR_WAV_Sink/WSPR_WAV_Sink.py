#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2026 MIT Haystack Observatory.
#
# SPDX-License-Identifier: GPL-3.0-or-later
#

import numpy as np

from gnuradio import gr

import pmt
import subprocess
import os
import scipy.io.wavfile as wav
from datetime import datetime, timezone

class wsprd_time_synced_block(gr.sync_block):
    def __init__(self, sample_rate=12000, signalCenterFrequency = 915000000, signalOffset = 1500, FileName = 'wspr_chunk', timing = 0):
        gr.sync_block.__init__(
            self,
            name='WSPRD WAV generator',
            in_sig=[np.float32],
            out_sig=[]
        )
        self.timing = timing
        self.center = str(signalCenterFrequency + signalOffset - 1500)
        self.sample_rate = sample_rate
        self.recording = False
        # 1 minute 54 seconds worth of samples
        self.samples_to_record = int(119 * self.sample_rate)
        self.buffer = []
        self.last_minute = None
        self.FileName = FileName
        self.message_port_register_out(pmt.intern('spots'))


    def work(self, input_items, output_items):
        in0 = input_items[0]
        n = len(in0)
        now = datetime.now()
        current_minute = now.minute
        # Check for the start of an even minute
        if self.last_minute is not None and self.last_minute != current_minute:
            if current_minute % 2 == 0 and not self.recording:
                print(f"Recording Started at {now.strftime('%H:%M:%S')}")
                self.recording = True
                self.buffer = [] # Clear buffer for new recording
                
        self.last_minute = current_minute

        if self.timing != 0 and self.recording == False:
            self.recording = True
            print(f"Recording Started at {now.strftime('%H:%M:%S')}")
            self.buffer = [] # Clear buffer for new recording
            
        # 2. Accumulate samples over multiple work calls 
        if self.recording:
            needed = self.samples_to_record - len(self.buffer)
            if needed > 0:
                # Take either what is available in this chunk, or just what we need to finish
                take = min(needed, n)
                self.buffer.extend(in0[:take])
    
            # 3. Check collected  full 1m 54s of data
            if len(self.buffer) >= self.samples_to_record:
                print("Recording stopped, beginning processing.")
                self.process_wsprd() 
                self.recording = False # Reset state, wait for next even minute

        # Consume all input items so GNU Radio keeps streaming
        return n
    def process_wsprd(self):
        temp_wav = 'TXScreenShots/' + self.FileName + '.wav'
        print(temp_wav)
        clipped_buffer = np.clip(self.buffer, -1.0,1.0) 
        audio_int16 = (clipped_buffer * 32767.0).astype(np.int16) 
        wav.write(temp_wav, self.sample_rate, audio_int16)
        print("recording and writing done")


        pass
