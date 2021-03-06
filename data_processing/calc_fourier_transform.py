"""
Filename:     calc_fourier_transform.py
Author:       Damien Irving, irving.damien@gmail.com
Description:  Calculate Fourier transform

"""

# Import general Python modules

import sys, os, pdb
import argparse
import numpy, math
import xarray
from scipy import fftpack
from scipy import signal
from copy import deepcopy

# Import my modules

cwd = os.getcwd()
repo_dir = '/'
for directory in cwd.split('/')[1:]:
    repo_dir = os.path.join(repo_dir, directory)
    if directory == 'climate-analysis':
        break

modules_dir = os.path.join(repo_dir, 'modules')
sys.path.append(modules_dir)

try:
    import general_io as gio
    import convenient_universal as uconv
except ImportError:
    raise ImportError('Must run this script from anywhere within the climate-analysis git repo')


# Define functions
    
def filter_signal(signal, indep_var, min_freq, max_freq, exclusion, real=False):
    """Filter a signal by performing a Fourier Tranform and then
    an inverse Fourier Transform for a selected range of frequencies"""
    
    sig_fft, sample_freq = fourier_transform(signal, indep_var)
    filtered_signal = inverse_fourier_transform(sig_fft, sample_freq, min_freq=min_freq, max_freq=max_freq, exclude=exclusion)
    
    if real:
        filtered_signal = filtered_signal.real
    
    return filtered_signal


def fourier_transform(signal, indep_var):
    """Calculate the Fourier Transform.
    
    Args:
      signal (numpy.ndarray): Data to be transformed 
      indep_var (list/tuple): Independent variable (i.e. 1 dimensional time axis or longitude axis)
    
    Returns:
      sig_fft (numpy.ndarray): Coefficients obtained from the Fourier Transform
      freqs (numpy.ndarray): Wave frequency associated with each coefficient
    
    """
    
    spacing = indep_var[1] - indep_var[0]
    sig_fft = fftpack.fft(signal)
    sample_freq = fftpack.fftfreq(len(indep_var), d=spacing) * len(indep_var) * spacing  #units = cycles per length of domain
    sample_freq = numpy.resize(sample_freq, sig_fft.shape)
    
    return sig_fft, sample_freq


def inverse_fourier_transform(coefficients, sample_freq, 
                              min_freq=None, max_freq=None, exclude='negative'):
    """Inverse Fourier Transform.
    
    Args:
      coefficients (numpy.ndarray): Coefficients obtained from the Fourier Transform
      sample_freq (numpy.ndarray): Wave frequency associated with each coefficient
      max_freq, min_freq (float, optional): Exclude values outside [min_freq, max_freq]
        frequency range. (Note that this filtering keeps both the positive and 
        negative half of the spectrum)
      exclude (str, optional): Exclude either the 'positive' or 'negative' 
        half of the Fourier spectrum. (A Hilbert transform, for example, excludes 
        the negative part of the spectrum)
                                 
    """
    
    assert exclude in ['positive', 'negative', None]
    
    coefs = deepcopy(coefficients)  # Deep copy to prevent side effects
                                    # (shallow copy not sufficient for complex
                                    # things like numpy arrays)
    
    if exclude == 'positive':
        coefs[sample_freq > 0] = 0
    elif exclude == 'negative':
        coefs[sample_freq < 0] = 0
    
    if (max_freq == min_freq) and max_freq:
        coefs[numpy.abs(sample_freq) != max_freq] = 0
    
    if max_freq:
        coefs[numpy.abs(sample_freq) > max_freq] = 0
    
    if min_freq:
        coefs[numpy.abs(sample_freq) < min_freq] = 0
    
    result = fftpack.ifft(coefs)
    
    return result


def first_localmax_index(data):
    """Return index of first local maxima. 

    If there is no local maxima (e.g. if all the values are zero), 
    it will simply return zero.

    """
    localmax_indexes = signal.argrelextrema(data, numpy.greater, mode='wrap')

    if localmax_indexes[0].size > 0:
        return localmax_indexes[0][0]
    else:
        return 0


