#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2026 MIT Haystack Observatory.

# ----------------------------------------------------------------------------
# Copyright (c) 2017 Massachusetts Institute of Technology (MIT)
# All rights reserved.
#
# Distributed under the terms of the BSD 3-clause license.
#
# The full license is in the LICENSE file, distributed with this software.
# ----------------------------------------------------------------------------
"""Convert a raw binary file to Digital RF format with metadata."""

from __future__ import absolute_import, division, print_function
import argparse
import glob
import time
import os
import numpy as np
import h5py
from digital_rf import DigitalRFWriter, DigitalMetadataWriter, util


def _patch_center_frequencies(metadata_dir):
    """Force center_frequencies datasets to shape (1,) on disk.

    DigitalMetadataWriter squeezes single-element arrays down to scalar
    (shape ()) datasets. When read back, a scalar surfaces as a native
    Python float, which lacks a .ravel() method -- causing the Digital RF
    Source block to crash with 'float object has no attribute ravel'.
    This re-writes any scalar center_frequencies dataset as a 1-D array.
    """
    files = [
        f for f in glob.glob(
            os.path.join(metadata_dir, "**", "*.h5"), recursive=True
        )
        if os.path.basename(f) != "dmd_properties.h5"
    ]
    for path in files:
        with h5py.File(path, "a") as h:
            for sample_grp in h.keys():
                grp = h[sample_grp]
                if "center_frequencies" not in grp:
                    continue
                ds = grp["center_frequencies"]
                if ds.shape == ():  # scalar -> fix to (1,)
                    val = np.atleast_1d(
                        np.asarray(ds[()], dtype=np.float64)
                    )
                    del grp["center_frequencies"]
                    grp.create_dataset("center_frequencies", data=val)
                    print("Patched center_frequencies in {} [{}]: () -> {}".format(
                        os.path.basename(path), sample_grp, val.shape))

def binary_to_drf(
    input_file,
    channel_dir,
    dtype="complex64",
    is_complex=True,
    num_subchannels=1,
    subdir_cadence_secs=3600,
    file_cadence_millisecs=1000,
    sample_rate_numerator=1000000,
    sample_rate_denominator=1,
    start=None,
    uuid_str=None,
    center_frequencies=None,
    metadata=None,
    compression_level=0,
    checksum=False,
    is_continuous=True,
    marching_periods=True,
    chunk_size=1000000
):
    # dtype handling (mirrors the original block)
    dtype = np.dtype(dtype)
    if is_complex and (
        not np.issubdtype(dtype, np.complexfloating) and not dtype.names
    ):
        realdtype = dtype
        dtype = np.dtype([("r", realdtype), ("i", realdtype)])

    sample_rate = np.longdouble(sample_rate_numerator) / np.longdouble(
        sample_rate_denominator
    )

    # start-time / start-sample handling 
    if start is None or start == "":
        start = time.time()          # UTC timestamp -> written as float
    start_sample = util.parse_identifier_to_sample(
        start, sample_rate, None
    )
    if start_sample is None:
        start_sample = 0
    print("Start sample index (samples since epoch):", start_sample)

    # ---- create channel + metadata directories ----
    if not os.path.exists(channel_dir):
        os.makedirs(channel_dir)
    metadata_dir = os.path.join(channel_dir, "metadata")
    if not os.path.exists(metadata_dir):
        os.makedirs(metadata_dir)

    # Digital RF writer 
    writer = DigitalRFWriter(
        channel_dir,
        dtype,
        subdir_cadence_secs,
        file_cadence_millisecs,
        start_sample,
        sample_rate_numerator,
        sample_rate_denominator,
        uuid_str=uuid_str,
        compression_level=compression_level,
        checksum=checksum,
        is_complex=is_complex,
        num_subchannels=num_subchannels,
        is_continuous=is_continuous,
        marching_periods=marching_periods,
    )

    # Digital Metadata writer 
    dmd_writer = DigitalMetadataWriter(
        metadata_dir=metadata_dir,
        subdir_cadence_secs=subdir_cadence_secs,
        file_cadence_secs=1,
        sample_rate_numerator=sample_rate_numerator,
        sample_rate_denominator=sample_rate_denominator,
        file_name="metadata",
    )

    # build the metadata dictionary 
    if metadata is None:
        metadata = {}
    if not center_frequencies:
        center_frequencies = np.array([0.0] * num_subchannels, dtype=np.float64)
    else:
        center_frequencies = np.ascontiguousarray(
            center_frequencies, dtype=np.float64
        )
    # guarantee at least 1-D so .ravel() always works on read-back
    center_frequencies = np.atleast_1d(center_frequencies)

    metadata.update(
        uuid_str=writer.uuid,
        sample_rate_numerator=sample_rate_numerator,
        sample_rate_denominator=sample_rate_denominator,
        center_frequencies=center_frequencies,
    )
    dmd_writer.write(start_sample, metadata)

    # read the binary file in chunks and write
    itemsize = dtype.itemsize          # bytes per sample (per subchannel item)
    samples_per_chunk = chunk_size     # e.g. 1_000_000 samples per write

    total_samples = 0
    file_bytes = os.path.getsize(input_file)
    bytes_per_sample = itemsize * num_subchannels
    expected_samples = file_bytes // bytes_per_sample
    print("File size: {:.2f} GB, expected {} samples".format(
        file_bytes / 1e9, expected_samples))

    with open(input_file, "rb") as f:
        while True:
            # read samples_per_chunk * num_subchannels items
            count = samples_per_chunk * num_subchannels
            chunk = np.fromfile(f, dtype=dtype, count=count)
            if chunk.size == 0:
                break                    # end of file

            if num_subchannels > 1:
                # reshape to (nsamples, num_subchannels)
                nfull = chunk.size // num_subchannels
                chunk = chunk[:nfull * num_subchannels].reshape(
                    (nfull, num_subchannels)
                )

            writer.rf_write(chunk)
            total_samples += len(chunk)

            # progress feedback
            pct = 100.0 * total_samples / expected_samples if expected_samples else 0
            print("\rWrote {} / {} samples ({:.1f}%)".format(
                total_samples, expected_samples, pct), end="", flush=True)

    print()  # newline after progress
    writer.close()

    # DigitalMetadataWriter collapses single-element center_frequencies to a
    # scalar dataset; re-expand it to shape (1,) so .ravel() works on read.
    _patch_center_frequencies(metadata_dir)

    print("Done. Wrote {} samples of Digital RF to: {}".format(
        total_samples, channel_dir))


