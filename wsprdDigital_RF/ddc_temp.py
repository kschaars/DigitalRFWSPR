import multiprocessing
import time
import warnings
from copy import copy
from fractions import Fraction
from math import ceil
from pathlib import Path
import pandas as pd

import digital_rf as drf

import numpy as np
import scipy.signal as sig

warnings.simplefilter(action="ignore", category=FutureWarning)
CUPY_INIT = True
try:
    import cupy as cp
    import cupyx.scipy.signal as sig_cu

    # warnings.filterwarnings("ignore", module="cupyx")
except:
    CUPY_INIT = False


class ModulatorResampler(object):
    """Implements a digital down/up converter for a large digital rf data set. This object"""

    def __init__(self, f_shift, ds_x, drfObj, use_gpu=True):
        """Creates the digital down/up converter object.

        Parameters
        ----------
        f_shift : float
            The frequency shift in Hz
        ds_x : Fraction
            Numerator respesents the upsampling factor, denominator is thedown sampling factor
        drfObj : str, Path or DigitalRFReader
            Data set.
        """
        if isinstance(drfObj, (str, Path)):
            self.dio = drf.DigitalRFReader(str(drfObj))
        else:
            self.dio = drfObj
        self.ds_x = ds_x
        self.use_gpu = use_gpu
        self.f_shift = f_shift
        wininfo = ("kaiser", 5.0)
        maxrate = max(ds_x.numerator, ds_x.denominator)
        hlen = 10 * maxrate
        self.hlen = hlen
        self.h_ds = sig.firwin(2 * hlen + 1, 1.0 / maxrate, window=wininfo)

    def get_start_samples(self, p, ichan, bnds=()):
        """Works out the reading locations in the original dataset given a number of reads, the channel name and desired bounds. If bounds is empty just reads the entire dataset. This is assuming that the resampling leaves a centered array.

        Parameters
        ----------
        p : int
            The number of pieces the recording will be broken into.
        ichan : str
            The channel name.
        bnds : tuple
            Start and stop sample of the overall read.
        Returns
        -------
        st_samps : ndarray
            The list of starting samples in the original recording. This will be the first sample in the new recording of each write.
        mread : int
            The number of samples per read
        m : int
            Number of samples after the down sampling for each read.
        """
        if not bnds:
            bnds = self.dio.get_bounds(ichan)
        nall = bnds[1] - bnds[0] + 1
        u = self.ds_x.numerator
        d = self.ds_x.denominator

        # the final number of samples after down sampling
        nd = ceil(nall * u / d)
        # the number of samples for each segment after resampling
        m = ceil(nd / p)
        # the read spacing
        mu = (m * d) // u
        ovlap = 2 * self.hlen
        mread = mu + ovlap

        st_samps = np.arange(p) * mu + bnds[0]
        # Pop off last read if it's less than
        if (bnds[-1] - st_samps[-1]) <= ovlap + int(self.ds_x):
            st_samps = st_samps[:-1]
        return st_samps, mread, m

    def dmod_ds_pool(self, ichan, start_sample, mread, m, out_start_sample):
        """
        Parameters
        ----------
        ichan : str
            The channel name.
        st_samps : ndarray
            The list of starting samples in the original recording. This will be the first sample in the new recording of each write.
        mread : ndarray
            The number of samples per read
        m : number of samples after the downsampling

        Returns
        -------
        xout : ndarray
            The down sampled array.
        st_ds : int
            The start time for the sample that will be written.
        """
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
        # radians per sample
        rps = 2 * np.pi * f_norm
        phi = st_samp_ - bnds[0]
        p1 = np.exp(-1j * phi * rps)
        xout, _ = dmod_ds(x, sr_x, f_shift, ds_x, p1, use_cupy=self.use_gpu)
        xout = xout[front_ds:]
        if mread_ == mread:
            xout = xout[:m]
#        st_ds = (start_sample*ds_x.numerator) // ds_x.denominator
        st_ds = out_start_sample
        return xout, st_ds


def sig_extract_ds(drf_list, out_dir_prot, sched_df, use_gpu=True, printfunc=print, sampRate= Fraction(12000,1)):
    """Extract the ionosphere sounding signal from the larger recording. This version downsamples and frequency converts the data which can be broken up across multiple digital RF datasets. It loops through the list of transmitted signals and then channels to process the data.

    Parameters
    ----------
    drf_dir : list
        Name of the original directory
    out_dir_pro : str
        Directory that holds all of the broken up datesets.
    sched_df : pd.DataFrame
        Columns are the center frequency in kHz, bandwidth in kHz, start, and stop. 
        The start and stop times are in posix seconds.
    use_gpu : bool
        Boolian to use the gpu.
    print_func : func
        Where to print the output
    sampRate: fraction 
        desired output sample rate
    """
    out_proto = Path.home() / out_dir_prot