def _get_coefficients(data, lon_axis, 
                      min_freq, max_freq,
                      long_name, units,
                      outdata_dict):
    """Calculate magnitude and phase coefficients for each frequency."""

    exclusion = None
    for freq in range(min_freq, max_freq + 1):
        filtered_signal = numpy.apply_along_axis(filter_signal, -1, 
                                                 data, lon_axis, 
                                                 freq, freq, 
                                                 exclusion, real=True)

        localmax_vals = numpy.max(filtered_signal, axis=-1)
        localmax_indexes = numpy.apply_along_axis(first_localmax_index, -1, filtered_signal)
        localmax_lons = map(lambda x: lon_axis[x], localmax_indexes)
        
        outdata_dict['wave'+str(freq)+'_amp'] = (localmax_vals, _coefficient_atts('amp', freq, long_name, units))
        outdata_dict['wave'+str(freq)+'_phase'] = (localmax_lons, _coefficient_atts('phase', freq, long_name, units))

    return outdata_dict


def _coefficient_atts(ctype, freq, orig_long_name, units):
    """Get the attributes for the coefficient output variable."""
    
    assert ctype in ('amp', 'phase')
    
    method = 'filtered'
    if ctype == 'amp':
        name = 'amplitude_of_'+method+'_'+orig_long_name
    elif ctype == 'phase':
        name = 'first_local_maxima_of_'+method+'_'+orig_long_name,

    atts = {'standard_name': name,
            'long_name': name,
            'units': units,
            'notes': _get_filter_text(method, freq, freq)}

    return atts


def extract_data(dset, inargs):
    """Extract the data from the input file."""

    subset_dict = gio.get_subset_kwargs(inargs)
    darray = dset[inargs.var].sel(**subset_dict)
    
    long_name = str(darray.attrs['long_name'])
    units = str(darray.attrs['units'])

    if inargs.avelat:
        darray = darray.mean('latitude')

    assert darray.dims[-1] == 'longitude', \
    'This script is setup to perform the fourier transform along the longitude axis'

    if inargs.valid_lon:
        start_lon, end_lon = inargs.valid_lon
        lon_vals = numpy.array([start_lon, end_lon, darray['longitude'].values.min()])          
        assert numpy.sum(lon_vals >= 0) == 3, "Longitudes must be 0 to 360" 
        darray.loc[dict(longitude=slice(0, start_lon))] = 0
        darray.loc[dict(longitude=slice(end_lon, 360))] = 0

    return darray, long_name, units


def _filter_data(data, lon_axis,
                 min_freq, max_freq,
                 var, long_name, units, 
                 outtype, outdata_dict):
    """Filter data.
    
    Can perform either a hilbert transform (i.e. inverse Fourier transform 
    for wavenumbers of interest) or go one step further and calculate the 
    wave envelope.
    
    """

    assert outtype in ['envelope', 'hilbert']

    if outtype == 'envelope':
        exclusion = 'negative'
        method_short = 'env'
        method_long = 'wave_envelope'
    elif outtype == 'hilbert':
        exclusion = None
        method_short = 'ift'
        method_long = 'inverse_fourier_transformed'

    outdata = numpy.apply_along_axis(filter_signal, -1, 
                                     data, lon_axis, 
                                     min_freq, max_freq, 
                                     exclusion)
    if outtype == 'envelope':
        outdata = 2 * numpy.abs(outdata)
    else:
        outdata = outdata.real
   
    filter_text = _get_filter_text(method_long, min_freq, max_freq)
    atts = {'standard_name': method_long+'_'+long_name,
            'long_name': method_long+'_'+long_name,
            'units': units,
            'notes': filter_text}

    outdata_dict[method_short+var] = (outdata, atts)

    return outdata_dict


def _get_filter_text(method, min_freq, max_freq):
    """Get the notes attribute text according to the analysis
    method and frequency range."""

    filter_text = '%s with frequency range: %s to %s' %(method, min_freq, max_freq)
 
    return filter_text


