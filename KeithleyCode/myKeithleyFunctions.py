import pyvisa
import sys
import numpy as np
from PyQt5 import QtTest
import time
from statistics import mean
import datetime
from scipy.interpolate import interp1d as interp
import datetime
import time

#####TO-DO#####
'''
- find out if you can use wait_for_srq or wai*
- determine Digital Output configuration required to open and close the shutter. The functions currently work, but the output configuration is a guess.
- consider changing TRIG:COUN for repeated measurements instead of repeating the command


'''
###############
def connectToKeithley(keithleyAddress=['GPIB0::22::INSTR']):
    '''
    This creates a Keithley object with which to interact with.
    Attempt to connect to a Keithley, then send an ID query to confirm connection. If this fails, send an error message to the terminal and terminate the program.
    '''
    if keithleyAddress == ['Test']:
        message = 'Keithley Code running in Test Mode. All of the following data is generated not measured.'
        global datetime
        global time
        global sleepTime
        sleepTime = 0.001
        global start
        start = datetime.datetime.now()
        global k
        k = 1.38e-23
        global T0
        T0 = 273.15
        global Iph
        Iph = 0
        global q
        q = 1.602e-19

        def testIV(V, Iph, I0=1e-10, T=25, VF=1.1, VR=1, V0=0.6):
            I = -Iph + I0 * (np.exp(q * (V - VF + V0) / (1.4 * k * (T + T0))) - 1) + np.random.uniform(-.00005, .00005)
            return I

        def testIVinv(I, Iph, I0=1e-10, T=25, VF=1.1, VR=1, V0=0.6):
            V = 1.4 * k * (T + T0) * np.log(1 + ((I + Iph) / I0)) / q + VF - V0 + np.random.uniform(-.00005, .00005)
            return V

        global getI
        getI = testIV

        global getV
        getV = testIVinv
        return [message, keithleyAddress[0]]

    success = 0
    for item in keithleyAddress:
        try:
            global rm
            global modelNum
            rm = pyvisa.ResourceManager()
            print('Attempting to connect to keithley.')
            keithleyObject = rm.open_resource(item)
            keithleyObject.baud_rate = 57600

            # if it is a 2600 series keithley
            if keithleyObject.query('*IDN?\n').contains("Model 26"):
                print("2600")
                keithley.baud_rate = 57600
                keithley.read_termination = '\n'
                keithley.write('smua.reset()')  # Reset the instrument
                keithley.write('smua.sense = smua.SENSE_REMOTE')  # Enable 4-wire sense
                modelNum = 2600
                print('Keithley setup done, ' + item)
                message = 'Keithley setup done, ' + item
                success = 1
            else:
                if keithleyObject.query('*IDN?\r').contains("Model 24"):
                    keithleyObject.read_termination = '\r'
                    print(keithleyObject.query('*IDN?\r'))
                    keithleyObject.write('*RST')
                    keithleyObject.write('SENS:FUNC:CONC OFF')
                    keithleyObject.write('SYST:RSEN ON')
                    keithleyObject.write('ROUT:TERM REAR')
                    print('Keithley setup done, ' + item)
                    message = 'Keithley setup done, ' + item
                    modelNum = 2400
                    success = 1
            break
        except:
            print('Could not establish connection with Keithley on: ' + item)
            message = 'Could not establish connection with Keithley on: ' + item

    if success:
        return [message, keithleyObject]
    else:
        print('\nCheck connection with Keithley')


def shutdownKeithley(keithley):
    if keithley == 'Test':
        print('Shutdown in Test Mode')
        return
    if modelNum == 2400:
        keithley.write('OUTP OFF')
    if modelNum == 2600:
        keithley.write('smua.source.output = smua.OUTPUT_OFF')
    keithley.close()


def openShutter(keithley):
    if keithleyObject == 'Test':
        global Iph
        activeArea = 1  # cm^2
        simulatedJsc = 22  # mA/cm^2
        photoCurrent = simulatedJsc * activeArea / 1000 + np.random.uniform(-.00050, .0005)
        Iph = photoCurrent  # Units are mAmps
        return


def closeShutter(keithley):
    if keithleyObject == 'Test':
        global Iph
        Iph = 0
        return