def main():
    p = argparse.ArgumentParser(
        description="Convert a raw binary file to Digital RF format."
    )
    p.add_argument("input_file", help="Path to the raw binary input file.")
    p.add_argument("channel_dir", help="Output channel directory.")
    p.add_argument("-d", "--dtype", default="complex64",
                   help="numpy dtype of the file data (e.g. complex64, float32, int16).")
    p.add_argument("-r", "--sample-rate", type=int, default=1000000,
                   dest="sample_rate_numerator",
                   help="Sample rate numerator in Hz.")
    p.add_argument("--sample-rate-denom", type=int, default=1,
                   dest="sample_rate_denominator")
    p.add_argument("-s", "--start", default=None,
                   help="Start time: UTC timestamp (float), sample index (int), "
                        "ISO8601 string, or 'now'. Default = current time.")
    p.add_argument("-f", "--center-freq", type=float, default=None,
                   help="Center frequency in Hz.")
    p.add_argument("-n", "--num-subchannels", type=int, default=1)
    p.add_argument("--real", action="store_true",
                   help="Data is real (not interleaved complex).")
    p.add_argument("--subdir-cadence", type=int, default=3600,
                   dest="subdir_cadence_secs")
    p.add_argument("--file-cadence", type=int, default=1000,
                   dest="file_cadence_millisecs")
    p.add_argument("--uuid", default=None, dest="uuid_str")
    p.add_argument("--chunk-size", type=int, default=1000000,
                   dest="chunk_size",
                   help="Samples to read/write per iteration. "
                        "Larger = faster but more RAM.")
    args = p.parse_args()

    cfreqs = [args.center_freq] if args.center_freq is not None else None

    binary_to_drf(
        input_file=args.input_file,
        channel_dir=args.channel_dir,
        dtype=args.dtype,
        is_complex=not args.real,
        num_subchannels=args.num_subchannels,
        subdir_cadence_secs=args.subdir_cadence_secs,
        file_cadence_millisecs=args.file_cadence_millisecs,
        sample_rate_numerator=args.sample_rate_numerator,
        sample_rate_denominator=args.sample_rate_denominator,
        start=args.start,
        uuid_str=args.uuid_str,
        center_frequencies=cfreqs,
        chunk_size=args.chunk_size
    )

if __name__ == "__main__":
    main()