#   f_samp = Fraction(500000, 1)
    nrows = sched_df.shape[0]
    ncores = multiprocessing.cpu_count()

    dmr = drf.DigitalMetadataReader(str(drf_list[0] + "/digitalRFWSPRTestHomeMade/metadata"))
    path = str(drf_list[0] + "/digitalRFWSPRTestHomeMade")
    dataDict = dmr.read()
    drf_op_dict = dict(
        sample_rate_numerator=sampRate.numerator,
        sample_rate_denominator=sampRate.denominator,
        subdir_cadence_secs=dmr.get_subdir_cadence_secs(),  # Number of seconds of data in a subdirectory
        file_cadence_millisecs=dmr.get_file_cadence_secs()*1000,  # Each file will have up to 400 ms of data
        compression_level=0,  # no compression
        checksum=False,  # no checksum
#        uuid_str= dataDict['uuid_str'],
        uuid_str = '920cecde7dc24e9d98ca9b4b6e52255f',
        marching_periods=False,  # no marching periods when writing
    )
    vsmeta_init_dict = dict(
        subdir_cadence_secs=3600,
        file_cadence_secs=1,
        sample_rate_numerator=sampRate.numerator,
        sample_rate_denominator=sampRate.denominator,
        file_name="vsinfo",
    )
    cmeta_init_dict = dict(
        subdir_cadence_secs=dmr.get_subdir_cadence_secs(),
        file_cadence_secs=dmr.get_file_cadence_secs(),
        sample_rate_numerator=sampRate.numerator,
        sample_rate_denominator=sampRate.denominator,
        file_name="metadata",
    )
    read_list = [{}] * len(drf_list)
    t_bnds = [np.ones(len(drf_list)), np.ones(len(drf_list))]
    # Data set loop reads them into structured dictionaries before downsampling
    printfunc("Extracting data from the follwing datasets:")
    for idrf, drf_dir in enumerate(drf_list):
        printfunc(f"Dataset {idrf}: {drf_dir}")
        idict = dict()
        drfObj = drf.DigitalRFReader(drf_dir)
        idict["drfObj"] = drfObj
        idict["chans"] = drfObj.get_channels()
        idict["bnds"] = drfObj.get_bounds(idict["chans"][0])

        props = drfObj.get_properties(idict["chans"][0])
        idict["props"] = props
        idict["sr_x"] = Fraction(
            props["sample_rate_numerator"], props["sample_rate_denominator"]
        )
        idict["bndtime"] = np.array(idict["bnds"]) / float(idict["sr_x"])
        idict["ds"] = sampRate / idict["sr_x"]
        # get the VSMeta data
        t_bnds[0][idrf] = idict["bndtime"][0]
        t_bnds[1][idrf] = idict["bndtime"][1]
        metadir = Path(path).joinpath("metadata")
        meta = drf.DigitalMetadataReader(str(metadir))
        metad = meta.read_flatdict()
        del metad["index"]
        idict["metad"] = metad
        idict["md"] = drfObj.get_digital_metadata(idict["chans"][0]).read_flatdict()
        cf_r = idict["md"]["center_frequencies"][0]
        read_list[idrf] = idict
    for inum, irow in sched_df.iterrows():
        dirname = f"iono_{int(irow['freq kHz'])}khz"
        curpath = out_proto.joinpath(dirname)
        st_ut = irow["start"]
        et_ut = irow["end"]
        # figure out which drf dataset the transmission is in.
        log1 = np.logical_and(st_ut >= t_bnds[0], st_ut < t_bnds[1])
        pos = np.where(log1)[0]
        if pos.size == 1:
            idict = read_list[pos[0]]
        else:
            printfunc(f"Could not find any data for {irow}")
            continue

        sr_x = idict["sr_x"]
        printfunc(f"Signal {inum} of {nrows} in directory: {dirname}")
        curpath.mkdir(parents=True, exist_ok=True)
        st_samp = drf.util.time_to_sample(max(0,int(st_ut) - 1), int(idict["sr_x"]))
        st_samp = max(st_samp, idict["bnds"][0])
        end_samp = drf.util.time_to_sample(et_ut, int(sr_x))

        tx_cf = irow["freq kHz"] * 1e3
        st_ind = int(idict["ds"] * st_samp)

        # Set up vsmetadata
        vsmetapath = curpath.joinpath("vsmetadata")
        vsmetapath.mkdir(parents=True, exist_ok=True)
        vsmeta_init_dict["metadata_dir"] = str(vsmetapath)
        vsinfo = drf.DigitalMetadataWriter(**vsmeta_init_dict)
        vsinfo.write(st_ind, idict["metad"])
        sec_tot = et_ut - st_ut
        nreads = max(5, int(sec_tot))

        tr_bnds = (st_samp, end_samp)
        # HACK there's center_frequencies and receiver/center_freqs should I change both?
        cf_r = idict["md"]["center_frequencies"][0]
        cf_lims = float(sr_x / 2) - float(sampRate / 2)
        band_edge = np.array([-cf_lims, cf_lims]) + cf_r

        if band_edge[0] <= tx_cf < band_edge[1]:
            # Deal with edge cases.
            new_cf = tx_cf
        elif tx_cf < band_edge[0]:
            new_cf = band_edge[0]
        else:
            new_cf = band_edge[1]
        f_shift = new_cf - cf_r
        ptime0 = time.time()
        modrs = ModulatorResampler(f_shift, idict["ds"], idict["drfObj"], use_gpu)
        ntype = np.complex64
        """
        printfunc(f"Resampling {sec_tot} seconds of data by {idict['ds']}")
        for ichan in idict["chans"]:
            printfunc(f"processing channel: {ichan}")
            a = modrs.get_start_samples(nreads, ichan, bnds=tr_bnds)
            """
        printfunc(f"Resampling {sec_tot} seconds of data by {idict['ds']}")
        for ichan in idict["chans"]:
            printfunc(f"processing channel: {ichan}")
            ch_bnds = idict["drfObj"].get_bounds(ichan)
            if ch_bnds is None or ch_bnds[0] is None:
                printfunc(f"Skipping non-data directory: {ichan}")
                continue
            a = modrs.get_start_samples(nreads, ichan, bnds=tr_bnds)
            st_samps, mread, m = a
