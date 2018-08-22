# runPLL.pyx
from redpitaya.overlay.mercury import mercury as overlay
cimport cython
import numpy as np
cimport numpy as np
from libc.math cimport sin, cos, ceil, atan, sqrt, M_PI
from posix.time cimport clock_gettime, timespec, CLOCK_MONOTONIC
import time
import argparse
import gc
import struct
       
cdef class PLL:
    cdef object fpga,osc,gen
    cdef float frequency, set_point,kp,ki,kd,p,err
    cdef int num, i
    cdef str id
    #cdef double[:] pp,RR,xx,yy,tt,ff
    cdef float ee
    cdef object tp,tf

    def __cinit__(self, id, f, sp, kp, ki, num, fpga, osc0, gen0, kd=0):
        self.id=id
        self.frequency=f
        self.set_point=sp
        self.kp=kp
        self.ki=ki
        self.kd=kd
        cdef int n = <int>num
        self.num=n
        self.p=0
        self.i=0
        self.ee=0
        self.err=0
        #self.pp = np.zeros(n, dtype=np.double)
        #self.RR = np.zeros(n, dtype=np.double)
        #self.xx = np.zeros(n, dtype=np.double)
        #self.yy = np.zeros(n, dtype=np.double)
        #self.tt = np.zeros(n, dtype=np.double)
        #self.ff = np.zeros(n, dtype=np.double)
        self.tp=open('data/tp'+id+'.text','wb',10)
        #self.ff=open('data/f'+id+'.text','wb',10)
        self.tf=open('data/tf'+id+'.text','wb',10)
        self.fpga=fpga
        self.osc=osc0
        self.gen=gen0
    
    cdef void update(self, int n=1,dt=.02):
        cdef float x,y,R,err,der,f,df
        cdef timespec t
        clock_gettime(CLOCK_MONOTONIC, &t)
        cdef int i = self.i
        x,y,self.p,R,f=self.lock_in(self.frequency,n,self.p)
        
        cdef float t_sec=float(t.tv_sec)*(10**9)+float(t.tv_nsec)

        self.tf.write(np.array([t_sec,f]).tobytes())
        self.tp.write(np.array([t_sec,self.p]).tobytes())

        err=self.set_point-self.p
        der = (err-self.err)/.02
        #self.ee[i%self.integ_range]=err*.02
        self.ee+=err
        df=self.kp*err+self.ki*self.ee+self.kd*der
        self.frequency=f+df
        self.i=self.i+1
    
    """
    cdef void write(self):
        cdef tuple s=np.asarray(self.xx).shape
        xfi = np.memmap('data/x'+self.id+'.text', dtype='float', mode='w+',shape=s)
        yfi = np.memmap('data/y'+self.id+'.text', dtype='float', mode='w+',shape=s)
        phase = np.memmap('data/p'+self.id+'.text', dtype='float', mode='w+',shape=s)
        rfi = np.memmap('data/R'+self.id+'.text', dtype='float', mode='w+',shape=s)
        tfi = np.memmap('data/t'+self.id+'.text', dtype='float', mode='w+',shape=s)
        ffi= np.memmap('data/f'+self.id+'.text', dtype='float', mode='w+',shape=s)
    

        xfi[:]=self.xx
        yfi[:]=self.yy
        phase[:]=self.pp
        rfi[:]=self.RR
        tfi[:]=self.tt
        tfi[0]=0
        tfi[1:]=[t-self.tt[0] for t in self.tt[1:]]
        ffi[:]=self.ff
        
        xfi.flush()
        yfi.flush()
        phase.flush()
        rfi.flush()
        tfi.flush()
        ffi.flush()

        del xfi
        del yfi
        del phase
        del tfi
        del ffi

        gc.collect()
    """

    #calculate in phase component (X) and quadrature component (Y)
    #it is assumed that the outgoing signal is a sine function
    #(implement in C)
    cdef tuple getXY(self, float [:] data):
        cdef float X,Y,mode_num
        cdef int i, L
        L=len(data)
        cdef float dt=1/125000000.0 #Time between samples
        i=0
        X=0
        Y=0
        mode_num=2*M_PI*dt*self.gen.frequency
        while (i< L):
            X=X+data[i]*cos(mode_num*i)
            Y=Y+data[i]*sin(mode_num*i)
            i=i+1
        if (L!=0): return X/L,Y/L
        else: return 0, 0
        

    #digital lock_in amplifier
    #leave in python
    def lock_in(self,float f,int n,float p_o):
        cdef float R,phase,X,Y,x,y
        cdef int i
        cdef double[:] xx,yy

        self.gen.frequency = f
        cdef float dt=1/125000000.0 #Time between samples
        cdef int N = self.osc.buffer_size
        cdef int T = <int>round(1/(dt*self.gen.frequency))
        cdef int S = <int>round(4000.0/T)
        cdef int L = N-N%T

        if (n!=1):
            i=0
            xx = np.empty(n, dtype=float)
            yy = np.empty(n, dtype=float)
            while(i<n):
                self.gen.start()
                self.gen.trigger()
                time.sleep(0.005)
                #synchronize oscilloscope with signal generator
                self.osc.sync_src = self.fpga.sync_src['gen0']
                self.osc.trig_src = 0

                self.osc.reset()
                self.osc.start()
                self.gen.reset()

                self.gen.enable=True

                self.gen.start_trigger()
                while (self.osc.status_run()): pass
                x,y=self.getXY(self.osc.data(N)[S:L])
                xx[i]=x
                yy[i]=y
                i=i+1
                self.gen.enable=False
            X=np.average(xx)
            Y=np.average(yy)
        else:
            self.gen.start()
            self.gen.trigger()

            time.sleep(0.005)
            #synchronize oscilloscope with signal generator
            self.osc.sync_src = self.fpga.sync_src['gen0']
            self.osc.trig_src = 0

            self.osc.reset()
            self.osc.start()
            self.gen.reset()

            self.gen.enable=True

            self.gen.start_trigger()
            while (self.osc.status_run()): pass
            X,Y=self.getXY(self.osc.data(N)[S:L])
            self.gen.enable=False

        R = sqrt(X*X+Y*Y)
        phase = np.arctan2(Y,X)*180.0/M_PI

        if (phase-p_o>180):
            phase=phase-360
        elif (p_o-phase>180):
            phase=phase+360

        return X,Y,phase,R,self.gen.frequency
        
