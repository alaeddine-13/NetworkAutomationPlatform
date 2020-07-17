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

class LinksEditor :
	def __init__(self):

		self.link_table_name = "link"
		self.traffic_monitor_table_name = "traffic_monitor"

		self.DB = os.getenv('postgres_DB', None)
		self.app_name = "Links Editor"
		self.enable_logging = True

		self.logger = None
		self.cnn = None
		self.engine = None
		self.metadata = None

	def create_link_table(self):
		query = '''
			CREATE TABLE IF NOT EXISTS public.{}(
				"link_id" SERIAL PRIMARY KEY,
				"server_ip" TEXT,
				"client_ip" TEXT,
				"link_name" TEXT UNIQUE,
				UNIQUE ("server_ip", "client_ip")
			)
		'''.format(self.link_table_name)
		self.logger.info("Creating table {} if not exists".format(self.link_table_name))
		self.cnn.execute(query)

	def insert(self, link):
		query = '''
			insert into public.{} ("server_ip", "client_ip", "link_name")
			values (%(server_ip)s, %(client_ip)s, %(link_name)s)
		'''.format(self.link_table_name)
		self.cnn.execute(query, link)

	def delete(self, link_id):
		query = '''
			DELETE FROM public.{0}
			WHERE "link_id" = %(link_id)s;
			DELETE FROM public.{1}
			WHERE "link_id" = %(link_id)s;
		'''.format(self.link_table_name, self.traffic_monitor_table_name)
		self.cnn.execute(query, {"link_id" : link_id})

	def init(self):
		self.logger = utils.log_setup(self.app_name, self.enable_logging)
		self.engine, self.cnn, self.metadata = db.connect_to_postgres(self.logger, self.DB)
		self.create_link_table()
		return self





if __name__ == '__main__':
	LinksEditor().run()