#            p_items = [(ichan, ist, mread, m) for ist in st_samps]
            p_items = [(ichan, ist, mread, m, b * m + st_ind) for b, ist in enumerate(st_samps)]
            ctx = multiprocessing.get_context("spawn")

            cur_chan_path = curpath.joinpath(ichan)
            cur_chan_path.mkdir(parents=True, exist_ok=True)
            chan_meta_dir = cur_chan_path.joinpath("metadata")
            chan_meta_dir.mkdir(parents=True, exist_ok=True)

            drf_out = drf.DigitalRFWriter(
                str(cur_chan_path),
                ntype,
                start_global_index=st_ind,
                **drf_op_dict,
            )
            try:
                with ctx.Pool(processes=ncores) as pool:
                    #     data = (pool.map(self.func, range(ns)))
                    outputs = pool.starmap(modrs.dmod_ds_pool, p_items)
                    for b in np.arange(len(st_samps), dtype=np.int_):
                        xout = outputs[b][0].astype(ntype)
                        st_samp_ds = outputs[b][1]
                        nx_samp = st_samp_ds - st_ind
                        drf_out.rf_write(xout, next_sample=nx_samp)

                c_md = copy(idict["md"])
            except IOError as e:
                printfunc(f"IOError: {e}")
                printfunc("Skiping this signal")
                break

            c_md["center_frequencies"] = np.array([new_cf, new_cf])

            del c_md["index"]
            cmeta_init_dict["metadata_dir"] = str(chan_meta_dir)
            chan_meta = drf.DigitalMetadataWriter(**cmeta_init_dict)
            chan_meta.write(st_ind, c_md)
            drf_out.close()
        ptime1 = time.time()
        proc_time = ptime1 - ptime0
        printfunc(f"Time for processing {proc_time} seconds")


def dmod_ds(
    x, sr_x, f_shift, ds_x, mod_off=1 + 0j, dec_filter=("kaiser", 5), use_cupy=True
):
    """Demod and downsample the data

    Parameters
    ----------
    x : array_like
        Data to be demoed and downsampled.
    sr_x : Fraction
        Sampling frequency in fraction form.
    f_shift : float
        Desired frequency shift in Hz.
    beg_samp : int
        Time in number of seconds since unix epoch multiplied by sample rate of data.
    ds_x : Fraction
        Resampling factor, numerator is upsampling, denominator is downsampling.
    mod_off : Complex
        Phase offset from the previous modulator.
    dec_filter : str, tuple, or array_like, optional
        Desired window to use to design the low-pass filter, or the FIR filter
        coefficients to employ.

    Returns
    -------
    x_ds : array_like
        Downsampled and demoded data.
    w_end : float
        The end of the modulation array for the next phase.
    """

    # create the modulation vector
    # Normalize the frquency by
    f_norm = f_shift / float(sr_x)
    # radians per sample
    rps = 2 * np.pi * f_norm
    # Make vector for the phase
    phi = np.arange(len(x) + 1, dtype=float) * rps
    # Find the phase offset by multiplying the radians per sample to first time sample
    # phase_off = rps*beg_samp
    w = np.exp(-1j * phi) * mod_off
    w_end = w[-1]

    if CUPY_INIT and use_cupy:
        x = cp.asarray(x)
        w = cp.asarray(w[:-1])
        if isinstance(dec_filter, np.ndarray):
            dec_filter = cp.asarray(dec_filter)

        x_dmod = x * w
        x_ds = sig_cu.resample_poly(
            x_dmod, ds_x.numerator, ds_x.denominator, window=dec_filter
        )
        x_ds = cp.asnumpy(x_ds)
    else:
        x_dmod = x * w[:-1]
        x_ds = sig.resample_poly(
            x_dmod, ds_x.numerator, ds_x.denominator, window=dec_filter
        )

    return x_ds, w_end

if __name__ == "__main__":
    # test data
    data = {
        'freq kHz': [500],
        'start': [0000000000],
        'end': [120]
    }

    # Create DataFrame
    sched = pd.DataFrame(data)

    # Print the DataFrame
    print(sched)

    # Run the processing script safely
    sig_extract_ds(["/home/kschaars"], "DDCoutput", sched, False, print, Fraction(12000, 1))
