from ftplib import FTP
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
from time import sleep

class UpgradePackage :
	def __init__(self, username = "username", password = "password", 
				start_ip = "192.168.0.1", end_ip = "192.168.0.255"
			):
		self.username = username
		self.password = password
		self.task_id = None

		self.account_table_name = "accounts"

		self.DB = os.getenv('postgres_DB', None)
		self.app_name = "Upgrade Package"
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

		for ip_int in range(int(self.start_ip), int(self.end_ip)):
			
			self.ip = str(ipaddress.IPv4Address(ip_int))

			if(not utils.ip_is_up(self.ip)):
				continue
			ftp = FTP(host = self.ip, user = self.username, passwd = self.password, acct = 'root')
			ftp.connect()
			ftp.login(user = self.username, passwd = self.password)

			client = paramiko.SSHClient()
			client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
			client.connect(self.ip, port = 22, username = self.username, password = self.password)


			file = open('packages/routeros-mipsbe-6.43.16.npk','rb')
			ftp.storbinary('STOR routeros-mipsbe-6.43.16.npk', file)
			file.close()
			stdin, stdout, stderr = client.exec_command('/system reboot' + '\r\n' + 'y')

			while(True):
				sleep(20)
				try :
					client = paramiko.SSHClient()
					client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
					client.connect(self.ip, port = 22, username = self.username, password = self.password)
					stdin, stdout, stderr = client.exec_command('/system resource print')
					output = stdout.readlines()
					output=''.join(output)
					version = re.findall("version:.*\n", output)[0][9:-2]
					if(version =="6.43.16 (long-term)"):
						print("version confirmed {}".format(version))
						break
				except Exception as e:
					print("connection failed : {}".format(e))

			stdin, stdout, stderr = client.exec_command('/system routerboard upgrade' + '\r\n' + 'y')
			stdin, stdout, stderr = client.exec_command('/system reboot' + '\r\n' + 'y')

if __name__ == '__main__':
	UpgradePackage().run()