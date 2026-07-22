#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2026 MIT Haystack.
#
# SPDX-License-Identifier: GPL-3.0-or-later
#
# Author: Kevin Schaars
# This is the code for a GNU radio block that takes user inputs and generates a WSPR signal
# that is intended to be part of a 3 part coexistance beacon. However, it can just create a WSPR signal,
# just set centralBeaconFrequency and centerOffset accordingly
import numpy as np
from datetime import datetime
from gnuradio import gr

class WSPR(gr.sync_block):
    """
    docstring for block WSPR
    """
    #Call sign of transmitter, must be a string, must be at least 4 characters, no more than 6, character 3 must be an int
    #Grid locator, must be 4 characters, first two must be letters, second two must be numbers
    #Power is transmitter power in dBm, range 0 - 60
    #Sample rate is the sample rate that the GNU enviroment is set to
    #Center Beacon Frequency is the value of the central tone of a 3 part communication beacon
    #Center offset is the distance in frequency that the WSPR signal is offset from central tone
    #Amplitude is the amplitude of the signal
    def __init__(self, callsign = 'HY5K', locator = "AA11", power = 20, sampleRate = 48000, centerBeaconFreq = 10000, centerOffSet = 10000, amplitude = 1, trueTone = 1000, debug = 0, timing = 0):
        gr.sync_block.__init__(self,
            name="WSPR Generator ",
            in_sig= [],             #This is a signal block, no inputs
            out_sig=[np.complex64]) #Outputs a complex signal
        #Declare Variables
        self.debug = debug
        self.callsign = callsign
        self.locator = locator.upper()
        self.power = power
        self.CBF = centerBeaconFreq
        self.centerOffSet = centerOffSet
        self.amplitude = amplitude
        self.sampleRate = sampleRate
        self.state = 0
        self.last_minute = None
        self.trueTone = trueTone
        self.timing = timing
        self.phase = 0.0                #Initializes phase tracking variable
        #Defines errors to ensure proper variables, not complete
        if self.callsign[2] > '9':
            raise ValueError("The call sign must have a number in the 3rd spot")
        if  len(self.callsign) > 6 or len(self.callsign) < 4:
            raise ValueError("The call sign must contain 4-6 characters")
        if self.locator[0]<= '9' or self.locator[0] > 'R' or self.locator[1] <= '9' or self.locator[1] > 'R':
            raise ValueError("Locator must begin with 2 letters")
        if self.locator[2]> '9' or self.locator[3] > '9':
            raise ValueError("Locator must end with 2 numbers")
        if self.power > 60 or self.power<0:
            raise ValueError("Power must be between 0 and 60 dBm")
        if type(self.callsign) != str:  
            raise ValueError("Callsign must be a string: 'ca1sgn'")
        if type(self.locator) != str:
            raise ValueError("Locator must be a string: 'AA11'")
        if type(self.power) != int and type(self.power) != float:
            raise ValueError("Power must be a number")
        if type(self.CBF) != int and type(self.CBF) != float:
            raise ValueError("Center beacon frequency must be a number")
        if type(self.centerOffSet) != int and type(self.centerOffSet) != float:
            raise ValueError("Center offset must be a number")
        if type(self.amplitude) != int and type(self.amplitude) != float:
            raise ValueError("Amplitude must be a number")
        if type(self.sampleRate) != int and type(self.sampleRate) != float:
            raise ValueError("Sample rate must be a number")
        if self.callsign[1] == '' or self.callsign[1] <= '9':
            raise ValueError("The second char of the callsign must be a letter")
        #Incrementing variables for the output
        self.buffer_index = 0
        self.sampleCount = 0
        #Calls generating function to create encoded signal based on user inputs
        self.symbol_buffer = self.generateSymbols()

   
    def generateSymbols(self):
        # get information varibales for the signal generation
        callsign = self.callsign.upper()
        locator = self.locator
        power = self.power
        # Sync vector that is defined by WSPR protocol. Used to generate symbols 0-3 in
        # the final step of the encoding process
        SYNC = [1,1,0,0,0,0,0,0,1,0,0,0,1,1,1,0,0,0,1,0,0,1,0,1,1,1,1,0,0,0,0,0,0,0,1,0,0,1,0,1,0,0,0,0,0,0,1,0,1,1,0,0,1,1,0,1,0,0,0,1,1,0,1,0,0,0,0,1,1,0,1,0,1,0,1,0,1,0,0,1,0,0,1,0,1,1,0,0,0,1,1,0,1,0,1,0,0,0,1,0,0,0,0,0,1,0,0,1,0,0,1,1,1,0,1,1,0,0,1,1,0,1,0,0,0,1,1,1,0,0,0,0,0,1,0,1,0,0,1,1,0,0,0,0,0,0,0,1,1,0,1,0,1,1,0,0,0,1,1,0,0,0]
       
        #---------Encode Callsign---------
        # pad the callsign with spaces so that it is always 6 characters long
        while len(callsign) < 6:
            callsign = callsign + ' '
        # Encode the callsign in to a 28 bit long binary int
        # If this does not work, increment all values except posVal[0] by 1, the instructions
        # for the encodign process were unclear.
        N = 0
        i = 0
        # Stored number of possible values for each char of the callsign, with 37 total possibilities
        # Initally, all possible values are numbers 0-9, represented by numbers 0-9
        # All letters are represented by numbers 10-35 and the space by 36
        # the first char can be any of the values, so the firts value is multiplied by 36
        # the second char has to be a number, so 9 possible values
        # all follwig chars can only be letters or a space, so they get shifted down in value by 10,
        # making 'A' = 0 and ' ' = 26
        posVal = [1,36,10,27,27,27]
        for char in callsign:
            if char == ' ':
                if i < 3:
                    V = 36      #Only valued at 36 when there are possible numbers
                else:
                    V = 26
            elif '0' <= char <= '9':
                V = ord(char) - ord('0')
            elif 'A' <= char <= 'Z':
                if i < 3:
                    V = ord(char) - ord('A') + 10 #'A is valued at 10 when numbers are possible
                else:
                    V = ord(char) - ord('A') #A becomes lowest value when no numbers
            else:
                V = 36 # Handle unexpected characters
            N = (N * posVal[i]) + V #takes form of (((((N1 * 36) + N2)*9 + N3)*26 + N4)*26 + N5)*26 + N6
            i += 1
        callsignNum = N #callsign is now a 28 bit binary int
        if self.debug != 0: 
            print("Callsign Num:")
            print(bin(callsignNum))
            print(len(bin(callsignNum))-2)
        # --------- Encode Locator and power into a 22 bit binary int ---------
        locator = locator.upper()
        # This is honeslty just how the WSPR document I found did it, I am not sure why but it outputs
        # a 15 bit binary int. A and 0 are the base values (the 0) for their respective parts of the
        # locator and thats why their value is subtracted from the locator char
        locatorNum = (179-10*(ord(locator[0])-ord('A'))-(ord(locator[2])-ord('0')))*180 + 10*((ord(locator[1])-ord('A')) + (ord(locator[3])-ord('0')))
        diff15 = 15 - len(bin(locatorNum)) - 2
        #Combine locator and power. shift the locator binary by 7 bits and add power into the 7 empy bits
        # WSPR protocol adds 64 to the power so that it is 7 bits. Max value is 60 dBm
        locPower = locatorNum*128 + (power+64)
        if self.debug != 0: 
            print("locPower:") 
            print(f"{locPower:b}")
        #combine callsign, locator and power into 1 50 bit binary integer
        data = callsignNum*(2**22) + locPower
        if self.debug != 0: 
            print("data:")
            print(f"{data:b}")
            print(len(bin(data))-2)
        #pad with 31 0's
        binaryString = data << 31  
        if self.debug != 0: 
            print(len(bin(binaryString))-2)
            print(bin(binaryString))
        #binaryString at this point should be 81 bits long. If leading 0's are dropped that is
        # fixed later in the program
       
        # ---------- Convoplution encoding ----------
        #WSPR defined convolution constants, both are 32 bits which ensures only looking at max 32 bits per the protocol
        G1 = 0xF2D05351
        G2 = 0xE4613C47
        #convolution encoding though parity generation
        output = 0  
       
        for i in range(81):
            # Simpulate passing the encoded information into a 32 bit register
            reg = binaryString >> (80 - i) # Start with the MSB by shifting by 80, and shifting one less each iteration
            parity0 = (reg & G1).bit_count() % 2 # and with constant, get number of 1's though bit count, then mod 2 to get odd or even count
            parity1 = (reg & G2).bit_count() % 2
            # Add bits in order reg0, reg 1. use bitwise or to add parity bits to two empty bits of output stream
            output = (output << 2) | (parity0 << 1) | parity1
        #output should be 162 bit binary int
        #---------- Interleaving ----------
        i = 0x00        # Iterates through adresses 0-255
        p = 0           # Counts number of sucessful interleave operations until all values are interleaved (162)
        #convert to a binary string to allow indexing
        outputString = bin(output)[2:]
        # Add leading 0's back to the information that get truncated by python int
        # Works becuase the convolution encoding will output 0's until it detects its first 1
        while len(outputString) < 162:
            outputString = '0' + outputString
        #Initialize final output data array, all 5's should be replaced by the end of the interleaving
        if self.debug != 0: 
            print("convolution:") 
            print(outputString)
        D = [5]*len(outputString)
        while p < 162:
            reversedI = int(f"{i:08b}"[::-1], 2) # bit reverse i
            # if the value of the reversed adress is less than 162 (a valid adress in D), assign the value at the reversed adress in D
            # the value of the data at the origional adress p.
            if reversedI < 162:
                D[reversedI] = outputString[p]
                p += 1  # Increment p to get the next value in the origional array
            i += 1      # Always increment i to skip invalid adresses
           
        # ---------- Merge data with sync ----------
        # Generate symbols matrix for value 0-3 for final output
        if self.debug != 0: 
            print("interleaved:")
            print(D)
        symbols = [5]*162
        for n in range(len(SYNC)):
            symbols[n] = SYNC[n] + 2*int(D[n],2) #generates values 0-3 to modulate output frequency
        timePerSymbol = 0.6826666       
        self.numSamplesTX = int(timePerSymbol*self.sampleRate)
        if self.trueTone == 0: 
            self.toneSpacing = 1.46484375
        else: 
            self.toneSpacing = self.trueTone
        self.lastIndex = 5
        self.indexPrint = 1
        if self.debug != 0: 
            print("symbols:")
            print(len(symbols))
            print(symbols)
            print("Num. Sampl. TX:") 
            print(self.numSamplesTX)
        return symbols
           
    def work(self, input_items, output_items):
        out = output_items[0]
        noutput_items = len(out)
        
        # 1. Handle your minute-rollover state logic
        if self.state == 0:
            self.now = datetime.now()
            self.current_minute = self.now.minute
            if self.last_minute is not None and self.last_minute != self.current_minute:
                if self.current_minute % 2 == 0 or self.timing != 0: 
                    self.state = 1 
                    self.buffer_index = 0
                    self.sampleCount = 0
        self.last_minute = self.current_minute

        # Track how many samples we have written into the output buffer so far
        n_written = 0
        
        # Fill the entire output buffer requested by GNU Radio
        while n_written < noutput_items:
            if self.state == 1 or self.timing != 0:
                if self.buffer_index < len(self.symbol_buffer):
                    # How many samples does the current WSPR symbol still need?
                    samples_needed_for_symbol = self.numSamplesTX - self.sampleCount
                    # How much space is left in the current GNU Radio output buffer?
                    space_left_in_buffer = noutput_items - n_written
                    
                    # Determine the size of the next contiguous chunk to process
                    chunk_size = min(samples_needed_for_symbol, space_left_in_buffer)
                    
                    # Calculate frequency and phase steps for the current symbol
                    current_symbol = self.symbol_buffer[self.buffer_index]
                    freqOffSet = (current_symbol - 1.5) * self.toneSpacing
                    phaseIncrement = (2.0 * np.pi * (self.CBF + self.centerOffSet + freqOffSet)) / self.sampleRate
                    
                    # VECTORIZED GENERATION: No python loops!
                    t = np.arange(chunk_size)
                    chunk_phases = self.phase + (t * phaseIncrement)
                    
                    # Compute the complex exponential for the entire chunk at once
                    out[n_written : n_written + chunk_size] = self.amplitude * np.exp(1j * chunk_phases)
                    
                    # Update tracking variables for the next iteration/call
                    self.phase = (chunk_phases[-1] + phaseIncrement) % (2.0 * np.pi)
                    self.sampleCount += chunk_size
                    n_written += chunk_size
                    
                    # Advance to the next WSPR symbol if this one is finished
                    if self.sampleCount >= self.numSamplesTX:
                        self.buffer_index += 1
                        self.sampleCount = 0
                else:
                    # All symbols sent, fill the remaining space with zeros
                    out[n_written:] = 0 + 0j
                    self.state = 0
                    n_written = noutput_items
            else: 
                # Idle state, fill the remaining space with zeros
                out[n_written:] = 0 + 0j
                n_written = noutput_items
            
        return noutput_items