def spectrum(signal_fft, freqs, scaling='amplitude', variance=None):
    """Calculate the spectral density for a given Fourier Transform.
    
    Args:
      signal_fft, freqs (numpy.ndarray): Typically the output of fourier_transform()
      scaling (str, optional): Choices for the amplitude scaling for each frequency
        are as follows (see Wilks 2011, p440):
         'amplitude': no scaling at all (C)
         'power': sqaure the amplitude (C^2)
         'R2': variance explained = [(n/2)*C^2] / (n-1)*variance^2, 
         where n and variance are the length and variance of the 
         orignal data series (R2 = the proportion of the variance 
         explained by each harmonic)    

    """

    assert scaling in ['amplitude', 'power', 'R2']
    if scaling == 'R2':
        assert variance, \
        "To calculate variance explained must provide variance value" 
        
    if len(signal_fft.shape) > 1:
        print "WARNING: Ensure that frequency is the final axis"
    
    # Calculate the entire amplitude spectrum
    n = signal_fft.shape[-1]
    amp = numpy.abs(signal_fft) / n
    
    # The positive and negative half are identical, so just keep positive
    # and double its amplitude
    freq_limit_index = int(math.floor(n / 2)) 
    pos_amp = 2 * numpy.take(amp, range(1, freq_limit_index), axis=-1)
    pos_freqs = numpy.take(freqs, range(1, freq_limit_index), axis=-1)
    
    if scaling == 'amplitude':
        result = pos_amp
    elif scaling == 'power':
        result = (pos_amp)**2
    elif scaling == 'R2':
        result = ((n / 2) * (pos_amp**2)) / ((n - 1) * (variance))
    
    return result, pos_freqs


def count_sign_change(data):
    """Count the number of times the data series changes sign.
    
    Works by determining the sign of all the values (-1, 0 or 1)
      and then replaces zeros with the next non-zero value, since
      -1 to/from 0 or 1 to/from 0 changes do not count as a sign
      change in this context.
    
    """

    assert data.ndim == 1, "Input array must be one dimensional"

    signs = numpy.sign(data)
    
    counter = -2
    while signs[-1] == 0:
        signs[-1] = signs[counter]
        counter = counter - 1   
        
    for i in range(len(signs)):
        counter = 1
        while signs[i] == 0:
            signs[i] = signs[i+counter]
            counter = counter + 1
    
    diffs = numpy.abs(numpy.diff(signs))
    change_count = numpy.sum(diffs == 2)
    
    return change_count


def _get_sign_change(data, outdata_dict):
    """ """

    sign_change_data = numpy.apply_along_axis(count_sign_change, -1, data)

    sign_change_atts = {'standard_name': 'sign_change_count',
                        'long_name': 'sign_change_count',
                        'units': '',
                        'notes': 'count of number of times signal sign (pos/neg) changed'}

    outdata_dict['sign_count'] = (sign_change_data, sign_change_atts)

    return outdata_dict


def _get_env_max(data, lon_axis,
                 min_freq, max_freq,
                 units, outdata_dict):
    """Get the maximum envelope value."""

    outdata = numpy.apply_along_axis(filter_signal, -1, 
                                     data, lon_axis, 
                                     min_freq, max_freq, 
                                     'negative')
    outdata = numpy.max(2 * numpy.abs(outdata), axis=-1)
    
    method_note = 'maximum value of wave envelope'
    filter_text = _get_filter_text(method_note, min_freq, max_freq)
    atts = {'standard_name': 'envelope_maximum',
            'long_name': 'envelope_maximum',
            'units': units,
            'notes': filter_text}

    outdata_dict['env_max'] = (outdata, atts)

    return outdata_dict


