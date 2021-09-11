# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function, unicode_literals
from battery import Protection, Battery, Cell
from utils import *
from struct import *
import serial

class Jkbms(Battery):

    def __init__(self, port,baud):
        super(Jkbms, self).__init__(port,baud)
        self.type = self.BATTERYTYPE
        self._serial = None

    BATTERYTYPE = "Jkbms"
    LENGTH_CHECK = 1
    LENGTH_POS = 2
    LENGTH_SIZE = '>H'
    CURRENT_ZERO_CONSTANT = 32768
    command_status = b"\x4E\x57\x00\x13\x00\x00\x00\x00\x06\x03\x00\x00\x00\x00\x00\x00\x68\x00\x00\x01\x29"

    def test_connection(self):
        # call a function that will connect to the battery, send a command and retrieve the result.
        # The result or call should be unique to this BMS. Battery name or version, etc.
        # Return True if success, False for failure
        return self.read_status_data()

    def get_settings(self):
        # After successful  connection get_settings will be call to set up the battery.
        # Set the current limits, populate cell count, etc
        # Return True if success, False for failure
        self.max_battery_current = MAX_BATTERY_CURRENT
        self.max_battery_discharge_current = MAX_BATTERY_DISCHARGE_CURRENT
        self.max_battery_voltage = MAX_CELL_VOLTAGE * self.cell_count
        self.min_battery_voltage = MIN_CELL_VOLTAGE * self.cell_count

        # init the cell array
        while len(self.cells) < self.cell_count:
          self.cells.append(Cell(False))

        self.hardware_version = "JKBMS " + str(self.cell_count) + " cells"
        return True

    def refresh_data(self):
        # call all functions that will refresh the battery data.
        # This will be called for every iteration (1 second)
        # Return True if success, False for failure
        result = self.read_status_data()

        return result

    def get_data(self, bytes, idcode, length):
        start = bytes.find(idcode)
        if start < 0: return False
        ret = bytes[start+1:start+length+1]
        del bytes[start:start+length+1]
        return ret

    def read_status_data(self):
        status_data = self.read_serial_data_jkbms(self.command_status)
        # check if connection success
        if status_data is False:
            return False
        del status_data[0]
        # cell voltages
        cellbyte_count = unpack_from('>B', self.get_data(status_data, b'\x79', 1))[0]
        while len(self.cells) < (cellbyte_count/3):
            self.cells.append(Cell(False))
        for c in self.cells:
            c.voltage = unpack_from('>xH', status_data)[0]/1000
            del status_data[:3]
        temp0 =  unpack_from('>H', self.get_data(status_data, b'\x80', 2))[0] 
        temp1 =  unpack_from('>H', self.get_data(status_data, b'\x81', 2))[0] 
        temp2 =  unpack_from('>H', self.get_data(status_data, b'\x82', 2))[0] 
        self.to_temp(0, temp0 if temp0 <= 100 else 100 - temp0)
        self.to_temp(1, temp1 if temp1 <= 100 else 100 - temp1)
        self.to_temp(2, temp2 if temp2 <= 100 else 100 - temp2)
        
        voltage = unpack_from('>H', self.get_data(status_data, b'\x83', 2))[0]
        self.voltage = voltage / 100

        current = unpack_from('>H', self.get_data(status_data, b'\x84', 2))[0]
        self.current = current / -100 if current < self.CURRENT_ZERO_CONSTANT else (current - self.CURRENT_ZERO_CONSTANT) / 100

        self.soc =  unpack_from('>B', self.get_data(status_data, b'\x85', 1))[0] 
        if self.soc > 100:
            logger.error('Invalid soc: %r' % [status_data])

        temperature_sensor_count =  unpack_from('>B', self.get_data(status_data, b'\x86', 1))[0] 
        self.cycles =  unpack_from('>H', self.get_data(status_data, b'\x87', 2))[0] 
        # 0x88 does not exist
        self.capacity_remain = unpack_from('>L', self.get_data(status_data, b'\x89', 4))[0]

        self.cell_count = unpack_from('>H', self.get_data(status_data, b'\x8A', 2))[0]
        if self.cell_count != len(self.cells):
            logger.error('Misconfigured number of cells, got %d' % self.cell_count)
            return False

        protection = self.to_protection_bits(unpack_from('>H', self.get_data(status_data, b'\x8B', 2))[0] )
        self.to_fet_bits(unpack_from('>H', self.get_data(status_data, b'\x8C', 2))[0] )
        # 8D does not exist
        self._internal = dict(
            battery_over_voltage =  unpack_from('>H', self.get_data(status_data, b'\x8E', 2))[0] / 100.0,
            battery_under_voltage =  unpack_from('>H', self.get_data(status_data, b'\x8F', 2))[0] / 100.0,
            cell_over_voltage =  unpack_from('>H', self.get_data(status_data, b'\x90', 2))[0] / 1000.0,
            cell_over_voltage_recovery =  unpack_from('>H', self.get_data(status_data, b'\x91', 2))[0] / 1000.0,
            cell_over_voltage_delay =  unpack_from('>H', self.get_data(status_data, b'\x92', 2))[0],
            cell_under_voltage =  unpack_from('>H', self.get_data(status_data, b'\x93', 2))[0] / 1000.0,
            cell_under_voltage_recovery =  unpack_from('>H', self.get_data(status_data, b'\x94', 2))[0] / 1000.0,
            cell_under_voltage_delay =  unpack_from('>H', self.get_data(status_data, b'\x95', 2))[0],
            cell_diff_voltage_max =  unpack_from('>H', self.get_data(status_data, b'\x96', 2))[0]/1000.0,
            discharge_over_current =  unpack_from('>H', self.get_data(status_data, b'\x97', 2))[0],
            discharge_over_current_delay =  unpack_from('>H', self.get_data(status_data, b'\x98', 2))[0],
            charge_over_current =  unpack_from('>H', self.get_data(status_data, b'\x99', 2))[0],
            charge_over_current_delay =  unpack_from('>H', self.get_data(status_data, b'\x9a', 2))[0],
            balancer_start_voltage =  unpack_from('>H', self.get_data(status_data, b'\x9b', 2))[0] / 1000.0,
            balancer_min_diff_voltage =  unpack_from('>H', self.get_data(status_data, b'\x9c', 2))[0] / 1000.0,
            balancing =  unpack_from('>B', self.get_data(status_data, b'\x9d', 1))[0] == 1,
            mos_over_temperature =  unpack_from('>H', self.get_data(status_data, b'\x9e', 2))[0],
            mos_over_temperature_recovery =  unpack_from('>H', self.get_data(status_data, b'\x9f', 2))[0],
            cell_over_temperature =  unpack_from('>H', self.get_data(status_data, b'\xa0', 2))[0],
            cell_over_temperature_recovery =  unpack_from('>H', self.get_data(status_data, b'\xa1', 2))[0],
            cell_diff_protection =  unpack_from('>H', self.get_data(status_data, b'\xa2', 2))[0],
            cell_charge_high_temperature =  unpack_from('>H', self.get_data(status_data, b'\xa3', 2))[0],
            cell_discharge_high_temperature =  unpack_from('>H', self.get_data(status_data, b'\xa4', 2))[0],
            charge_low_temperature =  unpack_from('>H', self.get_data(status_data, b'\xa5', 2))[0],
            charge_low_temperature_recovery =  unpack_from('>H', self.get_data(status_data, b'\xa6', 2))[0],
            discharge_low_temperature =  unpack_from('>H', self.get_data(status_data, b'\xa7', 2))[0],
            discharge_low_temperature_recovery =  unpack_from('>H', self.get_data(status_data, b'\xa8', 2))[0],
            cell_count_setting = unpack_from('>B', self.get_data(status_data, b'\xA9', 1))[0],
            capacity = unpack_from('>L', self.get_data(status_data, b'\xAA', 4))[0],
            charge_switch =  unpack_from('>B', self.get_data(status_data, b'\xAB', 1))[0],
            discharge_switch =  unpack_from('>B', self.get_data(status_data, b'\xAC', 1))[0],
            current_calibration =  unpack_from('>H', self.get_data(status_data, b'\xAD', 2))[0],
            guard_plate_address =  unpack_from('>B', self.get_data(status_data, b'\xAE', 1))[0],
            battery_type =  unpack_from('>B', self.get_data(status_data, b'\xAF', 1))[0],
            sleep_time =  unpack_from('>H', self.get_data(status_data, b'\xB0', 2))[0],
            soc_low =  unpack_from('>B', self.get_data(status_data, b'\xb1', 1))[0],
            password =  unpack_from('>10s', self.get_data(status_data, b'\xb2', 10))[0].rstrip(b'\0'),
            special_charger_switch =  unpack_from('>B', self.get_data(status_data, b'\xb3', 1))[0],
            production = unpack_from('>8s', self.get_data(status_data, b'\xB4', 8))[0].rstrip(b'\0'),
            manufactured = unpack_from('>4s', self.get_data(status_data, b'\xB5', 4))[0].rstrip(b'\0'),
            system_working_time = unpack_from('>L', self.get_data(status_data, b'\xB6', 4))[0],
            version = unpack_from('>15s', self.get_data(status_data, b'\xB7', 15))[0].rstrip(b'\0'),
            calibration_start =  unpack_from('>B', self.get_data(status_data, b'\xb8', 1))[0],
            battery_capacity_estimated = unpack_from('>L', self.get_data(status_data, b'\xB9', 4))[0],
            # This does not exist in all replies
            # manufacturer_id = unpack_from('>24s', self.get_data(status_data, b'\xBA', 24))[0].rstrip(b'\0'),
            # _restart =  unpack_from('>B', self.get_data(status_data, b'\xbb', 1))[0],
            # _restore =  unpack_from('>B', self.get_data(status_data, b'\xbc', 1))[0],
            # _start_upgrade =  unpack_from('>B', self.get_data(status_data, b'\xbd', 1))[0],
            # gps_low_voltage =  unpack_from('>H', self.get_data(status_data, b'\xbe', 2))[0] / 1000.0,
            # gps_low_voltage_recovery =  unpack_from('>H', self.get_data(status_data, b'\xbf', 2))[0] / 1000.0,
            # data_format_version =  unpack_from('>H', self.get_data(status_data, b'\xc0', 1))[0],
        )
        self.balancing = self._internal['balancing']
        self.capacity = self._internal['capacity']
        self.production = self._internal['production']
        self.version = self._internal['version']

        logger.info('%.2fV %.1f%% P%s' % (self.voltage, self.soc, protection))
        return True
       
    def to_fet_bits(self, byte_data):
        tmp = bin(byte_data)[2:].rjust(2, zero_char)
        self.charge_fet = is_bit_set(tmp[1])
        self.discharge_fet = is_bit_set(tmp[0])

    def to_protection_bits(self, byte_data):
        pos=13
        tmp = bin(byte_data)[15-pos:].rjust(pos + 1, zero_char)
        self.protection.soc_low = 2 if is_bit_set(tmp[pos-0]) else 0
        self.protection.set_IC_inspection = 2 if is_bit_set(tmp[pos-1]) else 0 # BMS over temp
        self.protection.voltage_high = 2 if is_bit_set(tmp[pos-2]) else 0
        self.protection.voltage_low = 2 if is_bit_set(tmp[pos-3]) else 0
        self.protection.current_over = 1 if is_bit_set(tmp[pos-5]) else 0
        self.protection.current_under = 1 if is_bit_set(tmp[pos-6]) else 0
        self.protection.cell_imbalance = 2 if is_bit_set(tmp[pos-7]) else 1 if is_bit_set(tmp[pos-10]) else 0
        self.protection.voltage_cell_low = 2 if is_bit_set(tmp[pos-11]) else 0        
        # there is just a BMS and Battery temp alarm (not high/low)
        self.protection.temp_high_charge = 1 if is_bit_set(tmp[pos-4]) or is_bit_set(tmp[pos-8]) else 0
        self.protection.temp_low_charge = 1 if is_bit_set(tmp[pos-4]) or is_bit_set(tmp[pos-8]) else 0
        self.protection.temp_high_discharge = 1 if is_bit_set(tmp[pos-4]) or is_bit_set(tmp[pos-8]) else 0
        self.protection.temp_low_discharge = 1 if is_bit_set(tmp[pos-4]) or is_bit_set(tmp[pos-8]) else 0
        return tmp

        
    def read_serial_data_jkbms(self, command):
        if True:
            # Keep the port persistently open.
            try:
                if not self._serial:
                    self._serial = serial.Serial(self.port, baudrate=self.baud_rate, timeout=1.0)
                    self._serial.flushOutput()
                    self._serial.flushInput()
                self._serial.write(command)
                start_data = self._serial.read(11)
                if len(start_data) < 11:
                    logger.error('Did not receive enough header data')
                    return False
                start, length, terminal, cmd, crc, tt = unpack_from('>HHLBBB', start_data)
                # Do checks
                serial_data = self._serial.read(length - 9)
                # self._serial.close()
            except serial.SerialException as e:
                self._serial = None
                logger.error(e)
                return False
            if not serial_data:
                return False
            data = bytearray()
            data.extend(start_data)
            data.extend(serial_data)
        else:

            # use the read_serial_data() function to read the data and then do BMS spesific checks (crc, start bytes, etc)
            data = read_serial_data(command, self.port, self.baud_rate, self.LENGTH_POS,
                                    self.LENGTH_CHECK, None, self.LENGTH_SIZE)
            if data is False:
                return False
            start, length, terminal, cmd, crc, tt = unpack_from('>HHLBBB', data)

        frame, frame1, end, crc_hi, crc_lo = unpack_from('>HHBHH', data[-9:])

        if start != 0x4E57 or end != 0x68:
            logger.error(">>> ERROR: Incorrect Reply magic bytes: %04x %02x" % (start, end))
            return False

        crc_calc = sum(data[0:-4])
        if crc_calc != crc_lo:
            logger.error('CRC checksum mismatch: Expected 0x%04x, Got 0x%04x' % (crc_lo, crc_calc))
            return False

        if cmd != 6:
            logger.error('Got wrong command code back: 0x%02x' % cmd)
            return False

        if tt != 1:
            logger.error('Got wrong transmission type code back: 0x%02x' % tt)
            return False
        

        return data[10:-9]
