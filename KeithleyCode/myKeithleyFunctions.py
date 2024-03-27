import pyvisa
import sys
import numpy as np
from PyQt5 import QtTest
import time
from statistics import mean
import datetime

#####TO-DO#####
'''
- find out if you can use wait_for_srq or wai*
- determine Digital Output configuration required to open and close the shutter. The functions currently work, but the output configuration is a guess.
- consider changing TRIG:COUN for repeated measurements instead of repeating the command


'''
###############
def connectToKeithley(keithleyAddress='GPIB0::22::INSTR'):
    rm = pyvisa.ResourceManager()
    keithley = rm.open_resource('ASRL13::INSTR')
    keithley.baud_rate=57600

    print(keithley.query('*IDN?\r'))
    if(keithley.query('*IDN?\r').has("2651A") == true):
        print("2600")
        keithley.baud_rate=57600
        keithley.read_termination = '\n'
        keithley.write('smua.reset()')  # Reset the instrument

        keithley.write('smua.sense = smua.SENSE_REMOTE')  # Enable 4-wire sense
        if keithleyAddress == 'Test':
            return 'Test Mode'  # Simulated mode for testing without actual hardware
        message = "Connected"
        return [message, keithley]
    else:
     if(keithley.query('*IDN?\r').contains("Model 24")):
        print("2400")
#Keithley Instruments Inc., Model 2651A, 4405857, 1.2.0
def shutdownKeithley(keithley):
    if keithley == 'Test':
        print('Shutdown in Test Mode')
        return
    keithley.write('smua.source.output = smua.OUTPUT_OFF')
    keithley.close()

def openShutter(keithley):
    if keithley == 'Test':
        print('Open Shutter in Test Mode')
        return
    # Implement the method to open the shutter using digital IO or other means if required.

def closeShutter(keithley):
    if keithley == 'Test':
        print('Close Shutter in Test Mode')
        return
    # Implement the method to close the shutter using digital IO or other means if required.

def prepareVoltage(keithley, NPLC=1, voltlimit=10, polarity='pin'):
    if keithley == 'Test':
        print('Prepare Voltage in Test Mode')
        return
    keithley.write('smua.source.func = smua.OUTPUT_DCAMPS')
    keithley.write('smua.source.autorangei = smua.AUTORANGE_ON')
    keithley.write('smua.measure.v()')


    keithley.write(f'smua.source.limitv = {voltlimit}')
    keithley.write('smua.source.autorangev = smua.AUTORANGE_ON')

    keithley.write(f'smua.measure.nplc = {NPLC}')
    keithley.write(f'smua.trigger.count = 1')    
    keithley.write('smua.source.output = smua.OUTPUT_ON')

def measureVoltage(keithleyObject, current=0, n=1, polarity='pin'):
    if polarity == 'pin':
        current *= -1
 
    rawDataArray = []
    # Assuming the keithleyObject can execute Lua commands and return the results
    for _ in range(n):
        measureVoltageCmd = 'print(smua.measure.v())\n'
        keithleyObject.write(measureVoltageCmd)
        voltageMeasurement = keithleyObject.read()
        rawDataArray.append(float(voltageMeasurement))
 
    if polarity == 'pin':
        rawDataArray = [-x for x in rawDataArray]
 
    # Creating a 2D numpy array, with each measurement as a new column in the single row
    data = np.array([rawDataArray])
 
    return data

