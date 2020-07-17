import re
import os
import sys
import  sqlalchemy as db
import logging
import logging.handlers
import datetime
import ipaddress
from utilities import utils, db
import pandas as pd
import numpy as np
from features.real_time_traffic_monitoring.real_time_device_traffic import RealTimeMonitor

class InsertTestTrafficData :
	def __init__(self, test_link_id = -1):

		self.traffic_monitor_table_name = "traffic_monitor"
		self.link_id = test_link_id


		self.DB = os.getenv('postgres_DB', None)
		self.app_name = "Insert Test Traffic Data"
		self.enable_logging = True

		self.cnn = None
		self.engine = None
		self.metadata = None

	def run(self):
		from random import randrange
		logger = utils.log_setup(self.app_name, self.enable_logging)
		self.engine, self.cnn, self.metadata = db.connect_to_postgres(logger, self.DB)

		real_time_monitor = RealTimeMonitor(link_id = -1, server_ip = 'test', client_ip = 'test', link_name = "test",
			set_datetime = False)

		real_time_monitor.cnn = self.cnn

		dt = datetime.datetime(2019, 1, 1)
		end = datetime.datetime.today()
		step = datetime.timedelta(days=1)

		real_time_monitor.create_traffic_monitor(logger)

		while dt < end:
			values = {
				"server_ip" : "test",
				"client_ip" : "test",
				"both_tx_max" : randrange(100),
				"both_tx_avg" : randrange(100),
				"both_tx_min" : randrange(100),
				"both_rx_max" : randrange(100),
				"both_rx_avg" : randrange(100),
				"both_rx_min" : randrange(100),
				"send_tx_max" : randrange(100),
				"send_tx_avg" : randrange(100),
				"send_tx_min" : randrange(100),
				"receive_rx_max" : randrange(100),
				"receive_rx_avg" : randrange(100),
				"receive_rx_min" : randrange(100),
				"datetime" : dt,
				"status" : "done",
				"error_details" : None
			}

			real_time_monitor.insert(values)
			dt += step


if __name__ == '__main__':
	InsertTestTrafficData().run()