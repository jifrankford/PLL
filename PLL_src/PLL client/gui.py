import os
import tkinter as tk
import pygubu
import paramiko
from matplotlib.backends.backend_tkagg import (
    FigureCanvasTkAgg, NavigationToolbar2TkAgg)
from matplotlib.backend_bases import key_press_handler
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
import numpy as np
import time
import threading
import shutil


CURRENT_DIR = os.path.abspath(os.path.dirname(__file__))
MAIN_DIR = os.path.abspath(os.path.join(CURRENT_DIR,os.pardir))
MAIN_DIR = os.path.abspath(os.path.join(MAIN_DIR,os.pardir))


class MyApplication:
    def __init__(self):
        #1: Create a builder
        self.builder = builder = pygubu.Builder()

        #self.t=time.strftime("%Y-%b-%d__%H_%M_%S",time.localtime())

        #2: Load an ui file
        builder.add_from_file(os.path.join(MAIN_DIR,'gui.ui'))

        #3: Create the widget using a master as parent
        self.mainwindow = builder.get_object('mainwindow')

        self.sweeping=False
        self.locking=False
        self.connected=False

        #Setup matplotlib canvas
        self.sweep_fig=sweep_fig= Figure(figsize=(5.5,4), dpi=200)
        sweep_container = builder.get_object('Plot_Sweeper')
        self.sweep_canvas = sweep_canvas = FigureCanvasTkAgg(sweep_fig, master=sweep_container)
        sweep_canvas.show()
        sweep_canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=1)
        
        #Setup matplotlib toolbar (optional)
        self.toolbar_sw = NavigationToolbar2TkAgg(sweep_canvas, sweep_container)
        self.toolbar_sw.update()
        sweep_canvas._tkcanvas.pack(side=tk.TOP, fill=tk.BOTH, expand=1)

        
        
        #Setup matplotlib canvas
        self.pll_fig=pll_fig= Figure(figsize=(7,5), dpi=150)
        pll_container = builder.get_object('Plot_PLL')
        self.pll_canvas = pll_canvas = FigureCanvasTkAgg(pll_fig, master=pll_container)
        pll_canvas.show()
        pll_canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=1)
        
        #Setup matplotlib toolbar (optional)
        self.toolbar_pll = NavigationToolbar2TkAgg(pll_canvas, pll_container)
        self.toolbar_pll.update()
        pll_canvas._tkcanvas.pack(side=tk.TOP, fill=tk.BOTH, expand=1)
        
       

        builder.connect_callbacks(self)
        
    def on_connect_click(self):
        self.ssh = ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.ip=ip=self.builder.get_variable('IP').get()
        try:
            ssh.connect(ip,22,username='root',password='root')
            self.sftp= ssh.open_sftp()
            print("Connected to "+ip)
            self.connected=True
        except:
            print("Failed to connect")

    def on_sweep_stop(self):
        self.sweeping=False
        

    def on_sweeper_click(self):
        if self.sweeping or not self.connected: return
        self.sweeping=True
        self.clear_temp()
        
        self.freq_start = freq_start= self.builder.get_variable('freq_start').get()
        self.freq_end   = freq_end  = self.builder.get_variable('freq_end').get()
        self.freq_step  = freq_step = self.builder.get_variable('freq_step').get()
        volt            =             self.builder.get_variable('volt_sweep').get()

        
        sweep_cmd = 'nohup bash Sweeper.sh '+freq_start+' '+freq_end+' '+freq_step+' 1 '+volt
            
        ThreadedTask(self,task='cmd',cmd=sweep_cmd).start()

        self.ax=self.sweep_fig.add_subplot(111)


        ThreadedTask(self,task='Sweep').start()

    def PLL_stop(self):
        self.locking=False
        self.ssh.exec_command('bash stop.sh')

    def PLL_start(self):
        if self.locking or not self.connected: return
        self.locking=True
        self.clear_temp()
        
        self.pll_ids = ids = self.builder.get_variable('ids').get()
        f0= self.builder.get_variable('f0').get()
        set_point= self.builder.get_variable('set_point').get()
        kp= self.builder.get_variable('kp').get()
        ki= self.builder.get_variable('ki').get()
        #Ti= self.builder.get_variable('Ti').get()
        volt= self.builder.get_variable('volt_PLL').get()
        Time= self.builder.get_variable('time').get()

        pll_cmd= 'nohup bash PLL.sh --id '+ids+' --f0 '+f0+' --set_point '+set_point+' --kp '+kp+' --ki '+ki+' --V '+volt+' --time '+Time
        ThreadedTask(self,task='cmd',cmd=pll_cmd).start()
        
        #print("Starting PLL")

        ThreadedTask(self,task='PLL').start()
        

    def on_advisor_click(self):
        f_res=self.builder.get_variable('f_res').get()
        Q=self.builder.get_variable('Q').get()
        import Advise
        kp,ki,Ti = Advise.advise(f_res,Q)
        T=self.builder.get_object('constants')
        T.insert(tk.END,"kp: "+str(kp)+"\nki: "+str(ki)+"\n")

    def clear_temp(self):
        folder=os.path.join(MAIN_DIR,'Temp')
        for file in os.listdir(folder):
            file_path = os.path.join(folder,file)
            try:
                if os.path.isfile(file_path):
                    os.unlink(file_path)
            except Exception as e:
                print(e)

    def on_quit_click(self):
        if self.locking:
            self.PLL_stop()
        self.clear_temp()
        self.mainwindow.destroy()

    def run(self):
        self.mainwindow.mainloop()

