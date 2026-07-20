#!/usr/bin/env python3
import argparse
import multiprocessing
import os
import subprocess
import time
import warnings
from copy import copy
from fractions import Fraction
from math import ceil
from pathlib import Path
import pandas as pd
import sys
import digital_rf as drf
import numpy as np
import scipy.signal as sig
from scipy.io import wavfile
import ast


warnings.simplefilter(action="ignore", category=FutureWarning)
CUPY_INIT = True
try:
    import cupy as cp
    import cupyx.scipy.signal as sig_cu
except:
    CUPY_INIT = False

class ModulatorResampler(object):
    """Implements a digital down/up converter for a large digital rf data set."""

    def __init__(self, f_shift, ds_x, drfObj, use_gpu=True):
        if isinstance(drfObj, (str, Path)):
            self.dio = drf.DigitalRFReader(str(drfObj))
        else:
            self.dio = drfObj
        self.ds_x = ds_x
        self.use_gpu = use_gpu
        self.f_shift = f_shift

        self.stages = _decimation_stages(ds_x.numerator, ds_x.denominator)

        # input-referred transient length of the whole cascade
        ovlap = 0
        D = 1                                  # cumulative decimation so far
        for (u, d) in self.stages:
            taps = 10 * max(u, d)
            ovlap += taps * D                  # this stage's half-length in input samples
            D *= d
        self.hlen = int(ovlap)                 # keep the name the rest of the code uses
        self.h_ds = sig.firwin(2 * hlen + 1, 1.0 / maxrate, window=wininfo)

    def get_start_samples(self, p, ichan, bnds=()):
        if not bnds:
            bnds = self.dio.get_bounds(ichan)
        nall = bnds[1] - bnds[0] + 1
        u = self.ds_x.numerator
        d = self.ds_x.denominator

        nd = ceil(nall * u / d)
        m = ceil(nd / p)
        mu = (m * d) // u
        ovlap = 2 * self.hlen
        mread = mu + ovlap

        st_samps = np.arange(p) * mu + bnds[0]
        if (bnds[-1] - st_samps[-1]) <= ovlap + int(self.ds_x):
            st_samps = st_samps[:-1]
        return st_samps, mread, m

    def dmod_ds_pool(self, ichan, start_sample, mread, m, out_start_sample):
        bnds = self.dio.get_bounds(ichan)

        f_shift = self.f_shift
        ds_x = self.ds_x
        st_samp_ = max(start_sample - self.hlen, bnds[0])

        front_us = (start_sample - st_samp_) * ds_x.numerator
        front_ds = front_us // ds_x.denominator + bool(front_us % ds_x.denominator)

        mread_ = min(mread, bnds[1] - st_samp_ + 1)

        x = self.dio.read_vector(st_samp_, mread_, ichan)
        props = self.dio.get_properties(ichan)
        sr_x = Fraction(
            props["sample_rate_numerator"], props["sample_rate_denominator"]
        )

        f_norm = f_shift / float(sr_x)
        rps = 2 * np.pi * f_norm
        phi = st_samp_ - bnds[0]
        p1 = np.exp(-1j * phi * rps)
        xout, _ = dmod_ds(x, sr_x, f_shift, ds_x, p1, use_cupy=self.use_gpu)
        xout = xout[front_ds:]
        if mread_ == mread:
            xout = xout[:m]
        st_ds = out_start_sample
        return xout, st_ds

def decode_has_spots(stdout):
    """True if the decoder produced at least one real spot line."""
    for line in stdout.splitlines():
        s = line.strip()
        if not s or s == "<DecodeFinished>":
            continue
        return True
    return False

def _decimation_stages(up, down, max_dec=8):
    """Split up/down into a cascade of (u, d) stages, each with a small
    decimation factor so anti-alias filters stay short and stable."""
    d = down
    factors = []
    for p in (2, 3, 5, 7):
        while d % p == 0:
            factors.append(p)
            d //= p
    if d > 1:
        factors.append(d)                    # leftover prime
    factors.sort(reverse=True)
    stages_d = []
    for f in factors:
        for i in range(len(stages_d)):
            if stages_d[i] * f <= max_dec:
                stages_d[i] *= f
                break
        else:
            stages_d.append(f)
    stages = [(1, dd) for dd in stages_d]
    _, d_last = stages[-1]
    stages[-1] = (up, d_last)                 # do the upsample in the last stage
    return stages

def dmod_ds(x, sr_x, f_shift, ds_x, mod_off=1+0j, dec_filter=None,
            beta=5.0, use_cupy=True):
    # frequency shift at full input rate
    f_norm = f_shift / float(sr_x)
    rps = 2 * np.pi * f_norm
    n = len(x)
    phi = np.arange(n, dtype=float) * rps
    w = np.exp(-1j * phi) * mod_off
    w_end = np.exp(-1j * n * rps) * mod_off

    stages = _decimation_stages(ds_x.numerator, ds_x.denominator)

    if CUPY_INIT and use_cupy:
        xp, spx = cp, sig_cu
        x = cp.asarray(x) * cp.asarray(w)
    else:
        xp, spx = np, sig
        x = x * w

    for (u, d) in stages:
        maxrate = max(u, d)
        taps = 10 * maxrate
        h = sig.firwin(2 * taps + 1, 1.0 / maxrate, window=("kaiser", beta))
        if xp is cp:
            h = cp.asarray(h)
        x = spx.resample_poly(x, u, d, window=h)

    if xp is cp:
        x = cp.asnumpy(x)
    return x, w_end