def prepareCurrent(keithleyObject, NPLC=1, currentlimit=1e-2, polarity='pin'):
    '''
    Prepares the Keithley to source voltage and measure current, using Lua commands.
    NPLC Range [0.01,10]
    '''
    if polarity == 'pin':
        currentlimit *= -1

    if keithleyObject == 'Test':
        return
    
    # Resetting the instrument to a known state is generally good practice, but commented out for safety
    # keithleyObject.write('reset()')
    
    # Set source function to voltage
    keithleyObject.write('smua.source.func = smua.OUTPUT_DCVOLTS\n')
    
    # Set the voltage source mode to fixed
    # This specific mode setting is implicit in setting the source level and not required as a separate command in TSP
    
    # Enable auto range for sourcing voltage
    keithleyObject.write('smua.source.autorangev = smua.AUTORANGE_ON\n')
    
    # Set the measurement function to current
    # For Keithley TSP, measurement function is set automatically based on the measure command used
    
    # Set the compliance (protection) limit for current measurement
    keithleyObject.write(f'smua.source.limiti = {currentlimit}\n')
    
    # Enable auto range for current measurement
    keithleyObject.write('smua.measure.autorangei = smua.AUTORANGE_ON\n')
    
    # Set the NPLC for current measurement
    keithleyObject.write(f'smua.measure.nplc = {NPLC}\n')
    
    # Set trigger count to 1
    keithleyObject.write('smua.trigger.count = 1\n')
    
    # Turn the output on
    keithleyObject.write('smua.source.output = smua.OUTPUT_ON\n')


def measureCurrent(keithleyObject, voltage=0, n=1, polarity='pin'):
    '''
    Sets the voltage and measures current n times using Lua commands.
    Constructs a 2D array with each row as a measurement cycle.
    '''
    if polarity == 'pin':
        voltage *= -1

    rawDataArray = []

    if keithleyObject == 'Test':
        # Simulated logic for testing environment
        pass
    else:
        for i in range(n):
            # Assuming keithleyObject.write() sends a Lua command
            # and keithleyObject.read() reads its output

            # Set voltage and measure current
            keithleyObject.write(f'smua.source.levelv = {voltage}\n')
            keithleyObject.write('smua.source.output = smua.OUTPUT_ON\n')
            keithleyObject.write('print(smua.measure.i())\n')
            currentMeasurement = float(keithleyObject.read())
            keithleyObject.write('smua.source.output = smua.OUTPUT_OFF\n')

            # Constructing each row: [sourced voltage, measured current]
            # Adjusting the polarity of the measured data if necessary
            voltageValue = -voltage if polarity == 'pin' else voltage
            rawDataArray.append([voltageValue, currentMeasurement])

    # Convert rawDataArray to a 2D NumPy array
    dataCurrent = np.array(rawDataArray)

    return dataCurrent
def takeIV(keithleyObject, minV=-0.2, maxV=1.2, stepV=0.1, delay=10, forw=1, polarity='pin', NPLC=1, Ilimit=100E-3):
    '''
    Takes an IV sweep from minV to maxV with stepV, measuring current at each step.
    Returns a numpy array with columns for voltage, current, resistance, time, and status.
    '''
    delay /= 1000  # Convert delay from ms to seconds
    rawDataArray = []

    volts = np.arange(minV, maxV + stepV, stepV) if forw else np.arange(maxV, minV - stepV, -stepV)
    start = datetime.datetime.now()

    for volt in volts:
        if polarity == 'pin':
            volt *= -1
        # Set the voltage
        keithleyObject.write(f'smua.source.levelv = {volt}\nsmua.source.output = smua.OUTPUT_ON\n')
        time.sleep(delay)  # Wait for the delay period

        # Measure the current
        keithleyObject.write('print(smua.measure.i())\n')
        currentMeasurement = float(keithleyObject.read())

        # Timestamp and resistance are placeholders in this context
        timeStamp = (datetime.datetime.now() - start).total_seconds()
        resistance = 9.91e+37  # Placeholder for resistance
        status = 0b00000000  # Placeholder for status

        rawData = [volt, currentMeasurement, resistance, timeStamp, status]
        rawDataArray.append(rawData)

    keithleyObject.write('smua.source.output = smua.OUTPUT_OFF\n')

    data = np.array(rawDataArray)
    return data


def setFrontTerminal(keithleyObject):
	if keithleyObject != 'Test':
		return("Feature Doesn't Exist on 2651A")