def main(inargs):
    """Run the program."""
    
    # Read the data
    dset_in = xarray.open_dataset(inargs.infile)
    gio.check_xarrayDataset(dset_in, inargs.var)
    darray, long_name, units = extract_data(dset_in, inargs)

    # Perform task
    outdata_dict = {}
    if inargs.outtype == 'coefficients':
        outdata_dict = _get_coefficients(darray.values, darray['longitude'].values, 
                                         inargs.min_freq, inargs.max_freq,
                                         long_name, units, outdata_dict)
        if inargs.sign_change:
            outdata_dict = _get_sign_change(darray.values, outdata_dict)

        if inargs.env_max:
            env_max_min_freq, env_max_max_freq = inargs.env_max
            outdata_dict = _get_env_max(darray.values, darray['longitude'].values,
                                        env_max_min_freq, env_max_max_freq,
                                        units, outdata_dict)
        dims = darray.dims[:-1]
    else:
        outdata_dict = _filter_data(darray.values, darray['longitude'].values, 
                                    inargs.min_freq, inargs.max_freq,
                                    inargs.var, long_name, units, 
                                    inargs.outtype, outdata_dict)
        dims = darray.dims
        
    # Write the output file
    d = {}
    for dim in dims:
        d[dim] = darray[dim]

    for outvar in outdata_dict.keys(): 
        d[outvar] = (dims, outdata_dict[outvar][0])

    dset_out = xarray.Dataset(d)

    for outvar in outdata_dict.keys(): 
        dset_out[outvar].attrs = outdata_dict[outvar][1]

    gio.set_global_atts(dset_out, dset_in.attrs, {inargs.infile: dset_in.attrs['history'],})
    dset_out.to_netcdf(inargs.outfile)


if __name__ == '__main__':

    extra_info =""" 
example (vortex.earthsci.unimelb.edu.au):
    /usr/local/uvcdat/1.5.1/bin/cdat calc_fourier_transform.py 
    va_Merra_250hPa_30day-runmean-Jun2002_r360x181.nc va test.nc 
    --filter 2 9 --outtype hilbert
author:
    Damien Irving, d.irving@student.unimelb.edu.au
notes:
    Note that the Hilbert transform excludes the negative half 
    of the frequency spectrum and doubles the final amplitude. This does not
    give the same result as if you simply retain the negative half.
references:
    http://docs.scipy.org/doc/numpy/reference/routines.fft.html
    http://gribblelab.org/scicomp/09_Signals_sampling_filtering.html
    
"""

    description='Perform Fourier Transform along lines of constant latitude'
    parser = argparse.ArgumentParser(description=description,
                                     epilog=extra_info, 
                                     argument_default=argparse.SUPPRESS,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)

    parser.add_argument("infile", type=str, help="Input file name")
    parser.add_argument("var", type=str, help="Input file variable")
    parser.add_argument("outfile", type=str, help="Output file name")
    parser.add_argument("min_freq", type=int, help="Minimum frequency to retain")
    parser.add_argument("max_freq", type=int, help="Maximum frequency to retain (can equal min_freq for single freq)")
    parser.add_argument("outtype", type=str, choices=('hilbert', 'coefficients', 'envelope'),
                        help="Output can be a hilbert transform (i.e. inverse Fourier transform), wave envelope or magnitude and phase coefficients for each freq")
    
    parser.add_argument("--latitude", type=float, nargs=2, metavar=('START', 'END'),
                        help="Latitude range over which to perform Fourier Transform [default = entire]")
    parser.add_argument("--valid_lon", type=float, nargs=2, metavar=('START', 'END'), default=None,
                        help="Longitude range over which to perform Fourier Transform (all other values are set to zero) [default = entire]")
    parser.add_argument("--time", type=str, nargs=2, metavar=('START_DATE', 'END_DATE'),
                        help="Time period [default = entire]")

    parser.add_argument("--avelat", action="store_true", default=False,
                        help="Average the data over the latitude axis before performing Fourier transform")

    parser.add_argument("--sign_change", action="store_true", default=False,
                        help="for a coefficients outtype, add an extra output variable which represents the count of times the signal changes sign")
    parser.add_argument("--env_max", type=int, nargs=2, metavar=('MIN_FREQ', 'MAX_FREQ'), default=None,
                        help="for a coefficients outtype, add an extra output variable for the maximum envelope value") 


    args = parser.parse_args()            

    print 'Input files: ', args.infile
    print 'Output file: ', args.outfile  

    main(args)
