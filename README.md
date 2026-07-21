##### README for digitalRFWSPRDecoder.py: 

This program was written by Kevin Schaars under MIT Haystack Obsevatory based on DDC code from John Swoboda.
The purpose is to take in a set of digital RF data to decode a WSPR like beacon signal. 
This is done by down converting the digital RF data to a temporary .wav file, which is then read by digitalRFWSPRD and the decoded information is printed. 
Command-line Parameters: 
* Path to directory that contains the channel directory to be decoded
  * If data is recorded on the mep, this is the directory above folders such as ChA - ChD
  * Otherwise, it is the path to the directory above the directory that contains the drf_properties.h5 file (also true for the mep)
  * If the sample is downloaded from this repository, this path should 
