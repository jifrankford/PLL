# Advise.pyx

import numpy as np
import control
import sys

def advise(f_res,Q):
    #f_res=resonant frequency
    #Q=quality factor


    tc=Q/(np.pi*f_res)
    LTI=control.tf([-360*tc],[tc, 1])

    gm,pm,wg,wp = control.margin(LTI)

    kp=abs(0.45*gm)
    if wg!=0:
        Ti=(2*np.pi/wg)/1.2
        ki=kp/Ti
    else:
        Ti=0
        ki=0

    return kp,ki,Ti