class ThreadedTask(threading.Thread):
    def __init__(self,app,task='',cmd='',a=None,td_remote='',td_local=''):
        self.app=app
        self.cmd=cmd
        self.task=task
        self.a=a
        self.td_remote=td_remote
        self.td_local=td_local
        threading.Thread.__init__(self, name=task+' '+cmd)

    def run(self):
        task=self.task
        if (task=='Sweep'):
            self.clear_files()
            time.sleep(7)
            #while (self.app.sweeping):
                #time.sleep(.2)
            self.animateSweep()
        elif(task=='PLL'):
            #print('PLL')
            #self.clear_files()
            time.sleep(7)
            self.animatePLL()
        elif(task=='cmd'):
            self.exec_cmd()
        elif(task=='PLL_subplot'):
            #print('PLL_subplot')
            self.PLL_subplot()
        else:
            print("No Task")

    def exec_cmd(self):
        ssh_stdin, ssh_stdout, ssh_stderr = self.app.ssh.exec_command(self.cmd)
        print(ssh_stdout.read())

    def save(self,file,name):
        dest=os.path.join('Data',name)
        dest=os.path.join(MAIN_DIR,dest)
        td=np.fromfile(file)
        t=td[0:][::2]
        d=td[1:][::2]
        t=(t-t[0])*10**(-9)
        data = np.array([t,d])
        data = data.T

        import csv
        with open(dest, 'w+') as df_id:
            writer = csv.writer(df_id, delimiter=' ')
            writer.writerows(zip(t,d))
        

    def clear_files(self):
        self.cmd='rm **/*.text'
        self.exec_cmd()
    
    def animateSweep(self):
        app = self.app
        plot_p = app.builder.get_variable('plot_p_sweep').get()
        plot_R = app.builder.get_variable('plot_R_sweep').get()
        if (plot_R and not plot_p):
            fname='R.text'
            lfname0=os.path.join('Temp',fname)
            lfname0=os.path.join(MAIN_DIR,lfname0)
            i=0
            while app.sweeping:
                lfname=lfname0+str(i)
                i+=1
                try:
                    while True:
                        try:
                            self.app.sftp.get(fname,lfname)
                            break
                        except Exception as e:
                            print("getting file Sweep: "+str(e))
                            time.sleep(.2)
                            if not app.sweeping:
                                break
                    R = np.memmap(lfname, dtype=float, mode='r',)
                    R_trim=np.trim_zeros(R,'b')
                    a=app.ax
                    a.clear()
                    a.set_xlabel('frequency (kHz)')
                    a.set_ylabel('R (V)')
                    f0=float(app.freq_start)
                    df=float(app.freq_step)
                    f1=f0+len(R_trim)*df
                    f=np.arange(f0,f1,df)
                    a.plot(f[0:len(R_trim)],R_trim)
                    app.sweep_fig.canvas.draw()
                    plt.tight_layout()
                    app.sweep_fig.canvas.show()
                    R._mmap.close()
                    del R
                    gc.collect()
                    os.remove(lfname)
                    if f1>=float(app.freq_end):
                        app.sweeping=False
                        print("Sweep finished")
                        break                   
                except Exception as e:
                    print("exception: " + str(e))
                    time.sleep(.2)
                    if not app.sweeping:
                        break
                    
        elif(plot_p and not plot_R):
            fname='p.text'
            lfname0=os.path.join('Temp',fname)
            lfname0=os.path.join(MAIN_DIR,lfname0)
            i=0
            while app.sweeping:
                lfname=lfname0+str(i)
                i+=1
                try:
                    while True:
                        try:
                            self.app.sftp.get(fname,lfname)
                            break
                        except Exception as e:
                            print("getting file Sweep: "+str(e))
                            time.sleep(.2)
                            if not app.sweeping:
                                break
                    p = np.memmap(lfname, dtype=float, mode='r',)
                    p_trim=np.trim_zeros(p,'b')
                    a=app.ax
                    a.clear()
                    a.set_xlabel('frequency (kHz)')
                    a.set_ylabel('Phase (deg)')
                    f0=float(app.freq_start)
                    df=float(app.freq_step)
                    f1=f0+len(p_trim)*df
                    f=np.arange(f0,f1,df)
                    a.plot(f[0:len(p_trim)],p_trim)
                    app.sweep_fig.canvas.draw()
                    app.sweep_fig.tight_layout()
                    app.sweep_fig.canvas.show()
                    p._mmap.close()
                    del p
                    gc.collect()
                    os.remove(lfname)
                    if f1>=float(app.freq_end):
                        app.sweeping=False
                        break                   
                except Exception as e:
                    print("exception: " + str(e))
                    time.sleep(.2)
                    if not app.sweeping:
                        break

        elif(plot_p and plot_R):
            fpname='p.text'
            lfpname0=os.path.join('Temp',fpname)
            lfpname0=os.path.join(MAIN_DIR,lfpname0)

            frname='R.text'
            lfrname0=os.path.join('Temp',frname)
            lfrname0=os.path.join(MAIN_DIR,lfrname0)
            
            i=0
            while app.sweeping:
                lfpname=lfpname0+str(i)
                lfrname=lfrname0+str(i)
                i+=1
                try:
                    while True:
                        try:
                            self.app.sftp.get(fpname,lfpname)
                            self.app.sftp.get(frname,lfrname)
                            break
                        except Exception as e:
                            print("getting file Sweep: "+str(e))
                            time.sleep(.2)
                            if not app.sweeping:
                                break
                    p = np.memmap(lfpname, dtype=float, mode='r',)
                    p_trim=np.trim_zeros(p,'b')

                    R = np.memmap(lfrname, dtype=float, mode='r',)
                    R_trim=R[0:len(p_trim)]
                    
                    a=app.ax
                    a.clear()
                    a.set_xlabel('frequency (kHz)')
                    a.set_ylabel('Phase (deg)')
                    f0=float(app.freq_start)
                    df=float(app.freq_step)
                    f1=f0+len(p_trim)*df
                    f=np.arange(f0,f1,df)


                    scale=p_trim[np.argmax(R_trim)]/(np.max(R_trim))
                    
                    a.plot(f[0:len(p_trim)],p_trim)
                    a.plot(f[0:len(p_trim)],scale*R_trim)
                    app.sweep_fig.canvas.draw()
                    plt.tight_layout()
                    app.sweep_fig.canvas.show()
                    
                    p._mmap.close()
                    del p
                    gc.collect()
                    os.remove(lfpname)
                    
                    R._mmap.close()
                    del R
                    gc.collect()
                    os.remove(lfrname)
                    
                    if f1>=float(app.freq_end):
                        app.sweeping=False
                        break                   
                except Exception as e:
                    print("exception: " + str(e))
                    time.sleep(.2)
                    if not app.sweeping:
                        break

    def animatePLL(self):
        app=self.app

        ids=app.pll_ids.split()
        length=len(ids)
        tp_file_names_remote=np.empty(length,dtype=object)
        tf_file_names_remote=np.empty(length,dtype=object)
        tp_file_names_local=np.empty(length,dtype=object)
        tf_file_names_local=np.empty(length,dtype=object)
        

        fig=app.pll_fig
        aa=np.empty(length,dtype=object)
        
        for i,s in enumerate(ids):
            tp_name='tp'+s+'.text'
            tp_file_names_remote[i]='data/'+tp_name
            tp_name=os.path.join('Temp',tp_name)
            tp_file_names_local[i]=os.path.join(MAIN_DIR,tp_name)

            tf_name='tf'+s+'.text'
            tf_file_names_remote[i]='data/'+tf_name
            tf_name=os.path.join('Temp',tf_name)
            tf_file_names_local[i]=os.path.join(MAIN_DIR,tf_name)

            aa[i]=fig.add_subplot(len(ids),1,i+1)

        plot_p = app.builder.get_variable('plot_p_pll').get()
        plot_f = app.builder.get_variable('plot_f_pll').get()


        if plot_f:
            ThreadedTask(self.app,task='PLL_subplot',a=aa,td_remote=tf_file_names_remote,td_local=tf_file_names_local).start()
        elif plot_p:
            ThreadedTask(self.app,task='PLL_subplot',a=aa,td_remote=tp_file_names_remote,td_local=tp_file_names_local).start()
        
        

    def PLL_subplot(self):
        plot_p = self.app.builder.get_variable('plot_p_pll').get()
        plot_f = self.app.builder.get_variable('plot_f_pll').get()

        sub_ax=self.a
        td_local=self.td_local
        td_remote=self.td_remote
        i=0
        while app.locking:
            i+=1
            try:
                for j,td_l in enumerate(td_local):
                    temp_name_local=td_local[j]+str(i)
                    while True:
                        try:
                            self.app.sftp.get(td_remote[j],temp_name_local)
                            break
                        except Exception as e:
                            print("getting "+td_remote+" subplot: "+str(e))
                            time.sleep(.2)
                            if not app.locking:
                                break
                            
                    td=np.fromfile(temp_name_local)
                    t=td[0:][::2]
                    d=td[1:][::2]

                    t=(t-t[0])*10**(-9)

                    a=sub_ax[j]
                    a.clear()
                    a.set_xlabel('Time (s)')
                    if plot_f:
                        a.set_ylabel('Freqeuncy (Hz)')
                    elif plot_p:
                        a.set_ylabel('Phase (deg)')
                    a.plot(t,d)
                    app.pll_fig.canvas.draw()
            except Exception as e:
                print("exception: " + str(e))
                time.sleep(.2)
                if not app.locking:
                    break
            app.pll_fig.tight_layout()
            app.pll_fig.canvas.show()

        for j,td_l in enumerate(td_local):
            self.save(td_local[j]+str(i),os.path.basename(td_l))
    

if __name__ == '__main__':
    app = MyApplication()
    app.run()
