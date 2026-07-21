##### README for digitalRFWSPRDecoder.py: 

This program was written by Kevin Schaars under MIT Haystack Obsevatory based on DDC code from John Swoboda.
The purpose is to take in a set of digital RF data with at least 4 minutes of samples and decode a WSPR like beacon signal. 
This is done by down converting the digital RF data to a temporary .wav file, which is then read by digitalRFWSPRD and the decoded information is printed. 
Command-line Parameters: 
* Path to directory that contains the channel directory to be decoded
  * If data is recorded on the mep, this is the directory above folders such as ChA - ChD
  * Otherwise, it is the path to the directory above the directory that contains the drf_properties.h5 file (also true for the mep)
  * If the sample is downloaded from this repository, this path should be to whatever directory contains the directory "TestSamples," as TestSamples is your "channel"
* Name of the channel to be decoded
 * Look at desciption of a channel above
*  Booolean (True/False) to use GPU when running the program
*  A list formatted [center, min, max] of where the program should try to decode first
*  Value for sweep variable
 * If set to 0, will only try to decode input rang
 * If set to 1 or 2, will try to decode in range from 200Hz - 5800Hz in 160Hz windows with the center frequency incrementing by 80Hz
  * If set to 1, will stop at first sucessful decode which may not be the origional signal
  * If set to 2, will go through whole range and print any instance of a sucessful decoding

With how the program is currently written, using high sample rate digital RF does not work due to how the DDC is implemented 

This outputs: 
* The time it took to decode the .wav file
* The snr of the recived signal
* The time delay of the signal
* The center frequency of the decoded signal
* The drift of the signal
* The encoded message (Callsign, locator, power)

This decoder works for signals that are encoded using the WSPR standard but do not have to match the time or frequency standards of the signal. 
For this to work, ensure that the digital RF data set contains at least 4 minutes of data and is down sampled to at most 2MHz sample rate before input to the program. 
