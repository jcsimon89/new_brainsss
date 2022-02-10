## to be sure I'm running just vol_moco

import time
import sys
import os
import re
import json
import datetime
import pyfiglet
import textwrap
import brainsss
import gc

modules = 'gcc/6.3.0 python/3.6.1 py-numpy/1.14.3_py36 py-pandas/0.23.0_py36 viz py-scikit-learn/0.19.1_py36' 

logfile = './logs/' + time.strftime("%Y%m%d-%H%M%S") + '.txt'
printlog = getattr(brainsss.Printlog(logfile=logfile), 'print_to_log')
sys.stderr = brainsss.Logger_stderr_sherlock(logfile)

scripts_path = "/home/users/asmart/projects/new_brainsss/scripts"

date = '20210719'
mem = 8
dataset_path = "/oak/stanford/groups/trc/data/Ashley2/imports/" + str(date)
flies_temp = os.listdir(dataset_path)  ## find directory names, they are the fly names
#to sort out non-fly directories (issue if I ever label a file with fly but I can't get isdir to work.)
flies = []
for i in flies_temp:
    if 'fly' in os.path.join(dataset_path, i):
        flies.append(i)

        
title = pyfiglet.figlet_format("Brainsss", font="cyberlarge" ) #28 #shimrod
title_shifted = ('\n').join([' '*28+line for line in title.split('\n')][:-2])
printlog(title_shifted)
day_now = datetime.datetime.now().strftime("%B %d, %Y")
time_now = datetime.datetime.now().strftime("%I:%M:%S %p")
printlog(F"{day_now+' | '+time_now:^{width}}")
printlog("")


######################
### Test vol moco ####
#######################
printlog(f"\n{'   vol by vol test   ':=^{width}}")
job_ids = []
for fly in flies:
    directory = os.path.join(dataset_path, fly)
    save_path = directory  #could have it save in a different folder in the future
    args = {'logfile': logfile, 'directory': directory, 'smooth': False, 'colors': ['green'], file_names = [ch1_stitched.nii, ch2_stitched.nii], save_path = save_path}
    script = 'vol_moco.py'
    job_id = brainsss.sbatch(jobname='voltest',
                         script=os.path.join(scripts_path, script),
                         modules=modules,
                         args=args,
                         logfile=logfile, time=96, mem=mem, nice=nice, nodes=nodes)
    job_ids.append(job_id)

for job_id in job_ids:
    brainsss.wait_for_job(job_id, logfile, com_path)
    
    
    
time.sleep(30) # to allow any final printing
day_now = datetime.datetime.now().strftime("%B %d, %Y")
time_now = datetime.datetime.now().strftime("%I:%M:%S %p")
printlog("="*width)
printlog(F"{day_now+' | '+time_now:^{width}}")
    


