from threading import Thread
import paramiko
import re
import os
import sys
import  sqlalchemy as db
import logging
import logging.handlers
import datetime
import ipaddress
from utilities import utils, db
from routeros.api_dev import Api, receive_from_api
import pandas as pd
from queue import Queue
import numpy as np

class RealTimeMonitor :
	def __init__(self, link_id = "0", server_ip = '192.168.0.1', server_username = 'username', 
		server_password = 'password', client_ip = '192.168.0.2', client_username = 'username',
		client_password = 'password', link_name = "test_link", insert_to_db = True, set_datetime = True):

		self.server = {
			"IP" : server_ip,
			"username" : server_username,
			"password" : server_password
		}

		self.client = {
			"IP" : client_ip,
			"username" : client_username,
			"password" : client_password
		}

		self.task_id = None
		self.traffic_monitor_table_name = "traffic_monitor"
		self.link_name = link_name
		self.link_id = link_id


		self.DB = os.getenv('postgres_DB', None)
		self.app_name = "Real Time Traffic Monitoring"
		self.enable_logging = True
		self.insert_to_db = insert_to_db
		self.set_datetime = set_datetime

		self.cnn = None
		self.engine = None
		self.metadata = None

	def create_traffic_monitor(self, logger):
		query = '''
			create table if not exists public.{}(
				"id" serial,
				"send_tx_max" bigint,
				"send_tx_avg" bigint,
				"send_tx_min" bigint,
				"receive_rx_max" bigint,
				"receive_rx_avg" bigint,
				"receive_rx_min" bigint,
				"both_tx_max" bigint,
				"both_tx_avg" bigint,
				"both_tx_min" bigint,
				"both_rx_max" bigint,
				"both_rx_avg" bigint,
				"both_rx_min" bigint,
				"datetime" timestamp,
				"link_id" bigint,
				"status" text,
				"error_details" text
			)
		'''.format(self.traffic_monitor_table_name)
		logger.info("Creating table {} if not exists".format(self.traffic_monitor_table_name))
		self.cnn.execute(query)

	def insert(self, values):
		if(self.set_datetime):
			values["datetime"] = datetime.datetime.now()
		values["link_id"] = self.link_id
		query = '''
			insert into public.{} ("send_tx_max", "send_tx_avg", "send_tx_min", 
			"receive_rx_max", "receive_rx_avg", "receive_rx_min", "both_tx_max", "both_tx_avg", "both_tx_min", 
			"both_rx_max", "both_rx_avg", "both_rx_min", "datetime", "link_id", "status", "error_details")
			values (%(send_tx_max)s, %(send_tx_avg)s, %(send_tx_min)s,
			%(receive_rx_max)s, %(receive_rx_avg)s, %(receive_rx_min)s, %(both_tx_max)s, %(both_tx_avg)s, 
			%(both_tx_min)s, %(both_rx_max)s, %(both_rx_avg)s, %(both_rx_min)s, %(datetime)s, %(link_id)s,
			%(status)s, %(error_details)s)
		'''.format(self.traffic_monitor_table_name)
		self.cnn.execute(query, values)

	def run(self):
		logger = utils.log_setup(self.app_name, self.enable_logging)
		self.engine, self.cnn, self.metadata = db.connect_to_postgres(logger, self.DB)

		self.task_id = db.insert_task_processing(logger, self.cnn, self.app_name, datetime.datetime.now(),
			str(self.server["IP"]), str(self.client["IP"]))

		self.create_traffic_monitor(logger)

		try :
			if(not utils.ip_is_up(self.server["IP"]) or not utils.ip_is_up(self.client["IP"])):
				raise Exception("IP down")

			api_conn = Api(self.server["IP"], logger, user=self.server["username"], 
				password=self.server["password"], use_ssl=False, port=8728
			)
			if(api_conn.successful == False):
				raise Exception("connection failed")

			both_res = api_conn.talk([
				"/tool/bandwidth-test",
				"=direction=both",
				"=address={}".format(self.client["IP"]),
				"=user={}".format(self.client["username"]),
				"=password={}".format(self.client["password"]),
				"=protocol=tcp",
				"=duration=10s",
				"=connection-count=20"
			])
			processed = utils.process_response(both_res)
			processed = processed[2:-2]

			both_tx = [int(el['tx_current']) for el in processed]
			both_rx = [int(el['rx_current']) for el in processed]

			both_tx_avg = sum(both_tx)/len(both_tx)
			both_tx_min = min(both_tx)
			both_tx_max = max(both_tx)

			both_rx_avg = sum(both_rx)/len(both_rx)
			both_rx_min = min(both_rx)
			both_rx_max = max(both_rx)


			send_res = api_conn.talk([
				"/tool/bandwidth-test",
				"=direction=transmit",
				"=address={}".format(self.client["IP"]),
				"=user={}".format(self.client["username"]),
				"=password={}".format(self.client["password"]),
				"=protocol=tcp",
				"=duration=10s",
				"=connection-count=20"
			])
			processed = utils.process_response(send_res)
			processed = processed[2:-2]

			send_tx = [int(el['tx_current']) for el in processed]

			send_tx_avg = sum(send_tx)/len(send_tx)
			send_tx_min = min(send_tx)
			send_tx_max = max(send_tx)


			receive_res = api_conn.talk([
				"/tool/bandwidth-test",
				"=direction=receive",
				"=address={}".format(self.client["IP"]),
				"=user={}".format(self.client["username"]),
				"=password={}".format(self.client["password"]),
				"=protocol=tcp",
				"=duration=10s",
				"=connection-count=20"
			])
			processed = utils.process_response(receive_res)
			processed = processed[2:-2]

			receive_rx = [int(el['rx_current']) for el in processed]

			receive_rx_avg = sum(receive_rx)/len(receive_rx)
			receive_rx_min = min(receive_rx)
			receive_rx_max = max(receive_rx)

			values = {
				"server_ip" : self.server["IP"],
				"client_ip" : self.client["IP"],
				"both_tx_max" : both_tx_max,
				"both_tx_avg" : both_tx_avg,
				"both_tx_min" : both_tx_min,
				"both_rx_max" : both_rx_max,
				"both_rx_avg" : both_rx_avg,
				"both_rx_min" : both_rx_min,
				"send_tx_max" : send_tx_max,
				"send_tx_avg" : send_tx_avg,
				"send_tx_min" : send_tx_min,
				"receive_rx_max" : receive_rx_max,
				"receive_rx_avg" : receive_rx_avg,
				"receive_rx_min" : receive_rx_min,
				"status" : "done",
				"error_details" : None
			}
			if(self.insert_to_db):
				self.insert(values)


		except Exception as e:
			values = {
				"server_ip" : self.server["IP"],
				"client_ip" : self.client["IP"],
				"both_tx_max" : None,
				"both_tx_avg" : None,
				"both_tx_min" : None,
				"both_rx_max" : None,
				"both_rx_avg" : None,
				"both_rx_min" : None,
				"send_tx_max" : None,
				"send_tx_avg" : None,
				"send_tx_min" : None,
				"receive_rx_max" : None,
				"receive_rx_avg" : None,
				"receive_rx_min" : None,
				"status" : "error",
				"error_details" : str(e)
			}
			if(self.insert_to_db):
				self.insert(values)
			else :
				raise Exception(str(e))


if __name__ == '__main__':
	RealTimeMonitor().run()