def setRearTerminal(keithleyObject):
	if keithleyObject != 'Test':
		return("Feature Doesn't Exist on 2651A")



if __name__ == "__main__":

	import matplotlib.pyplot as plt
#	import pymeasure
##	print(pymeasure.__version__)
#	from pymeasure.instruments.keithley import Keithley2400
#    
#	sourcemeter=Keithley2400('ASRL1::INSTR')
#	print(sourcemeter.ask("*IDN?"))    
    
    
	rm = pyvisa.ResourceManager(r'C:\WINDOWS\system32\visa32.dll')
	print(rm.list_resources('?*'))
#	print(pyvisa.log_to_screen())
# 	keithley = connectToKeithley('GPIB0::22::INSTR')
	keithleyObject = connectToKeithley('ASRL13::INSTR')
	#keithleyObject = rm.open_resource('ASRL13::INSTR')
	print('1')
	#keithleyObject.baud_rate=57600
#	print('2')
	#keithleyObject.read_termination = '\n'
#	time.sleep(1)
#	print('3')
	#print (keithleyObject.query('*IDN?\n'))
# 	keithley = connectToKeithley(['Test'])
	polarity = 'pin'
	forw = 1
# 	keithleyObject=keithley[1]
	# keithley = connectToKeithley('Test')
	prepareVoltage(keithleyObject)
	#rawDataDark = takeIV(keithleyObject, stepV = 0.01, forw=forw, polarity=polarity)
#	setFrontTerminal(keithley)
    
# 	global Iph
# 	openShutter(keithleyObject)
# 	print(Iph)
#	time.sleep(5)
#	closeShutter(keithley)

#	prepareCurrent(keithley, NPLC = 0.01, polarity=polarity)
#	dataCurrent = measureCurrent(keithley,voltage=0.2,n=10, polarity=polarity)
#	keithley.write('OUTP ON')    

#	keithley.write('OUTP OFF')
	# print (dataCurrent[0,:])

# 	prepareVoltage(keithleyObject, NPLC = 0.01, polarity=polarity)
# 	dataVoltage = measureVoltage(keithleyObject, current=0.0, n=2, polarity=polarity)
# 	print (dataVoltage[0,:])
# 	print (dataVoltage)
# 	voltage=abs(mean(dataVoltage[:,0]))
# 	print(voltage)
# 	voltage=abs(mean(dataVoltage[:,1]))
# 	print(voltage)


# 	rawDataLight = takeIV(keithley,forw=1,stepV=0.01)

# 	closeShutter(keithley)




	#prepareCurrent(keithleyObject, NPLC = 0.01, polarity=polarity)
	#dataCurrent = measureCurrent(keithleyObject,voltage=0.2,n=10, polarity=polarity)
	#print (dataCurrent[0,:])

	#prepareVoltage(keithleyObject, NPLC = 0.01, polarity=polarity)
	#dataVoltage = measureVoltage(keithleyObject, current=0.01, n=10, polarity=polarity)
	#print (dataVoltage[0,:])

# 	shutdownKeithley(keithley)
# 	plt.axhline(color = 'k')
# 	plt.axvline(color = 'k')
# 	pixarea=1
# 	currentdenlist=[x*1000/pixarea for x in rawDataLight[:,1]]#to mA/cm2
# 	plt.plot(rawDataLight[:,0],currentdenlist, color = 'r')
# 	plt.scatter(rawDataLight[0,0],rawDataLight[0,1], label = 'start', color = 'y')
# 	plt.scatter(rawDataLight[-1,0],rawDataLight[-1,1], label = 'end', color = 'g')
# 	plt.plot(rawDataDark[:,0],rawDataDark[:,1], color = 'b')
# 	plt.scatter(rawDataDark[0,0],rawDataDark[0,1], label = 'start', color = 'cyan')
# 	plt.scatter(rawDataDark[-1,0],rawDataDark[-1,1], label = 'end', color = 'purple')
# 	plt.legend()

# 	plt.show()