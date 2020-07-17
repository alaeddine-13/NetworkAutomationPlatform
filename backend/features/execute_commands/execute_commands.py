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
from utilities.decorators import log_errors
import json
from time import sleep

class ExecuteCommands :
	def __init__(self, ip_version = "ipv4", start_ip = '192.168.0.1', end_ip = '192.168.0.2',
			username = 'username', password = 'password', connection_type = 'api', commands = '', logs_queue = None
		):
		self.username = username
		self.password = password
		self.task_id = None
		self.ip = ""
		self.start_ip_str = start_ip
		self.end_ip_str = end_ip
		self.ip_version = ip_version
		self.connection_type = connection_type
		self.commands_list = commands.split('#')
		self.account_table_name = "accounts"


		self.DB = os.getenv('postgres_DB', None)
		self.app_name = "Execute Commands"
		self.enable_logging = True

		self.logs_queue = logs_queue
		self.api_conn = None
		self.ssh = None
		self.cnn = None
		self.engine = None
		self.metadata = None

	def execute_command(self, logger, command, IP):

		logger.info("Executing the following command on IP {} : \n{}".format(IP, command))
		res = None
		if(self.connection_type == 'ssh'):
				commands = command.split("\n")
				for command in commands :
					stdin, stdout, stderr = self.ssh.exec_command(command)
					res = stdout.read().decode("utf-8", 'ignore').split('\n')
					if(res):
						for line in res:
							logger.info(line)
		elif (self.connection_type == 'api'):
			res = self.api_conn.talk(command.split('\r\n'))
			if(res):
				for line in res:
					logger.info(line)
		return res

	def execute_api_command_onestep(self, command, IP, log_tag = '', end_signal=None):
		logger = utils.log_setup(self.app_name, self.enable_logging, logs_queue = self.logs_queue)
		self.engine, self.cnn, self.metadata =db.connect_to_postgres(logger, self.DB)
		response = {}
		if(not self.is_standardized(IP)):
			response["result"] = False
			response["message"] = "IP {} is not standardized, please standardize it first".format(IP)
			logger.info(log_tag + json.dumps(response))
		else :
			self.api_conn = api_dev.Api(IP, logger, user=self.username,
				password=self.password, use_ssl=False, port=8728
			)
			if(self.api_conn.successful == False):
				response["result"] = False
				response["message"] = "connection to device failed"
				logger.info(log_tag + json.dumps(response))
			else :
				res = self.execute_command(logger, command, IP)
				response_data = []
				for element in res:
					response_data.append({"flag" : element[0], "message" : element[1]})
				response["result"] = True
				response["data"] = response_data
				logger.info(log_tag + json.dumps(response))
		if(end_signal):
			logger.info(end_signal)
		return response


	def is_standardized(self, ip):
		query = '''
			SELECT * FROM public.{0} where "IP" = %(ip)s and "username" = %(username)s
		'''.format(self.account_table_name)
		try :
			res = self.cnn.execute(query, {"ip" : ip, "username" : self.username})
			return len(res.fetchall()) == 1
		except:
			return False

	@log_errors("errors")
	def run(self):
		logger = utils.log_setup(self.app_name, self.enable_logging, logs_queue = self.logs_queue)
		self.engine, self.cnn, self.metadata =db.connect_to_postgres(logger, self.DB)

		self.task_id = db.insert_task_processing(logger, self.cnn, self.app_name, datetime.datetime.now(),
			self.start_ip_str, self.end_ip_str)
		
		up_ips = utils.get_up_ips(logger, self.start_ip_str, self.end_ip_str, num_worker_threads = 200, ip_version = self.ip_version)

		for up_ip in up_ips:
			self.ip = up_ip
			if(not self.is_standardized(self.ip)):
				logger.info("IP {} is not standardized, please standardize it first".format(self.ip))
				continue

			if(self.connection_type == 'ssh') :
				self.ssh, success = utils.ssh_connect(logger, self.ip, self.username, self.password)
				if(not success):
					continue

			elif (self.connection_type == 'api') :
				self.api_conn = api_dev.Api(self.ip, logger, user=self.username,
					password=self.password, use_ssl=False, port=8728
				)
				if(self.api_conn.successful == False):
					continue
			for command in self.commands_list :
				self.execute_command(logger, command, self.ip)


		db.update_task_completed(logger, self.cnn, self.task_id)
		self.logs_queue.put(('completed', str(self.task_id)))
		return self.task_id

if __name__ == '__main__':
	connection_type = 'api'
	commands = open("commands_{}.txt".format(connection_type), "r").read()
	ExecuteCommands(connection_type = connection_type, commands = commands).run()