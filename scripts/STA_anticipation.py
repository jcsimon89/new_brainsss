## use hdf5 zscore file generated by processing code to get 
## light triggered average
##other things needed: xml file, voltage file (for light pulses)

## IMPORT
import os
import sys
import numpy as np
import argparse
import subprocess
import json
import time
import csv as csv
from scipy.ndimage import gaussian_filter1d
from scipy.interpolate import interp1d
from sklearn.cluster import AgglomerativeClustering
from sklearn.feature_extraction.image import grid_to_graph
from sklearn.linear_model import RidgeCV
from matplotlib import pyplot as plt
from xml.etree import ElementTree as ET

import scipy as scipy
from scipy.signal import find_peaks
import nibabel as nib
import h5py

import pickle
import psutil


##data files

date = '20210806'
folder_path = "/oak/stanford/groups/trc/data/Ashley2/imports/"

dataset_path = os.path.join(folder_path, date)

window = 20  #may want to change this to be specific for the length of the interval

#################FUNCTIONS ######################
## get data out of voltage file     
#get just diode column
def get_diode_column(raw_light_data):
    """light data should be single fly and have the header be the first row"""
    header = raw_light_data[0]
    diode_column = []
    for i in range(len(header)):
        if 'diode' in header[i]:
            diode_column = i
    reshape_light_data = np.transpose(raw_light_data[1:])
    column = reshape_light_data[:][diode_column] #don't want header anymore
    column = [float(i) for i in column] #for some reason it was saved as string before
    return column


## get xml timestamps
def load_timestamps(directory, file='functional.xml'):
    """ Parses a Bruker xml file to get the times of each frame, or loads h5py file if it exists.
    First tries to load from 'timestamps.h5' (h5py file). If this file doesn't exist
    it will load and parse the Bruker xml file, and save the h5py file for quick loading in the future.
    Parameters
    ----------
    directory: full directory that contains xml file (str).
    file: Defaults to 'functional.xml'
    Returns
    -------
    timestamps: [t,z] numpy array of times (in ms) of Bruker imaging frames.
    """
    try:
        print('Trying to load timestamp data from hdf5 file.')
        with h5py.File(os.path.join(directory, 'timestamps.h5'), 'r') as hf:
            timestamps = hf['timestamps'][:]

    except:
        print('Failed. Extracting frame timestamps from bruker xml file.')
        xml_file = os.path.join(directory, file)
        tree = ET.parse(xml_file)
        root = tree.getroot()
        timestamps = []
        
        sequences = root.findall('Sequence')
        for sequence in sequences:
            frames = sequence.findall('Frame')
            for frame in frames:
                filename = frame.findall('File')[0].get('filename')
                time = float(frame.get('relativeTime'))
                timestamps.append(time)
        timestamps = np.multiply(timestamps, 1000)

        if len(sequences) > 1:
            timestamps = np.reshape(timestamps, (len(sequences), len(frames)))
        else:
            timestamps = np.reshape(timestamps, (len(frames), len(sequences)))

        ### Save h5py file ###
        with h5py.File(os.path.join(directory, 'timestamps.h5'), 'w') as hf:
            hf.create_dataset("timestamps", data=timestamps)
    
    print('Success.')
    return timestamps

def get_z_timestamps(timestamps, z):
    """get each timestamp for a particular z"""
    z_timestamps = []
    for t_slice in timestamps:
        z_timestamps.append(t_slice[z])
    z_timestamps = np.array(z_timestamps)
    return z_timestamps

# ##---> will still need to get timestamps in seconds and bruker framerate
# z_time_mean = np.mean(z_timestamps[1:] - z_timestamps[:-1])
# bruker_framerate = 1000/z_time_mean #f/s
# z_timestamps_s = z_timestamps/1000

