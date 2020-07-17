import paramiko
from routeros import api_dev
import re
import os
import sys
import  sqlalchemy as db
import logging
import logging.handlers
import datetime
import ipaddress
from utilities import utils, db

class AddToAccessList :
	def __init__(self, mac_address, comment, ip = "192.168.0.1", username = 'username', password = 'password'):
		self.username = username
		self.password = password
		self.task_id = None
		self.ip = ip
		self.mac_address = mac_address
		self.comment = comment

		self.DB = os.getenv('postgres_DB', None)
		self.app_name = "Add To Access List"
		self.enable_logging = True

		self.api_conn = None
		self.cnn = None
		self.engine = None
		self.metadata = None


	def run(self):
		logger = utils.log_setup(self.app_name, self.enable_logging)
		self.engine, self.cnn, self.metadata =db.connect_to_postgres(logger, self.DB)

		self.task_id = db.insert_task_processing(logger, self.cnn, self.app_name, datetime.datetime.now(),
			str(self.ip), str(self.ip))

		logger.info("Processing IP {}".format(self.ip))
		logger.info("Testing IP status . . .")
		if(not utils.ip_is_up(self.ip)):
			logger.info("IP {} is down".format(self.ip))
			db.update_task_completed(logger, self.cnn, self.task_id, status="IP Down")
			return

		self.api_conn = api_dev.Api(self.ip, logger, user=self.username,
			password=self.password, use_ssl=False, port=8728
		)
		if(self.api_conn.successful == False):
			db.update_task_completed(logger, self.cnn, self.task_id, status = "Connection Failed")
			return

		res = self.api_conn.talk([
			"/interface/wireless/access-list/add",
			"=mac-address={}".format(self.mac_address),
			"=comment={}".format(self.comment)
			])
		if(len(res)==1 and res[0][0]=="!done"):
			db.update_task_completed(logger, self.cnn, self.task_id)
		else :
			db.update_task_completed(logger, self.cnn, self.task_id, status = "Execution Failed")
		return self.task_id

if __name__ == '__main__':
	AddToAccessList("11:22:33:44:55:66", "test_comment").run()