def prepareVoltage(keithley, NPLC=1, voltlimit=10, polarity='pin'):
    if keithley == 'Test':
        print('Prepare Voltage in Test Mode')
        return
    if polarity == 'pin':
        voltlimit *= -1
    if modelNum == 2600:
        keithley.write('smua.source.func = smua.OUTPUT_DCAMPS')
        keithley.write('smua.source.autorangei = smua.AUTORANGE_ON')
        keithley.write('smua.measure.v()')

        keithley.write(f'smua.source.limitv = {voltlimit}')
        keithley.write('smua.source.autorangev = smua.AUTORANGE_ON')

        keithley.write(f'smua.measure.nplc = {NPLC}')
        keithley.write(f'smua.trigger.count = 1')
        keithley.write('smua.source.output = smua.OUTPUT_ON')
    if modelNum == 2400:
        keithleyObject.write('SOUR:FUNC CURR')
        keithleyObject.write('SOUR:CURR:MODE FIXED')
        keithleyObject.write('SOUR:CURR:RANG:AUTO ON')
        keithleyObject.write('SENS:FUNC "VOLT"')
        keithleyObject.write('SENS:VOLT:PROT {:.3f}'.format(voltlimit))
        keithleyObject.write('SENS:VOLT:RANG:AUTO ON')
        keithleyObject.write('SENS:VOLT:NPLC {:.3f}'.format(NPLC))
        keithleyObject.write('TRIG:COUN 1')
        keithleyObject.write('OUTP ON')

    if keithleyObject == 'Test':
        return


def measureVoltage(keithleyObject, current=0, n=1, polarity='pin'):
    if polarity == 'pin':
        current *= -1

    rawDataArray = []
    # Assuming the keithleyObject can execute Lua commands and return the results
    if modelNum == 2600:
        for _ in range(n):
            measureVoltageCmd = 'print(smua.measure.v())\n'
            keithleyObject.write(measureVoltageCmd)
            voltageMeasurement = keithleyObject.read()
            rawDataArray.append(float(voltageMeasurement))

        if polarity == 'pin':
            rawDataArray = [-x for x in rawDataArray]

        # Creating a 2D numpy array, with each measurement as a new column in the single row
        data = np.array([rawDataArray])
    if modelNum == 2400:
        keithleyObject.write('SOUR:CURR:LEV {:.3f}'.format(current))
        rawData = keithleyObject.query_ascii_values('READ?')
        rawDataArray = np.array(rawData)
        for i in range(n - 1):
            rawData = keithleyObject.query_ascii_values('READ?')
            rawDataArray = np.vstack((rawDataArray, rawData))
        data = rawDataArray
        if polarity == 'pin':
            data[:, 0:2] *= -1
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

    if modelNum == 2600:
        keithleyObject.write('smua.source.func = smua.OUTPUT_DCVOLTS\n')
        keithleyObject.write('smua.source.autorangev = smua.AUTORANGE_ON\n')
        keithleyObject.write(f'smua.source.limiti = {currentlimit}\n')
        keithleyObject.write('smua.measure.autorangei = smua.AUTORANGE_ON\n')
        keithleyObject.write(f'smua.measure.nplc = {NPLC}\n')
        keithleyObject.write('smua.trigger.count = 1\n')
        keithleyObject.write('smua.source.output = smua.OUTPUT_ON\n')
    if modelNum == 2400:
        keithleyObject.write('SOUR:FUNC VOLT')
        keithleyObject.write('SOUR:VOLT:MODE FIXED')
        keithleyObject.write('SOUR:VOLT:RANG:AUTO ON')
        keithleyObject.write('SENS:FUNC "CURR"')
        keithleyObject.write('SENS:CURR:PROT {:.3f}'.format(currentlimit))
        keithleyObject.write('SENS:CURR:RANG:AUTO ON')
        keithleyObject.write('SENS:CURR:NPLC {:.3f}'.format(NPLC))
        keithleyObject.write('TRIG:COUN 1')
        keithleyObject.write('OUTP ON')


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
        if modelNum == 2600:
            for i in range(n):
                keithleyObject.write(f'smua.source.levelv = {voltage}\n')
                keithleyObject.write('smua.source.output = smua.OUTPUT_ON\n')
                keithleyObject.write('print(smua.measure.i())\n')
                currentMeasurement = float(keithleyObject.read())
                keithleyObject.write('smua.source.output = smua.OUTPUT_OFF\n')
                voltageValue = -voltage if polarity == 'pin' else voltage
                rawDataArray.append([voltageValue, currentMeasurement])
                dataCurrent = np.array(rawDataArray)

                return dataCurrent
        if modelNum == 2400:
            keithleyObject.write('SOUR:VOLT:LEV {:.3f}'.format(voltage))
            rawData = keithleyObject.query_ascii_values('READ?')
            rawDataArray = np.array(rawData)
            for i in range(n - 1):
                rawData = keithleyObject.query_ascii_values('READ?')
                rawDataArray = np.vstack((rawDataArray, rawData))
            data = rawDataArray
            if polarity == 'pin':
                data[:, 0:2] *= -1
            return data


