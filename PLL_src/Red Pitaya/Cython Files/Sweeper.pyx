# Sweeper.pyx

from redpitaya.overlay.mercury import mercury as overlay
import collections
cimport cython
import numpy as np
cimport numpy as np
from libc.math cimport ceil,sin, cos, atan, sqrt, M_PI
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import sys
from posix.time cimport clock_gettime, timespec, CLOCK_MONOTONIC
import time

#create overlay, signal generator, and oscilloscope
fpga = overlay()
gen0 = fpga.gen(0)
cdef int dec, n, num, N
dec=1


cdef float dt = dec/125000000.0

cdef float f0,f1,df,V

N=16384

if (len(sys.argv)==6):
    f0=float(sys.argv[1])
    f1=float(sys.argv[2])
    df=float(sys.argv[3])
    n=int(sys.argv[4])
    V=float(sys.argv[5])
elif (len(sys.argv)==5):
    f0=float(sys.argv[1])
    f1=0
    n=int(sys.argv[2])
    V=float(sys.argv[3])
    num=int(sys.argv[4])
else:
   #print('Wrong number of arguments')
   #sys.exit(0)
   for i in sys.argv:
       print(i)

gen0.amplitude = V
gen0.offset    = 0.0
gen0.waveform  = gen0.sin()
gen0.mode      = 'PERIODIC'

osc0 = fpga.osc(0,1.0)
osc0.decimation = dec
osc0.trigger_pre = 0
osc0.trigger_post = N

#calculate in phase component (X) and quadrature component (Y)
#it is assumed that the outgoing signal is a sine function
#(implement in C)
cdef tuple getXY(float [:] data):
    cdef float X,Y,mode_num
    cdef int i, L
    L=len(data)
    i=0
    X=0
    Y=0
    mode_num=2*M_PI*dt*gen0.frequency
    while (i< L):
        X=X+data[i]*cos(mode_num*i)
        Y=Y+data[i]*sin(mode_num*i)
        i=i+1
    return X/L,Y/L

#digital lock_in amplifier
#leave in python
def lock_in(float f,int n,float po):
    cdef float R,phase,X,Y,x,y
    cdef int i
    cdef double[:] xx,yy

    gen0.frequency = f    
   
    cdef int T=<int>round(1/(dt*gen0.frequency))
    cdef int S=<int>round(4000.0/T)
    cdef int L=N-N%T

    if (n!=1):
        i=0
        xx = np.empty(n, dtype=float)
        yy = np.empty(n, dtype=float)
        while(i<n):
            gen0.start()
            gen0.trigger()
            time.sleep(0.005)
            #synchronize oscilloscope with signal generator
            osc0.sync_src = fpga.sync_src['gen0']
            osc0.trig_src = 0

            osc0.reset()
            osc0.start()
            gen0.reset()

            gen0.enable=True

            gen0.start_trigger()
            while (osc0.status_run()): pass
            x,y=getXY(osc0.data(N)[S:L])
            xx[i]=x
            yy[i]=y
            i=i+1
            gen0.enable=False
        X=np.average(xx)
        Y=np.average(yy)
    else:
        gen0.start()
        gen0.trigger()

        time.sleep(0.005)
        #synchronize oscilloscope with signal generator
        osc0.sync_src = fpga.sync_src['gen0']
        osc0.trig_src = 0

        osc0.reset()
        osc0.start()
        gen0.reset()

        gen0.enable=True

        gen0.start_trigger()
        while (osc0.status_run()): pass
        X,Y=getXY(osc0.data(N)[S:L])
        gen0.enable=False

    R = sqrt(X*X+Y*Y)
    phase = np.arctan2(Y,X)*180.0/np.pi

    if (phase-po>180):
        phase=phase-360
    elif (po-phase>180):
        phase=phase+360


    return X,Y,phase,R

#frequency sweep
#(implement in C)
#cdef tuple sweep(float f0,float f1,float df,int n):
def sweep(f0,f1,df,n):
    cdef float f,p,R,x,y
    cdef int length,i
    length=<int>ceil((f1-f0)/df)
    RR = np.memmap('R.text', dtype=float, mode='w+', shape=(length,))
    pp = np.memmap('p.text', dtype=float, mode='w+', shape=(length,))
    f=f0
    i=0
    while (i<length):
        x,y,p,R=lock_in(f,n,p)
        RR[i]=R
        pp[i]=p
        f=f+df
        i=i+1
        if (i%10==0):
            RR.flush()
            pp.flush()


cdef tuple sit(float f0, int n):
    cdef float f,p,R,x,y,t0
    cdef int length,i
    cdef timespec t
    length=num
    cdef double[:] pp = np.empty(length, dtype=float)
    cdef double[:] RR = np.empty(length, dtype=float)
    cdef double[:] xx = np.empty(length, dtype=float)
    cdef double[:] yy = np.empty(length, dtype=float)
    cdef double[:] tt = np.empty(length, dtype=float)
    f=f0
    i=0
    clock_gettime(CLOCK_MONOTONIC, &t)
    t0=t.tv_sec*1000+(t.tv_nsec/1000000)
    while (i<length):
        clock_gettime(CLOCK_MONOTONIC, &t)
        tt[i]=t.tv_sec*1000+(t.tv_nsec/1000000)-t0
        x,y,p,R=lock_in(f,n)
        pp[i]=p
        RR[i]=R
        xx[i]=x
        yy[i]=y
        i=i+1

    return tt,xx,yy,pp,RR


if (f1==0):
    t,X,Y,P,R=sit(1000*f0,n)
else:
    sweep(1000*f0,1000*f1,1000*df,n)
