from keithley2600 import Keithley2600

k = Keithley2600('ASRL13::INSTR')

k.smua.source.output = k.smua.OUTPUT_ON   # turn on SMUA
k.smua.source.levelv = -40  # sets SMUA source level to -40V
v = k.smua.measure.v()  # measures and returns the SMUA voltage
i = k.smua.measure.i()  # measures current at smuA

k.smua.measure.v(k.smua.nvbuffer1)  # measures the voltage, stores the result in buffer
k.smua.nvbuffer1.clear()  # clears nvbuffer1 of SMUA