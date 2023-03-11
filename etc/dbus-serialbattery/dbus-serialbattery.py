#!/usr/bin/python
# -*- coding: utf-8 -*-

from __future__ import absolute_import, division, print_function, unicode_literals
from time import sleep
from dbus.mainloop.glib import DBusGMainLoop
from threading import Thread
import dbus
try:
  import gobject
except ImportError:
  from gi.repository import GLib as gobject
import logging
import sys

from dbushelper import DbusHelper
from utils import DRIVER_VERSION, DRIVER_SUBVERSION
import battery
from lltjbd import LltJbd
from daly import Daly
from ant import Ant
from jkbms_mqtt import JkbmsMqtt
from jkbms import Jkbms
from sinowealth import Sinowealth
#from mnb import MNB

# Logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

logging.info('Starting dbus-serialbattery')


def main():

    def poll_battery(loop):
        # Run in separate thread. Pass in the mainloop so the thread can kill us if there is an exception.
        poller = Thread(target=lambda: helper.publish_battery(loop))
        # Thread will die with us if deamon
        poller.daemon = True
        poller.start()
        return True

    def get_battery_type(_port):
        # all the different batteries the driver support and need to test for
        battery_types = [
            LltJbd(port=_port, baud=9600),
            Ant(port=_port, baud=19200),
            Daly(port=_port, baud=9600, address=b"\x40"),
            Daly(port=_port, baud=9600, address=b"\x80"),
            Jkbms(port=_port, baud=115200),
            Sinowealth(port=_port, baud=9600),
            # MNB(port=_port, baud=9600),
        ]

        if port.startswith('jkbms'):
            return JkbmsMqtt(port=port, baud=9600)


        if len(sys.argv) > 2:
            test = battery_types[int(sys.argv[2])]
            count = 5
            while count > 0:
                if test.test_connection():
                    logger.info('Connection established to ' + test.__class__.__name__)
                    return test
                logger.error('Connection failed to ' + test.__class__.__name__)
                sleep(1)
                count -= 1
            return None

        # try to establish communications with the battery 3 times, else exit
        count = 3
        while count > 0:
            # create a new battery object that can read the battery and run connection test
            for test in battery_types:
                logger.info('Testing ' + test.__class__.__name__)
                if test.test_connection() is True:
                    logger.info('Connection established to ' + test.__class__.__name__)
                    return test

            count -= 1
            sleep(0.5)

        return None

    def get_port():
        # Get the port we need to use from the argument
        if len(sys.argv) > 1:
            return sys.argv[1]
        else:
            # just for MNB-SPI
            logger.info('No Port needed')
            return '/dev/tty/USB9'

    logger.info('dbus-serialbattery v' + str(DRIVER_VERSION) + DRIVER_SUBVERSION)

    port = get_port()
    battery = get_battery_type(port)

    # exit if no battery could be found
    if battery is None:
        logger.error("ERROR >>> No battery connection at " + port)
        return

    # Have a mainloop, so we can send/receive asynchronous calls to and from dbus
    DBusGMainLoop(set_as_default=True)
    gobject.threads_init()
    mainloop = gobject.MainLoop()

    # Get the initial values for the battery used by setup_vedbus
    port = None
    if len(sys.argv) > 3:
        port = sys.argv[3]
    helper = DbusHelper(battery, port=port)
    if not helper.setup_vedbus():
        logger.error("ERROR >>> Problem with battery set up at " + port)
        return
    logger.info('Battery connected to dbus from ' + port)


    # Poll the battery at INTERVAL and run the main loop
    gobject.timeout_add(battery.poll_interval, lambda: poll_battery(mainloop))
    try:
        mainloop.run()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
