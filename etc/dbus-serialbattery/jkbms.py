# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function, unicode_literals
from battery import Protection, Battery, Cell
from utils import *
from struct import *

import paho.mqtt.client as mqtt
import time



class Jkbms(Battery):

    def __init__(self, port, baud):
        super(Jkbms, self).__init__(port, baud)
        self.type = self.BATTERYTYPE
        self.cells = [Cell(0) for _ in range(16)]
        self.voltage_cell = {}
        self._current_charge = 0
        self._current_discharge = 0
        self._mos_temp = 0
        self._last_msg = 0
        self._attr = {}
        self.client = mqtt.Client()
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.connect("127.0.0.1", 1883, 60)
        self.client.loop_start()

    def on_message(self, client, userdata, msg):
        try:
            print(msg.topic+" "+str(msg.payload))
        except:
            print(msg.topic+" cannot decode payload")
        _, _, k, x = msg.topic.split('/')
        v = msg.payload
        if x != 'value':
            return
        self._last_msg = time.time()
        try:
            self._attr[k] = float(v)
        except ValueError:
            self._attr[k] = v

        if k == 'battery_voltage':
            self.voltage = float(v)
        elif k == 'current_charge':
            self._current_charge = float(v)
            if float(v) > 0:
                self.current = float(v)
        elif k == 'current_discharge':
            self._current_discharge = float(v)
            if float(v) > 0:
                self.current = -1*float(v)
        elif k == 'percent_remain':
            self.soc = float(v)
        elif k == 'battery_t1':
            self.temp1 = float(v)
        elif k == 'battery_t2':
            self.temp2 = float(v)
        elif k == 'mos_temp':
            self._mos_temp = float(v)
        elif k.startswith('voltage_cell'):
            n = int(k[len('voltage_cell'):]) - 1
            if n < len(self.cells):
                self.cells[n].voltage = float(v)
            self.voltage_cell[n] = float(v)
        elif k == 'cycle_count':
            self.cycles = int(v)
        elif k == 'capacity_remain':
            self.capacity_remain = float(v)
        elif k == 'cycle_capacity':
            self.total_ah_drawn = float(v)
        elif k == 'balance_current':
            self.balancing = float(v) > 0
        elif k == 'hardware_version':
            self.hardware_version = 'JKBMS HW ' + str(v)
        elif k == 'software_version':
            self.version = 'JKBMS SW ' + str(v)
        else:
            print("  unparsed")


    def on_connect(self, client, userdata, flags, rc):
        print("Connected with result code "+str(rc))
        client.subscribe("jkbms/#")

    balancing = 0
    BATTERYTYPE = "JKBMS"

    def test_connection(self):
        # call a function that will connect to the battery, send a command and retrieve the result.
        # The result or call should be unique to this BMS. Battery name or version, etc.
        # Return True if success, False for failure
        # return self.read_status_data()
        return True

    def get_settings(self):
        # After successful  connection get_settings will be call to set up the battery.
        # Set the current limits, populate cell count, etc
        # Return True if success, False for failure
        self.max_battery_current = MAX_BATTERY_CURRENT
        self.max_battery_discharge_current = MAX_BATTERY_DISCHARGE_CURRENT

        self.voltage = None
        current, self.soc = None, None
        self.current = None

        self.cell_count = 16
        self.max_battery_voltage = MAX_CELL_VOLTAGE * self.cell_count
        self.min_battery_voltage = MIN_CELL_VOLTAGE * self.cell_count

        self.cell_max_no = None
        self.cell_min_no = None
        self.cell_max_voltage = None
        self.cell_min_voltage = None
        
        self.capacity = 280

        self.capacity_remain = None
        
        self.total_ah_drawn = None
        self.cycles = None
        
        self.charge_fet, self.discharge_fet, self.balancing = 1, 1, False

        self.temp1, self.temp2 = None, None

        self.hardware_version = "JKBMS " + str(self.cell_count) + " cells"
        
        # Alarms
        self.protection.voltage_high = 0
        self.protection.voltage_low = 0
        self.protection.voltage_cell_low = 0
        self.protection.temp_high_charge = 0
        self.protection.temp_high_discharge = 0
        self.protection.current_over = 0
        self.protection.current_under = 0
        
        self.version = "JKBMS V0.1"
        logger.info(self.hardware_version)
        return True

    def refresh_data(self):
        # call all functions that will refresh the battery data.
        # This will be called for every iteration (1 second)
        # Return True if success, False for failure
        result = self.read_status_data()
        return result

    def read_status_data(self):
   
        if self.voltage_cell:
            #self.cell_max_voltage = max(self.voltage_cell.values())
            #self.cell_min_voltage = min(self.voltage_cell.values())

            #self.cell_max_no = [n for n, v in self.voltage_cell.items() if v == self.cell_max_voltage][0]
            #self.cell_min_no = [n for n, v in self.voltage_cell.items() if v == self.cell_min_voltage][0]

            cell_min = min([c.voltage for c in self.cells])
            print('cell_min', cell_min)
            if cell_min > 0.1:
                self.protection.voltage_cell_low = 2 if cell_min < MIN_CELL_VOLTAGE - 0.1 else 1 if cell_min < MIN_CELL_VOLTAGE else 0
            else:
                self.protection.voltage_cell_low = 0



        # Alarms
        if self.voltage is not None:
            self.protection.voltage_high = 2 if self.voltage > self.max_battery_voltage else 0
            self.protection.voltage_low = 2 if self.voltage < self.min_battery_voltage else 0
        if self._mos_temp is not None:
            self.protection.temp_high_charge = 2 if self._mos_temp > 50 else 0
            self.protection.temp_high_discharge = 2 if self._mos_temp > 50 else 0
        # self.protection.current_over = 2 if self.charge_fet==3 else 0
        # self.protection.current_under = 2 if self.discharge_fet==3 else 0
        
        return True
        
    def get_balancing(self): 
        return 1 if self.balancing or self.balancing == 2 else 0