def run_decoder(wav_path, realWSPRD, dr):
    if realWSPRD == 1:
        cmd = ["wsprd", "-f", "1500", wav_path]
    else:
        cmd = ["./digitalRFWSPRD", "-f", str(dr[1]),
               "-n", str(dr[0]), "-x", str(dr[2]), wav_path]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        if result.stderr:
            print("--- Decoder Alerts ---")
            print(result.stderr)
        return result.stdout
    except subprocess.CalledProcessError as e:
        print(f"Decoder exited with error code {e.returncode}")
        print(e.stderr)
        return ""
    except FileNotFoundError:
        print("Error: decoder binary not found in PATH.")
        return ""

def extract_and_decode_wspr(
    drf_dir, channel, sched_df, decoder_bin="wsprd", use_gpu=True, tmp_wav_dir="./wspr_tmp", realWSPRD = 1, decodeRange = [1500,1400,1600], sweep = 0):
    """Reads a Digital RF folder (all underlying .h5 files), processes it 
    in scheduled intervals, outputs 12kHz WAV files, and decodes them using 
    the external C binary.
    """
    if not os.path.exists(tmp_wav_dir):
        os.makedirs(tmp_wav_dir)

    # Initialize the Reader to abstract the underlying .h5 files
    dio = drf.DigitalRFReader(drf_dir)
    props = dio.get_properties(channel)
    sr_x = Fraction(props["sample_rate_numerator"], props["sample_rate_denominator"])
    bnds =dio.get_bounds(channel)
    startTime = bnds[0]/float(sr_x)
    #print(startTime)
    #print("sr_x: " + str(sr_x))
    target_sr = Fraction(12000, 1)
    ds_ratio = target_sr / sr_x
    ncores = min(multiprocessing.cpu_count(), 8)

    print(f"--- Starting WSPR Pipeline ---")
    print(f"Targeting Channel: {channel} | Original Sample Rate: {float(sr_x)} Hz")

    for idx, row in sched_df.iterrows():
        st_ut = row["start"]
        et_ut = row["end"]
        
        # Convert schedule times to sample indices
        st_samp = max(bnds[0], drf.util.time_to_sample(int(st_ut), int(sr_x)))
        end_samp = min(bnds[1], drf.util.time_to_sample(int(et_ut), int(sr_x)))
        st_samp, end_samp = bnds[0], bnds[1]
        """
        print("bnds        :", bnds)
        print("sr_x        :", sr_x, float(sr_x))
        print("startTime   :", startTime)
        print("T(start)    :", drf.util.time_to_sample(int(st_ut), int(sr_x)))
        print("T(end)      :", drf.util.time_to_sample(int(et_ut), int(sr_x)))
        print("st_samp     :", st_samp)
        print("end_samp    :", end_samp)
        print("covered (s) :", (end_samp - st_samp) / float(sr_x))
        print("full rec (s):", (bnds[1] - bnds[0]) / float(sr_x))
        """
        if st_samp >= end_samp:
            print(f"Invalid time bounds or missing data for entry {idx}. Skipping...")
            continue
        #print("st_samp:  " + str(st_samp)) 
        #print("end_samp: " + str(end_samp))
        f_shift = 0.0 
        
        print(f"\nProcessing segment {idx}: {et_ut - st_ut} seconds")
        
        modrs = ModulatorResampler(f_shift, ds_ratio, dio, use_gpu)
        TARGET_SAMPLES_PER_READ = 4_000_000        # ~64 MB complex128 per read
        total_in = end_samp - st_samp + 1
        nreads = max(5, ceil(total_in / TARGET_SAMPLES_PER_READ))
        
        st_samps, mread, m = modrs.get_start_samples(nreads, channel, bnds=(st_samp, end_samp))
        p_items = [(channel, ist, mread, m, idx * m + b) for b, ist in enumerate(st_samps)]
        #print("new st_samp: " + str(st_samp))
        ctx = multiprocessing.get_context("spawn")
        complex_buffers = []
        
        # Parallelized Downsampling Pipeline
        with ctx.Pool(processes=ncores) as pool:
            outputs = pool.starmap(modrs.dmod_ds_pool, p_items)
            for out_data, _ in outputs:
                complex_buffers.append(out_data)
        
        # Concatenate pieces into one complete continuous block
        if not complex_buffers:
            print(f"No data returned for segment {idx}.")
            continue
        x_ds = np.concatenate(complex_buffers)
        #print(len(x_ds)) 
        # Convert complex spectrum to real audio data
        x_real = np.real(x_ds)
        
        # Clean up any residual NaN or Inf values that ruin scaling math
        x_real = np.nan_to_num(x_real, nan=0.0, posinf=0.0, neginf=0.0)
        
        # Safe 16-bit Integer PCM Peak Normalization
        max_val = np.max(np.abs(x_real))
        if max_val > 0.0:
            # Scale full dynamic range into standard 16-bit signed boundaries (-32768 to 32767)
            x_scaled = ((x_real / max_val) * 32000).astype(np.int16)
        else:
            x_scaled = np.zeros_like(x_real, dtype=np.int16)
            print("Warning: Extracted signal vector contains only silent/zero values.")
        fs  = int(target_sr)     # 12000
        WIN = 120                # WSPR frame length (s)
        total_s = len(x_real) / fs
        first_boundary = np.ceil(startTime / 120.0) * 120.0
        offset0        = first_boundary - startTime
        if offset0 < 0:
            offset0 += 120.0

        seg = 0
        t = offset0
        """
        print("fs: " + str(fs)) 
        print("x_real: " + str(len(x_real)))
        print("total_s:")
        print(total_s)
        print("t: " + str(t))
        print("WIN: " + str(WIN))
        """
        while t + WIN <= total_s + 1e-6:
            a = int(round(t * fs))
            b = a + WIN * fs
            chunk = x_real[a:b]
            mv = np.max(np.abs(chunk))
            chunk16 = ((chunk/mv)*32000).astype(np.int16) if mv > 0 else \
                      np.zeros_like(chunk, np.int16)
            wav_path = os.path.join(tmp_wav_dir, f"wspr_segment_{idx}_{seg}.wav")
            wavfile.write(wav_path, fs, chunk16)
            print(f"WAV file exported to: {wav_path}  (t={t:.1f}s)")
            dr = sorted(decodeRange)
            stdout = run_decoder(wav_path, realWSPRD, dr)
            print("\n--- Decoder Output ---")
            print(stdout)
            # Sweep only if nothing decoded and sweeping is enabled
            if realWSPRD != 1 and sweep == 1 and not decode_has_spots(stdout):
                HALF = 80          # half of the 160 Hz window
                for center in range(200 + HALF, 5800 - HALF + 1, 160):
                    lo, hi = center - HALF, center + HALF
                    print(f"Sweeping center={center} Hz  [{lo}-{hi}]")
                    stdout = run_decoder(wav_path, realWSPRD, [lo, center, hi])
                    if decode_has_spots(stdout):
                        print("\n--- Decoder Output (sweep hit) ---")
                        print(stdout)
                        break   # stop at first successful decode

            seg += 1
            t   += 120.0 

