# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function, unicode_literals
import logging
import utils

# Logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)



class Protection(object):
    # 2 = Alarm, 1 = Warning, 0 = Normal
    def __init__(self):
        self.voltage_high = None
        self.voltage_low = None
        self.voltage_cell_low = None
        self.soc_low = None
        self.current_over = None
        self.current_under = None
        self.cell_imbalance = None
        self.internal_failure = None
        self.temp_high_charge = None
        self.temp_low_charge = None
        self.temp_high_discharge = None
        self.temp_low_discharge = None


class Cell:
    voltage = None
    balance = None

    def __init__(self, balance):
        self.balance = balance


class Battery(object):

    def __init__(self, port, baud):
        self.port = port
        self.baud_rate = baud
        self.role = 'battery'
        self.type = 'Generic'
        self.poll_interval = 1000

        self.hardware_version = None
        self.voltage = None
        self.current = None
        self.capacity_remain = None
        self.capacity = None
        self.cycles = None
        self.total_ah_drawn = None
        self.production = None
        self.protection = Protection()
        self.version = None
        self.soc = None
        self.charge_fet = None
        self.discharge_fet = None
        self.cell_count = None
        self.temp_sensors = None
        self.temp_internal = None
        self.temp1 = None
        self.temp2 = None
        self.cells = []
        self.control_charging = None
        self.control_voltage = None
        self.control_current = None
        self.control_previous_total = None
        self.control_previous_max = None
        self.control_discharge_current = None
        self.control_charge_current = None
        self.control_allow_charge = None
        self.control_allow_discharge = True
        # max battery charge/discharge current
        self.max_battery_current = None
        self.max_battery_discharge_current = None
        self.balancing = None

    def test_connection(self):
        # Each driver must override this function to test if a connection can be made
        # return false when fail, true if successful
        return False

    def get_settings(self):
        # Each driver must override this function to read/set the battery settings
        # It is called once after a successful connection by DbusHelper.setup_vedbus()
        # Values:  battery_type, version, hardware_version, min_battery_voltage, max_battery_voltage,
        #   MAX_BATTERY_CURRENT, MAX_BATTERY_DISCHARGE_CURRENT, cell_count, capacity
        # return false when fail, true if successful
        return False

    def refresh_data(self):
        # Each driver must override this function to read battery data and populate this class
        # It is called each poll just before the data is published to vedbus
        # return false when fail, true if successful
        return False

    def to_temp(self, sensor, value):
        # Keep the temp value between -20 and 100 to handle sensor issues or no data.
        # The BMS should have already protected before those limits have been reached.
        if sensor == 1:
            self.temp1 = min(max(value, -20), 100)
        if sensor == 2:
            self.temp2 = min(max(value, -20), 100)
        if sensor == 0:
            self.temp_internal = min(max(value, -20), 100)

    def linear(self, value, threshold, max_value):
        if value < threshold:
            return 1.0
        return max((1 - (value - threshold)/(max_value - threshold)), 0.0)

    def manage_charge_current(self):


        # Start with the current values
        max_cell_voltage = self.get_max_cell_voltage() or None
        min_cell_voltage = self.get_min_cell_voltage() or None
        if (max_cell_voltage is None or min_cell_voltage is None or
                self.soc is None or self.voltage is None):
            self.control_charge_current = 1
            self.control_discharge_current = 1
            self.control_allow_charge = False
            self.control_allow_discharge = False
            logger.warning('Invalid battery state, disabling charging.')
            return
        # our input data
        logger.info('SoC %d, Cells %.3fV-%.3fV, Pack %.2fV' % (
            self.soc, min_cell_voltage, max_cell_voltage, self.voltage))

        cell_limiter = self.max_battery_voltage_warning / self.cell_count
        cell_limiter_hi = self.max_battery_voltage / self.cell_count
        cell_limiter_lo_warn = self.min_battery_voltage_warning / self.cell_count
        cell_limiter_lo = self.min_battery_voltage / self.cell_count

        limits = dict(
            cell = self.linear(
                max_cell_voltage, cell_limiter, cell_limiter_hi),
            pack = self.linear(
                self.voltage, self.max_battery_voltage_warning,
                self.max_battery_voltage),
            soc = self.linear(self.soc, 95, 100)
        )
        for k, v in limits.items():
            limits[k] = int(v * self.max_battery_current)

        self.control_charge_current = min(limits['cell'], max(
            limits['pack'], limits['soc']))
        logger.info('Max Charge Current: Cell %dA, Pack %dA, SoC %dA -> %dA' % (
            limits['cell'], limits['pack'], limits['soc'],
            self.control_charge_current))

        limits = dict(
            cell = self.linear(
                -1*min_cell_voltage,
                -1*cell_limiter_lo_warn,
                -1*cell_limiter_lo),
            pack = self.linear(
                -1*self.voltage,
                -1*self.min_battery_voltage_warning,
                -1*self.min_battery_voltage),
            soc = self.linear(-1*self.soc, -10, -20)
        )
        for k, v in limits.items():
            limits[k] = int(v * self.max_battery_discharge_current)

        self.control_discharge_current = min(limits['cell'], max(
            limits['pack'], limits['soc']))
        logger.info('Max Discharge Current: Cell %dA, Pack %dA, SoC %dA -> %dA' % (
            limits['cell'], limits['pack'], limits['soc'],
            self.control_discharge_current))

        # Change depending on the SOC values
        self.control_allow_charge = max_cell_voltage < cell_limiter_hi
        self.control_allow_discharge = min_cell_voltage > cell_limiter_lo
           

    def get_min_cell(self):
        min_voltage = 9999
        min_cell = None
        if len(self.cells) == 0 and hasattr(self, 'cell_min_no'):
            return self.cell_min_no

        for c in range(min(len(self.cells), self.cell_count)):
            if self.cells[c].voltage is not None and min_voltage > self.cells[c].voltage:
                min_voltage = self.cells[c].voltage
                min_cell = c
        return min_cell

    def get_max_cell(self):
        max_voltage = 0
        max_cell = None
        if len(self.cells) == 0 and hasattr(self, 'cell_max_no'):
            return self.cell_max_no

        for c in range(min(len(self.cells), self.cell_count)):
            if self.cells[c].voltage is not None and max_voltage < self.cells[c].voltage:
                max_voltage = self.cells[c].voltage
                max_cell = c
        return max_cell

    def get_min_cell_desc(self):
        cell_no = self.get_min_cell()
        if cell_no is None:
            return None
        return 'C' + str(cell_no + 1)

    def get_max_cell_desc(self):
        cell_no = self.get_max_cell()
        if cell_no is None:
            return None
        return 'C' + str(cell_no + 1)

    def get_min_cell_voltage(self):
        min_voltage = 9999
        if len(self.cells) == 0 and hasattr(self, 'cell_min_voltage'):
            return self.cell_min_voltage

        for c in range(min(len(self.cells), self.cell_count)):
            if self.cells[c].voltage is not None and min_voltage > self.cells[c].voltage:
                min_voltage = self.cells[c].voltage
        return None if min_voltage == 9999 else min_voltage

    def get_max_cell_voltage(self):
        max_voltage = 0
        if len(self.cells) == 0 and hasattr(self, 'cell_max_voltage'):
            return self.cell_max_voltage

        for c in range(min(len(self.cells), self.cell_count)):
            if self.cells[c].voltage is not None and max_voltage < self.cells[c].voltage:
                max_voltage = self.cells[c].voltage
        return None if max_voltage == 0 else max_voltage

    def get_balancing(self):
        if self.balancing is not None:
            return 1
        for c in range(min(len(self.cells), self.cell_count)):
            if self.cells[c].balance is not None and self.cells[c].balance:
                return 1
        return 0

    def get_temp(self):
        if self.temp1 is not None and self.temp2 is not None:
            return round((float(self.temp1) + float(self.temp2)) / 2, 2)
        if self.temp1 is not None and self.temp2 is None:
            return round(float(self.temp1) , 2)
        if self.temp1 is None and self.temp2 is not None:
            return round(float(self.temp2) , 2)
        else:
            return None

    def get_min_temp(self):
        if self.temp1 is not None and self.temp2 is not None:
            return min(self.temp1, self.temp2)
        if self.temp1 is not None and self.temp2 is None:
            return self.temp1
        if self.temp1 is None and self.temp2 is not None:
            return self.temp2
        else:
            return None

    def get_max_temp(self):
        if self.temp1 is not None and self.temp2 is not None:
            return max(self.temp1, self.temp2)
        if self.temp1 is not None and self.temp2 is None:
            return self.temp1
        if self.temp1 is None and self.temp2 is not None:
            return self.temp2
        else:
            return None
        
