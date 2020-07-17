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
from utilities.decorators import log_errors

class SSHStandardizeAccounts :
	def __init__(self, ip_version = "ipv4", start_ip = '192.168.0.1', end_ip = '192.168.0.2', logger = None,
		logs_queue = None,
		existing_users = [{"username": "username", "passwords": ["password"]}],
		standard_account_username = "username",
		standard_account_password = "password",
		ftp_server_address = "192.168.0.3",
		ftp_server_name = "ftpname",
		ftp_server_pass = "ftppass"):
		self.users = existing_users
		self.accounts = utils.get_account_pairs(self.users)
		self.task_id = None
		self.ip = ""
		self.start_ip_str = start_ip
		self.end_ip_str = end_ip
		self.ip_version = ip_version

		self.standard_account = {
			"username" : standard_account_username,
			"password" : standard_account_password,
			"group" : "full"
		}


		self.ftp_server = {
			"address": ftp_server_address,
			"name" : ftp_server_name,
			"password" : ftp_server_pass,
			"port":"21"
		}

		self.account_table_name = "accounts"

		self.DB = os.getenv('postgres_DB', None)
		self.app_name = "SSH Standardize accounts"
		self.enable_logging = True

		self.ssh = None
		self.cnn = None
		self.engine = None
		self.metadata = None
		self.logs_queue = logs_queue

	def create_account_table(self, logger):
		query = '''
		CREATE TABLE IF NOT EXISTS public.{0}(
			"username" text,
			"password" text,
			"IP" text,
			"status" text,
			"date" TIMESTAMP,
			"version" text,
			PRIMARY KEY ("IP", "username")
		);
		'''.format(self.account_table_name)
		logger.info ("Creating {} table if not exist".format(self.account_table_name))
		try :
			self.cnn.execute(query)
		except Exception as e:
			logger.info('Something went wrong when creating table')
			logger.info('Error: {}'.format(e))
			raise Exception("unable to create account table. " +e)

	def is_standardized(self, ip):
		query = '''
			SELECT * FROM public.{0} where "IP" = %(ip)s and "username" = %(username)s
		'''.format(self.account_table_name)
		try :
			res = self.cnn.execute(query, {"ip" : ip, "username" : self.standard_account["username"]})
			return len(res.fetchall()) == 1
		except:
			return False


	def upsert(self, logger, account):
		query = '''
		INSERT INTO public.{0} (
			"username", "password", "IP", "status", "date", "version", "mac", "task_id"
		)
		VALUES (
			%(username)s, %(password)s, %(IP)s, %(status)s, %(date)s, %(version)s, %(mac)s, %(task_id)s
		)
		'''.format(self.account_table_name)
		try :
			self.cnn.execute(query, account)
		except Exception as e:
			try :
				query = '''
					UPDATE public.{0} SET "password" = %(password)s, "status" = %(status)s, "date" = %(date)s,
					"version" = %(version)s, "mac" = %(mac)s, "task_id" = %(task_id)s
					WHERE public.{0}."IP" = %(IP)s and public.{0}."username" = %(username)s 
				'''.format(self.account_table_name)
				self.cnn.execute(query, account)
			except Exception as e:
				logger.info("Error occured when updating row with id ({0}, {1}) in table {2}. {3}"
					.format(account['IP'], account['username'], self.account_table_name, e)
				)
				raise Exception("Error occured when updating row with id ({0}, {1}) in table {2}. {3}"
					.format(account['IP'], account['username'], self.account_table_name, e)
				)

	@log_errors("errors")
	def run(self, logger = None):
		if(not logger):
			logger = utils.log_setup(self.app_name, self.enable_logging, logs_queue = self.logs_queue)
		self.engine, self.cnn, self.metadata =db.connect_to_postgres(logger, self.DB)

		self.task_id = db.insert_task_processing(logger, self.cnn, self.app_name, datetime.datetime.now(),
			self.start_ip_str, self.end_ip_str)

		self.create_account_table(logger)

		up_ips = utils.get_up_ips(logger, self.start_ip_str, self.end_ip_str, num_worker_threads = 200, ip_version = self.ip_version)

		for up_ip in up_ips:
			self.ip = up_ip

			logger.info("Processing IP {}".format(self.ip))
			if(self.is_standardized(self.ip)):
				logger.info("IP {} is already standardized".format(self.ip))
				continue

			done = False
			for username, password in self.accounts:
				self.ssh, success = utils.ssh_connect(logger, self.ip, username, password)
				if(not success):
					continue
				#for standard_account in [self.standard_account, self.standard_account_kubi]:
				for standard_account in [self.standard_account]:
					self.upsert(logger, 
						{
							"username" : standard_account["username"],
							"password" : standard_account["password"],
							"IP" : self.ip,
							"status" : "Processing",
							"date" : datetime.datetime.now(),
							"version" : None,
							"mac" : None,
							"task_id" : self.task_id
						}
					)
				stdin, stdout, stderr = self.ssh.exec_command('/system identity print')
				output = stdout.read().decode("utf-8", 'ignore')
				device_name = output[8:-4]
				backup_filename = '{0}{1}.rsc'.format(device_name, datetime.datetime.now().strftime('%d_%m_%Y-%H_%M'))
				stdin, stdout, stderr = self.ssh.exec_command(
							'/export file={}'.format(backup_filename)
						)
				output = stdout.readlines()

				backup_taken = True
				logger.info("export backup results : {}".format(output))
				if(output != []):
					backup_taken = False
					logger.info("Error: couldn't generate backup file for device {0} {1}".format(device_name, self.ip))

				if(backup_taken):
					stdin, stdout, stderr = self.ssh.exec_command(
						'/tool fetch address={address} port={port} src-path={0} user={name} mode=ftp password={password} dst-path={0} upload=yes'
						.format(backup_filename, **self.ftp_server)
					)
					print(stdout.read().decode("utf-8", 'ignore'))

				stdin, stdout, stderr = self.ssh.exec_command('/system resource print')
				output = stdout.read().decode("utf-8", 'ignore')
				version = re.findall("version:.*\n", output)[0][9:-2]
				
				stdin, stdout, stderr = self.ssh.exec_command('/interface ethernet print')
				output = stdout.read().decode("utf-8", 'ignore')
				self.mac = None
				try:
					self.mac = re.findall("[0-9A-F]{2}:[0-9A-F]{2}:[0-9A-F]{2}:[0-9A-F]{2}:[0-9A-F]{2}:[0-9A-F]{2}", output)[0]
				except :
					logger.info("mac not found, skipping IP")
					break

				stdin, stdout, stderr = self.ssh.exec_command(
					'/user add name={username} password={password} group={group}'.format(**self.standard_account)
				)
				output = stdout.read().decode("utf-8", 'ignore')

				"""				stdin, stdout, stderr = self.ssh.exec_command(
					'/user add name={username} password={password} group={group}'.format(**self.standard_account_kubi)
				)
				output = stdout.readlines()"""

				stdin, stdout, stderr = self.ssh.exec_command('/user print')
				output = stdout.read().decode("utf-8", 'ignore')
				
				output = re.sub("\n ", "\n", output)
				output = re.sub(" +", " ", output)
				output = output.split('\n')[2:-2]
				users = [line.split(' ')[0:2] for line in output]

				logger.info("users before deletion for ip {0} : {1}".format(self.ip, output))

				for user in users:
					#if(user[1]!=self.standard_account["username"] and user[1]!="admin" 
					#	and user[1]!=self.standard_account_kubi["username"]):
					if(user[1]!=self.standard_account["username"] and user[1]!="admin" ):
						stdin, stdout, stderr = self.ssh.exec_command('/user remove {}'.format(user[1]))
						output = stdout.read().decode("utf-8", 'ignore')

				stdin, stdout, stderr = self.ssh.exec_command('/ip service set api,ssh,winbox disabled=no')
				output = stdout.read().decode("utf-8", 'ignore')

				stdin, stdout, stderr = self.ssh.exec_command('/ip service set api-ssl,ftp,telnet,www,www-ssl disabled=yes')
				output = stdout.read().decode("utf-8", 'ignore')

				stdin, stdout, stderr = self.ssh.exec_command("system ntp client set enabled=yes primary-ntp=95.0.60.220")
				output = stdout.read().decode("utf-8", 'ignore')

				#for standard_account in [self.standard_account, self.standard_account_kubi] :
				for standard_account in [self.standard_account] :
					status = "Done"
					if(not backup_taken):
						status = "Done without backup"
					self.upsert(logger,
						{
							"username" : standard_account["username"],
							"password" : standard_account["password"],
							"IP" : self.ip,
							"status" : status,
							"date" : datetime.datetime.now(),
							"version" : version,
							"mac" : self.mac,
							"task_id" : self.task_id
						}
					)
				done = True
				break
			if(not done):
				self.upsert(logger,
					{
						"username" : "to kubi",
						"password" : None,
						"IP" : self.ip,
						"status" : "to kubi",
						"date" : datetime.datetime.now(),
						"version" : None,
						"mac" : None,
						"task_id" : self.task_id
					}
				)

		db.update_task_completed(logger, self.cnn, self.task_id)
		self.logs_queue.put(('completed', str(self.task_id)))
		return self.task_id

if __name__ == '__main__':
	SSHStandardizeAccounts().run()