# Original signal extraction function
def sig_extract_ds(drf_list, out_dir_prot, sched_df, use_gpu=True, printfunc=print, sampRate=Fraction(12000, 1)):
    pass


if __name__ == "__main__":
    #Command line arguments required:
    #   Name of directory that contains digitalRF data
    #   The frequency the signal is to be down converted to (set to 0 if frequency already offset to 1.5kHz)
    #   Start time of signal in unix time
    #   End time in unix time
    #   Boolean to use GPU
    # Test schedule matching standard 2-minute WSPR time windows
    metadataPath = "/data/captures/" + sys.argv[1] + "/data"
    dir_drf = metadataPath
    metadataPath = metadataPath + "/" + str(os.listdir(metadataPath)[1])
    startTime = metadataPath + "/" + str(os.listdir(metadataPath)[1]) 
    metadataPath = metadataPath + "/" + str(os.listdir(metadataPath)[0]) 
    startTime = 0
    #print("startTime: " + str(startTime))
    dmr = drf.DigitalMetadataReader(str(metadataPath))
    dataDict = dmr.read()
    #center <= 5800
    center = 200 
    left = center
    right = center 
    
#    startTimeIndex = list(dataDict.keys())[0]
#    start_val__ = np.ceil(dataDict[startTimeIndex]['start_time'])
#    if start_val__ % 2 != 0: 
#        start_val__ += 1
    data = {
        'freq kHz': [int(sys.argv[2])],
        'start': int(startTime),  # Start Unix Epoch Timestamp
        'end':  int(startTime) + 240    # End Unix Epoch Timestamp
    }
    sched = pd.DataFrame(data)
    extract_and_decode_wspr(
        drf_dir= dir_drf,  
        channel=sys.argv[6] ,    #Name of digital RF directory, no "/"
        sched_df=sched,      
        decoder_bin="./wsprd",  #WSPRD decoder
        use_gpu= sys.argv[3],    #Boolean for using the GPU
        realWSPRD=int(sys.argv[4]), #use a 0 to run as digitalRFWSPRD, 1 for WSPRD
        decodeRange = ast.literal_eval(sys.argv[5]), #An array containing center frequency, lower, and upper decoding range
        sweep = 1
    )

