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
from routeros.api_dev import Api
import pandas as pd

class UpdateAccessListTables :
	def __init__(self, username = "username", password = "password", 
			start_ip = "192.168.0.1", end_ip = "192.168.0.255"
			):
		self.password = password
		self.username = username
		self.task_id = None

		self.access_list_table_name = "access_list"

		self.DB = os.getenv('postgres_DB', None)
		self.app_name = "Update Access List Tables"
		self.enable_logging = True

		self.cnn = None
		self.engine = None
		self.metadata = None

		self.start_ip = start_ip
		self.end_ip = end_ip

	def run(self):
		logger = utils.log_setup(self.app_name, self.enable_logging)
		self.engine, self.cnn, self.metadata =db.connect_to_postgres(logger, self.DB)

		self.start_ip = ipaddress.IPv4Address(self.start_ip)
		self.end_ip = ipaddress.IPv4Address(self.end_ip)

		self.task_id = db.insert_task_processing(logger, self.cnn, self.app_name, datetime.datetime.now(),
			str(self.start_ip), str(self.end_ip))

		access_lists_all = []

		for ip_int in range(int(self.start_ip), int(self.end_ip)):
			
			self.ip = str(ipaddress.IPv4Address(ip_int))

			if(not utils.ip_is_up(self.ip)):
				continue

			api_conn = Api(self.ip, logger, user=self.username, password=self.password, use_ssl=False, port=8728)
			if(api_conn.successful == False):
					continue

			access_lists = api_conn.talk(["/interface/wireless/access-list/print"])
			access_lists = utils.process_response(access_lists, 
				to_add_params = {"IP" : self.ip, "task_id" : self.task_id}
			) 

			access_lists_all = access_lists_all + access_lists

		access_lists_df = pd.DataFrame(access_lists_all)
		access_lists_df.to_sql("access_list", self.engine, if_exists='append', index=True)
		db.update_task_completed(logger, self.cnn, self.task_id)

if __name__ == '__main__':
	UpdateAccessListTables().run()