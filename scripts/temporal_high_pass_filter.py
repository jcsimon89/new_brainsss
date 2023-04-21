## from Luke's brainsss repository

import os
import sys
import numpy as np
import argparse
import subprocess
import json
import nibabel as nib
import h5py
import datetime
import matplotlib.pyplot as plt
from time import time
from time import strftime
from time import sleep
from scipy.ndimage import gaussian_filter1d

sys.path.append(os.path.split(os.path.dirname(__file__))[0])
import brainsss

def main(args):
    
    load_directory = args['load_directory']
    save_directory = args['save_directory']
    brain_files = args['brain_file']
    stepsize = 2
    rerun_hpass = False #if false will check if hp files already exist. 
    for brain_file in brain_files:
        full_load_path = os.path.join(load_directory, brain_file)
        save_file = os.path.join(save_directory, brain_file.split('.')[0] + '_highpass.h5')

        #####################
        ### SETUP LOGGING ###
        #####################

        width = 120
        logfile = args['logfile']
        printlog = getattr(brainsss.Printlog(logfile=logfile), 'print_to_log')

        #################
        ### HIGH PASS ###
        #################

        printlog("Beginning high pass")
        printlog("this should be the full path")
        printlog(str(full_load_path))
        with h5py.File(full_load_path, 'r') as hf:
            data = hf['data'] # this doesn't actually LOAD the data - it is just a proxy
            dims = np.shape(data)
            printlog("Data shape is {}".format(dims))

            steps = list(range(0,dims[-1],stepsize))
            steps.append(dims[-1])

            with h5py.File(save_file, 'w') as f:
                dset = f.create_dataset('high pass filter data', dims, dtype='float32', chunks=True) 

                for chunk_num in range(len(steps) - 1):
                    t0 = time()
                    #if chunk_num + 1 <= len(steps)-1:
                    chunkstart = steps[chunk_num]
                    chunkend = steps[chunk_num + 1]
                    chunk = data[:,:,chunkstart:chunkend,:]
    #                 chunk_mean = np.mean(chunk,axis=-1)

                    ### SMOOTH ###
                    t0 = time()
                    smoothed_chunk = gaussian_filter1d(chunk,sigma=200,axis=-1,truncate=1)

                    ### Apply Smooth Correction ###
                    t0 = time()
                    chunk_high_pass = chunk - smoothed_chunk 

                    ### Save ###
                    t0 = time()
                    f['high pass filter data'][:,:,chunkstart:chunkend,:] = chunk_high_pass

        printlog("high pass done")

if __name__ == '__main__':
    main(json.loads(sys.argv[1]))
