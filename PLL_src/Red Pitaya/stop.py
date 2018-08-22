#stop.py
from redpitaya.overlay.mercury import mercury as overlay

fpga = overlay()
gen0 = fpga.gen(0)
gen0.enable= False