def get_time_since_pulse(z_timestamps_s, light_peaks_adjusted):
    """input = timestamps for particular z in seconds and light_peaks_adjusted 
    which is light peaks in seconds.
    output = array for the particular z that finds the time post light pulse for each z timepoint
    if the time is before the first light pulse then it will have a -1 flag"""
    time_since_pulse_vector = []
    for z_time in z_timestamps_s:
        if z_time > light_peaks_adjusted[0]:
            each_time_since_pulse = z_time - light_peaks_adjusted[z_time - light_peaks_adjusted > 0].max()
        else: #needed to keep the lengths the same
            each_time_since_pulse = -1  #as a flag for earyl responses
        time_since_pulse_vector.append(each_time_since_pulse)
    return time_since_pulse_vector

###########################################################

fly_names = []
files = os.listdir(dataset_path)
for i in range(len(files)):
    if '.txt' not in files[i] and 'nii' not in files[i]: #get rid of non-directory things
        fly_names.append(files[i])
        print (files[i])
print('file name list', fly_names)

#run through all flies

for fly in fly_names:
    fly_path = os.path.join(dataset_path, fly)
    fly_zscore_list = [] #should reset for every fly
    for name in os.listdir(fly_path):
        if 'MOCO' in name:
            fly_zscore_list.append(name)
            fly_zscore_file = name
        elif 'Voltage' in name and '.csv' in name:
            fly_voltage_file = name

    #generate save path per fly
    save_filepath = os.path.join(dataset_path, fly)
    xml_path = os.path.join(folder_path, fly)

    
    #get voltage file
    data_reducer = 100
    light_data = []
    fly_voltage_path = os.path.join(dataset_path, fly, fly_voltage_file)  #this isn't the right way to do this--redo after testing
    with open(fly_voltage_path, 'r') as rawfile:
        reader = csv.reader(rawfile)
        data_single = []
        for i, row in enumerate(reader):
            if i % data_reducer == 0: #will downsample the data 
                data_single.append(row)
        #light_data.append(data_single) #for more than one fly
        light_data = data_single    

    light_column = get_diode_column(light_data)
    print(np.shape(light_column))
        
    # find peaks
    light_median = np.median(light_column)
    early_light_max = max(light_column[0:2000])
    light_peaks, properties = scipy.signal.find_peaks(light_column, height = early_light_max +.001, prominence = .1, distance = 10)
       
    ## convert to seconds
    voltage_framerate =  10000/data_reducer #frames/s # 1frame/.1ms * 1000ms/1s = 10000f/s
    light_peaks_adjusted = light_peaks/voltage_framerate

    ##get averge distance between peaks to find interval time
    print('light difference--should be interval', int(np.median(light_peaks_adjusted[1:]-light_peaks_adjusted[:-1])))
    #this will give me a window that should equal the length of the interval
    window = int(np.median(light_peaks_adjusted[1:]-light_peaks_adjusted[:-1]))

    xml_file = str(fly) + '.xml'
    directory = os.path.join(dataset_path, fly)
    timestamps = load_timestamps(directory, xml_file)

    for i in range(len(fly_zscore_list)):
        if '2' in fly_zscore_list[i]:
            ch2zscore = fly_zscore_list[i]
    
    ch2_filepath = os.path.join(dataset_path, fly, ch2zscore)

    #get dims
    with h5py.File(ch2_filepath, 'r') as hf:   
        #moco = hf['data']
        zscore_data = hf['zscore']
        dims = np.shape(zscore_data) #dims are (x,y,z,t)

        
    #initialize h5 file
    save_file = os.path.join(save_filepath, "STA.h5")
    with h5py.File(save_file, 'w') as f:
        dset_anticipatory = f.create_dataset('anticipatory difference', dims[:3])  #I will want the dataset to hold anticipatory differences shape = (x,y,z) and I append on z
        dset_light_response = f.create_dataset('light response difference', dims[:3])
        dset_average = f.create_dataset('average bins', [dims[0], dims[1], dims[2],window])
        print(np.shape(dset_average))
        
    for z in range(dims[2]):
        z_timestamps = get_z_timestamps(timestamps, z)
        
        z_time_mean = np.mean(z_timestamps[1:] - z_timestamps[:-1])
        bruker_framerate = 1000/z_time_mean #f/s
        z_timestamps_s = z_timestamps/1000
        print(bruker_framerate)
        
        time_since_pulse_vector = get_time_since_pulse(z_timestamps_s, light_peaks_adjusted)

        ## this is for one z
        with h5py.File(ch2_filepath, 'r') as hf:   
            #moco = hf['data']
            zscore_data = hf['zscore']
            dims = np.shape(zscore_data) #dims are (x,y,z,t)
            anticipatory_xy = []
            light_response_xy = []
            all_average_bins = np.zeros(shape = (dims[0], dims[1], window))
            # all_average_bins = np.zeros(shape = (2, 2, 20))
            #all_average_bins = []
            anticipatory_difference = np.zeros(shape = (dims[0], dims[1]))
            light_response_difference = np.zeros(shape = (dims[0], dims[1]))
            for x in range(dims[0]):
                for y in range(dims[1]):
                    ##get zscore
                    ch2_zscore = np.array(zscore_data[x,y,z,:])

                    #adjust timestamps so they are the same length as data (still don't know why this happened)
                    time_since_pulse_vector = np.array(time_since_pulse_vector[:len(ch2_zscore)])

                    ## get average bins
                    average_bins = [] 
                    for bin_index in range(window):
                        bin_start = bin_index + 0.0
                        bin_end = bin_index + 1.0
                        data_value_vector = ch2_zscore #ch2_test
                        bin_value = np.nanmean(data_value_vector[np.logical_and(time_since_pulse_vector >= bin_start, time_since_pulse_vector < bin_end)])
                        average_bins.append(bin_value)
                    #all_average_bins.append(average_bins)

                    ## check if there is anticipation
                    # defining it as increase in response 2/3 of interval 13-20s compared to 6-13s (same window and ignore response to light)
                    if window == 20:
                        if np.mean(average_bins[13:]) > np.mean(average_bins[6:13]):
                            xy = [x,y]
                            anticipatory_xy.append(xy)
                            #I should probably store these in a dictionary...
                    elif window == 40:
                        if np.mean(average_bins[26:]) > np.mean(average_bins[12:26]):
                            xy = [x,y]
                            anticipatory_xy.append(xy)
                    else:
                        twothird = int(window*2/3)
                        onethird = int(window/3)
                        if np.mean(average_bins[twothird:]) > np.mean(average_bins[onethird:twothird]):
                            xy = [x,y]
                            anticipatory_xy.append(xy)

                    #put difference in anticipation to an array
                    if window == 20:
                        anticipatory_difference[x,y] = np.mean(average_bins[13:]) - np.mean(average_bins[6:13]) 
                    elif window == 40:
                        anticipatory_difference[x,y] = np.mean(average_bins[26:]) - np.mean(average_bins[12:26])
                    else:
                        twothird = int(window*2/3)
                        onethird = int(window/3)
                        anticipatory_difference[x,y] = np.mean(average_bins[twothird:]) - np.mean(average_bins[onethird:twothird])

                    ##check if there is response to light
                    ## defining as bigger response in first 5 seconds than in next 5 seconds
                    if np.mean(average_bins[:5]) > np.mean(average_bins[5:10]):
                        xy = [x,y]
                        light_response_xy.append(xy)

                    #put difference in light response in array
                    light_response_difference[x,y] = np.mean(average_bins[:5]) - np.mean(average_bins[5:10])
                    
                    all_average_bins[x,y] = np.array(average_bins)
#             print(all_average_bins)
#             print(np.shape(all_average_bins))
            #append the z anticipatory data
            with h5py.File(save_file, 'a') as f:
                f['anticipatory difference'][:,:,z] = anticipatory_difference
                f['light response difference'][:,:,z] = light_response_difference
                f['average bins'][:,:,z,:] = all_average_bins
                #print(average_bins)
            print('z slice done, z = : ', z)

