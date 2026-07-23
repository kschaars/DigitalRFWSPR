Binary_To_DigitalRF is a command line python program that takes a binary audio file and converts it to Digital RF 

Example command line call: python Binary_To_DigitalRF.py /path/to/binary/file ./output/B2DRF_Output     --dtype complex64     --sample-rate 15000000     --center-freq 0     --start "2026-07-22T16:00:00
Z"

Saves into one channel, one file, and each sub file is 1 second long. Time stamps are calculated off of user's UNIX time
