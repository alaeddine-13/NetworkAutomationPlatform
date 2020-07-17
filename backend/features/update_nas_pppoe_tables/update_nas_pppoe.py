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

class UpdateNasPPPOE :
	def __init__(self, username = "username", password = "password", 
				start_ip = "192.168.0.1", end_ip = "192.168.0.255"
			):
		self.password = password
		self.username = username
		self.task_id = None

		self.nas_pppoe_table_name = "nas_pppoe"

		self.DB = os.getenv('postgres_DB', None)
		self.app_name = "Update Nas PPPOE Tables_dev"
		self.enable_logging = True

		self.cnn = None
		self.engine = None
		self.metadata = None

		self.start_ip = start_ip
		self.end_ip = end_ip

	def create_nas_pppoe_table(self, logger):
		query = '''
		CREATE TABLE IF NOT EXISTS public.{0}(
			"id" text,
			"name" text,
			"service" text,
			"caller_id" text,
			"address" text,
			"uptime" text,
			"encoding" text,
			"session_id" text,
			"limit_bytes_in" text,
			"limit_bytes_out" text,
			"radius" text,
			"NAS_IP" VARCHAR(15),
			"task_id" INTEGER,
			PRIMARY KEY ("NAS_IP", "name")
		);
		'''.format(self.nas_pppoe_table_name)
		logger.info ("Creating {} table if not exist".format(self.nas_pppoe_table_name))
		try :
			self.cnn.execute(query)
		except Exception as e:
			logger.info('Something went wrong when creating table')
			logger.info('Error: {}'.format(e))
			raise Exception("unable to create {} table. {}".format(self.nas_pppoe_table_name, e))

	def upsert(self, logger, nas_pppoe):
		query = '''
		INSERT INTO public.{0} (
			"id", "name", "service", "caller_id", "address", "uptime", "encoding", "session_id", "limit_bytes_in",
			"limit_bytes_out", "radius", "NAS_IP", "task_id"
		)
		VALUES (
			%(id)s, %(name)s, %(service)s, %(caller_id)s, %(address)s, %(uptime)s, %(encoding)s, %(session_id)s, %(limit_bytes_in)s, %(limit_bytes_out)s, %(radius)s, %(NAS_IP)s, %(task_id)s
		)
		'''.format(self.nas_pppoe_table_name)
		try :
			self.cnn.execute(query, nas_pppoe)
		except Exception as e:
			try :
				query = '''
					UPDATE public.{0} SET "id" = %(id)s, "service" = %(service)s,
					"caller_id" = %(caller_id)s, "address" = %(address)s, "uptime" = %(uptime)s,
					"encoding" = %(encoding)s, "session_id" = %(session_id)s, "limit_bytes_in" = %(limit_bytes_in)s,
					 "limit_bytes_out" = %(limit_bytes_out)s, "radius" = %(radius)s, "task_id" = %(task_id)s
					WHERE public.{0}."NAS_IP" = %(NAS_IP)s and public.{0}."name" = %(name)s 
				'''.format(self.nas_pppoe_table_name)
				self.cnn.execute(query, nas_pppoe)
			except Exception as e:
				logger.info("Error occured when updating row with id ({0}, {1}) in table {2}. {3}"
					.format(nas_pppoe['NAS_IP'], nas_pppoe['name'], self.nas_pppoe_table_name, e)
				)
				raise Exception("Error occured when updating row with id ({0}, {1}) in table {2}. {3}"
					.format(nas_pppoe['NAS_IP'], nas_pppoe['name'], self.nas_pppoe_table_name, e))

	def run(self):
		logger = utils.log_setup(self.app_name, self.enable_logging)
		self.engine, self.cnn, self.metadata =db.connect_to_postgres(logger, self.DB)
		self.create_nas_pppoe_table(logger)
		
		self.start_ip = ipaddress.IPv4Address(self.start_ip)
		self.end_ip = ipaddress.IPv4Address(self.end_ip)

		self.task_id = db.insert_task_processing(logger, self.cnn, self.app_name, datetime.datetime.now(),
			str(self.start_ip), str(self.end_ip))


		for ip_int in range(int(self.start_ip), int(self.end_ip)):
			
			self.ip = str(ipaddress.IPv4Address(ip_int))

			if(not utils.ip_is_up(self.ip)):
				continue

			api_conn = Api(self.ip, logger, user=self.username, password=self.password, use_ssl=False, port=8728)
			if(api_conn.successful == False):
					continue

			response = api_conn.talk(["/ppp/active/print"])
			pppoe_list =  utils.process_response(response,
				to_add_params = {"NAS_IP" : self.ip, "task_id" : self.task_id}
			)
			for pppoe in pppoe_list :
				self.upsert(logger, pppoe)

		
		db.update_task_completed(logger, self.cnn, self.task_id)

if __name__ == '__main__':
	UpdateNasPPPOE().run()