def takeIV(keithleyObject, minV=-0.2, maxV=1.2, stepV=0.1, delay=10, forw=1, polarity='pin', NPLC=1, Ilimit=100E-3):
    '''
    Takes an IV sweep from minV to maxV with stepV, measuring current at each step.
    Returns a numpy array with columns for voltage, current, resistance, time, and status.
    '''
    delay /= 1000
    rawDataArray = []
    if modelNum == 2600:
        if polarity == 'pin' and keithleyObject != 'Test':
            minV, maxV = -maxV, -minV
            forw = not forw
        volts = np.arange(minV, maxV + stepV, stepV) if forw else np.arange(maxV, minV - stepV, -stepV)
        start = datetime.datetime.now()

        for volt in volts:
            keithleyObject.write(f'smua.source.levelv = {volt}\nsmua.source.output = smua.OUTPUT_ON\n')
            time.sleep(delay)
            keithleyObject.write('print(smua.measure.i())\n')
            currentMeasurement = float(keithleyObject.read())
            timeStamp = (datetime.datetime.now() - start).total_seconds()
            resistance = 9.91e+37
            status = 0b00000000
            rawData = [volt, currentMeasurement, resistance, timeStamp, status]
            rawDataArray.append(rawData)
        keithleyObject.write('smua.source.output = smua.OUTPUT_OFF\n')
        data = np.array(rawDataArray)
        return data
    if modelNum == 2400:
        if polarity == 'pin' and keithleyObject != 'Test':
            minV, maxV = -maxV, -minV
            forw = not forw
        if forw:
            startV, stopV = minV, maxV
        else:
            startV, stopV = maxV, minV
            stepV *= -1
        n = round(1 + (stopV - startV) / stepV)
        keithleyObject.timeout = 100000
        keithleyObject.write('SOUR:FUNC VOLT')
        keithleyObject.write('SOUR:VOLT:STAR {:.3f}'.format(startV))
        keithleyObject.write('SOUR:VOLT:STOP {:.3f}'.format(stopV))
        keithleyObject.write('SOUR:VOLT:STEP {:.3f}'.format(stepV))
        keithleyObject.write('SOUR:VOLT:MODE SWE')
        keithleyObject.write('SOUR:SWE:RANG AUTO')
        keithleyObject.write('SOUR:SWE:SPAC LIN')
        keithleyObject.write('SOUR:SWE:POIN {:d}'.format(n))
        keithleyObject.write('SOUR:DEL {:.3f}'.format(delay))
        keithleyObject.write('SENS:FUNC "CURR"')
        keithleyObject.write('SENS:CURR:PROT {:.3f}'.format(Ilimit))
        keithleyObject.write('SENS:CURR:NPLC {:.3f}'.format(NPLC))
        keithleyObject.write('TRIG:COUN {:d}'.format(n))
        keithleyObject.write('SYST:TIME:RES')
        keithleyObject.write('OUTP ON')
        try:
            rawData = keithleyObject.query_ascii_values('READ?')
        except:
            print('VisaIOError, ', datetime.now().strftime("%H:%M:%S"))
            rawData = []
            pass
        keithleyObject.write('OUTP OFF')
        data = np.reshape(rawData, (-1, 5))
        if polarity == 'pin':
            data[:, 0:2] *= -1
        return data


def setFrontTerminal(keithleyObject):
    if keithleyObject != 'Test':
        if modelNum == 2400:
            keithleyObject.write('ROUT:TERM FRON')
        return "Feature Doesn't Exist on 2651A"


def setRearTerminal(keithleyObject):
    if keithleyObject != 'Test':
        if modelNum == 2400:
            keithleyObject.write('ROUT:TERM REAR')
        return "Feature Doesn't Exist on 2651A"


if __name__ == "__main__":
    import matplotlib.pyplot as plt

    rm = pyvisa.ResourceManager(r'C:\WINDOWS\system32\visa32.dll')
    print(rm.list_resources('?*'))
    keithleyObject = connectToKeithley('ASRL13::INSTR')
    polarity = 'pin'
    forw = 1
    prepareVoltage(keithleyObject)