CLI=argparse.ArgumentParser()
CLI.add_argument(
    "--id",
    nargs="*",
    type=str,
    default=[]
)
CLI.add_argument(
    "--f0",
    nargs="*",
    type=float,
    default=[]
)
CLI.add_argument(
    "--set_point",
    nargs="*",
    type=float,
    default=[]
)
CLI.add_argument(
    "--kp",
    nargs="*",
    type=float,
    default=[]
)
CLI.add_argument(
    "--ki",
    nargs="*",
    type=float,
    default=[]
)
CLI.add_argument(
    "--kd",
    nargs="*",
    type=float,
    default=[]
)

CLI.add_argument(
    "--Ti",
    nargs="*",
    type=float,
    default=[]
)
CLI.add_argument(
    "--n",
    type=int,
    default=1
)
CLI.add_argument(
    "--V",
    type=float,
    default=1.0
)
CLI.add_argument(
    "--time",
    type=float,
    default=0
)

args= CLI.parse_args()

#create overlay, signal generator, and oscilloscope
fpga = overlay()
gen0 = fpga.gen(0)
cdef int n, N

osc0 = fpga.osc(0,1.0)
osc0.decimation = 1
N = osc0.buffer_size
osc0.trigger_pre = 0
osc0.trigger_post = N


cdef int length = len(args.f0)
cdef float dt_PLL=.02*length #Time for PLL loop

cdef int num = <int>ceil(args.time/dt_PLL)


#cdef int[:] integ_range = np.array([<int>ceil(t/dt_PLL) for t in args.Ti])

gen0.amplitude = args.V
gen0.offset    = 0.0
gen0.waveform  = gen0.sin()
gen0.mode      = 'PERIODIC'

cdef int i=0
PLLs=[None]*length
while (i<length):
    PLLs[i]=PLL(args.id[i],args.f0[i],args.set_point[i],
                args.kp[i],args.ki[i],num,fpga,osc0,gen0)
    i=i+1

cdef PLL p_cur
i=0
while (i<num):
    for p in PLLs:
        p_cur=<PLL>p
        p_cur.update()
    i=i+1
