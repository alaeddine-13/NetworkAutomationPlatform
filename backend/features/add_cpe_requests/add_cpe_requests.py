import re
import os
import sys
import  sqlalchemy as db
import logging
import logging.handlers
import datetime
from utilities import utils, db

class AddCPERequests :
	def __init__(self, engine = None, cnn = None, default_add_cpe_request_table_name = "add_cpe_request"):
		self.postgres_DB = os.getenv('postgres_DB', None) 
		self.enable_logging = False

		self.logger = None
		self.app_name = "Add CPE Requests"
		self.add_cpe_request_table_name = os.getenv('ADD_CPE_REQUEST_TABLE_NAME', default_add_cpe_request_table_name)
		self.cnn = cnn
		self.engine = engine
		self.metadata = None

	def create_add_cpe_request_table(self):
		self.logger.info("creating table {} if not exists".format(self.add_cpe_request_table_name))
		query = '''
			CREATE TABLE IF NOT EXISTS public.{0}(
				"add_cpe_request_id" SERIAL PRIMARY KEY,
				"installer_id" integer,
				"mac" varchar(17),
				"comment" text,
				"status" varchar(20),
				"approver_id" integer,
				"requested_at" timestamp,
				"approved_at" timestamp,
				"station_key" varchar(20),
				"access_point" integer,
				"executed_task_id" integer
			);
		'''.format(self.add_cpe_request_table_name)
		try :
			self.cnn.execute(query)
		except Exception as e :
			self.logger.info("something went wrong trying to create table {0}. {1}".format(
				self.add_cpe_request_table_name, str(e)))
			raise Exception(e)
	def request_add_cpe_request(self, installer_id, mac, comment, station_key, access_point):
		query = '''
			INSERT INTO public.{} ("installer_id", "mac", "comment", "status", "requested_at",
			"station_key", "access_point") 
			VALUES (%(installer_id)s, %(mac)s, %(comment)s, %(status)s, %(requested_at)s,
			%(station_key)s, %(access_point)s)
			RETURNING "add_cpe_request_id";
		'''.format(self.add_cpe_request_table_name)
		res = self.cnn.execute(query, {
				"installer_id" : installer_id,
				"mac" : mac,
				"comment" : comment,
				"status" : "pending",
				"requested_at" : datetime.datetime.now(),
				"station_key" : station_key,
				"access_point" : access_point
			})
		self.logger.info("installer_id {} requested to add cpe with mac {} at {} {}.".format(
			installer_id, mac, station_key, access_point))
		return res.fetchall()[0][0]

	def approve_add_cpe_request(self, approver_id, add_cpe_request_id):
		from features.add_to_access_list.add_to_access_list import AddToAccessList
		from rest.api import get_antenna_ip
		add_cpe_request = self.get_add_cpe_request_by_add_cpe_request_id(add_cpe_request_id)
		station_ip = get_antenna_ip(add_cpe_request["station_key"], add_cpe_request["access_point"])
		task_id = AddToAccessList(add_cpe_request["mac"], add_cpe_request["comment"], ip = station_ip).run()
		query = '''
			UPDATE public.{0} SET "status" = %(status)s, "approved_at" = %(approved_at)s,
			"approver_id" = %(approver_id)s, "executed_task_id" = %(executed_task_id)s
			WHERE public.{0}."add_cpe_request_id" = %(add_cpe_request_id)s 
		'''.format(self.add_cpe_request_table_name)
		res = self.cnn.execute(query, {
				"status" : "approved",
				"approved_at" : datetime.datetime.now(),
				"approver_id" : approver_id,
				"add_cpe_request_id" : add_cpe_request_id,
				"executed_task_id" : task_id
			})
		self.logger.info("approver_id {} accepted add cpe request with id {}, task_id : {}".format(
			approver_id, add_cpe_request_id, task_id))
		return task_id

	def reject_add_cpe_request(self, approver_id, add_cpe_request_id):
		query = '''
			UPDATE public.{0} SET "status" = %(status)s, "approved_at" = %(approved_at)s,
			"approver_id" = %(approver_id)s, "executed_task_id" = %(executed_task_id)s
			WHERE public.{0}."add_cpe_request_id" = %(add_cpe_request_id)s 
		'''.format(self.add_cpe_request_table_name)
		res = self.cnn.execute(query, {
				"status" : "rejected",
				"approved_at" : None,
				"approver_id" : approver_id,
				"add_cpe_request_id" : add_cpe_request_id,
				"executed_task_id" : None
			})
		self.logger.info("approver_id {} rejected add cpe request with id {}".format(
			approver_id, add_cpe_request_id))

	def delete_add_cpe_request(self, add_cpe_request_id):
		delete_query = '''
			DELETE from public.{0} where "add_cpe_request_id" = %(add_cpe_request_id)s
		'''.format(self.add_cpe_request_table_name)
		self.cnn.execute(delete_query, {"add_cpe_request_id" : add_cpe_request_id})
		self.logger.info("add cpe request with id {} was deleted".format(add_cpe_request_id))

	def get_add_cpe_request(self):
		query = '''
			SELECT add_cpe_request.*, installer.username AS "installer_username", approver.username AS "approver_username"
			FROM public.{0}
			LEFT JOIN users installer ON installer.user_id = add_cpe_request.installer_id
			LEFT JOIN users approver ON approver.user_id = add_cpe_request.approver_id
		'''.format(self.add_cpe_request_table_name)
		res = self.cnn.execute(query)
		requests  = res.fetchall()
		return utils.tuple_list_key_list_to_dict_list(requests, res.keys())

	def get_add_cpe_request_by_installer_id(self, installer_id):
		query = '''
			SELECT add_cpe_request.*, installer.username AS "installer_username", approver.username AS "approver_username"
			FROM public.{0}
			LEFT JOIN users installer ON installer.user_id = add_cpe_request.installer_id
			LEFT JOIN users approver ON approver.user_id = add_cpe_request.approver_id
			WHERE "installer_id" = %(installer_id)s
		'''.format(self.add_cpe_request_table_name)
		res = self.cnn.execute(query, {"installer_id" : installer_id})
		requests  = res.fetchall()
		return utils.tuple_list_key_list_to_dict_list(requests, res.keys())

	def get_add_cpe_request_by_approver_id(self, approver_id):
		query = '''
			SELECT add_cpe_request.*, installer.username AS "installer_username", approver.username AS "approver_username"
			FROM public.{0}
			LEFT JOIN users installer ON installer.user_id = add_cpe_request.installer_id
			LEFT JOIN users approver ON approver.user_id = add_cpe_request.approver_id
			WHERE "approver_id" = %(approver_id)s
		'''.format(self.add_cpe_request_table_name)
		res = self.cnn.execute(query, {"approver_id" : approver_id})
		requests  = res.fetchall()
		return utils.tuple_list_key_list_to_dict_list(requests, res.keys())

	def get_add_cpe_request_by_add_cpe_request_id(self, add_cpe_request_id):
		query = '''
			SELECT add_cpe_request.*, installer.username AS "installer_username", approver.username AS "approver_username"
			FROM public.{0}
			LEFT JOIN users installer ON installer.user_id = add_cpe_request.installer_id
			LEFT JOIN users approver ON approver.user_id = add_cpe_request.approver_id
			WHERE "add_cpe_request_id" = %(add_cpe_request_id)s
		'''.format(self.add_cpe_request_table_name)
		res = self.cnn.execute(query, {"add_cpe_request_id" : add_cpe_request_id})
		return dict(res.fetchone())

	def init(self):
		self.logger = utils.log_setup(self.app_name, self.enable_logging)
		self.engine, self.cnn, self.metadata = db.connect_to_postgres(self.logger, self.postgres_DB)
		self.create_add_cpe_request_table()
		return self



if __name__ == '__main__':
	pass