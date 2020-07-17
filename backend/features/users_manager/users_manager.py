import re
import os
import sys
import  sqlalchemy as db
import logging
import logging.handlers
import datetime
from utilities import utils, db

class UsersManager :
	def __init__(self):

		self.users_table_name = "users"

		self.DB = os.getenv('postgres_DB', None)
		self.app_name = "Users Manager"
		self.enable_logging = True

		self.logger = None
		self.cnn = None
		self.engine = None
		self.metadata = None

	def create_users_table(self, logger):
		create_type_query = '''
			DO $$
				BEGIN
					IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'role_type') THEN
						CREATE TYPE role_type AS
						enum ('admin', 'installer', 'approver');
					END IF;
				END$$;
		'''
		
		logger.info("Creating role_type if not exists")
		self.cnn.execute(create_type_query)

		query = '''
			CREATE TABLE IF NOT EXISTS public.{}(
				"user_id" SERIAL PRIMARY KEY,
				"username" TEXT UNIQUE,
				"password" TEXT,
				"role" role_type
			)
		'''.format(self.users_table_name)

		self.logger.info("Creating table {} if not exists".format(self.users_table_name))
		self.cnn.execute(query)

	def insert(self, user):
		query = '''
			insert into public.{} ("username", "password", "role")
			values (%(username)s, %(password)s, %(role)s)
		'''.format(self.users_table_name)
		self.cnn.execute(query, user)

	def delete(self, user_id):
		select_query = '''
			SELECT * FROM public.{0} where "user_id" = %(user_id)s
		'''.format(self.users_table_name)
		res = self.cnn.execute(select_query, {"user_id" : user_id})
		user = res.fetchone()
		print(user["role"])
		if(user["role"] == "admin"):
			count_query = '''
				SELECT count(*) from public.{0} where "role" = 'admin'
			'''.format(self.users_table_name)
			res = self.cnn.execute(count_query)
			number = res.fetchone()[0]
			if(number ==1):
				raise Exception("There is only 1 user left with admin role. Impossible to delete it")

		delete_query = '''
			DELETE FROM public.{0}
			WHERE "user_id" = %(user_id)s;
		'''.format(self.users_table_name)
		self.cnn.execute(delete_query, {"user_id" : user_id})

	def edit(self, user):
		query = '''
			UPDATE public.{0} SET "username" = %(username)s, "password" = %(password)s, "role" = %(role)s
			WHERE "user_id" = %(user_id)s;
		'''.format(self.users_table_name)
		self.cnn.execute(query, user)

	def init(self):
		self.logger = utils.log_setup(self.app_name, self.enable_logging)
		self.engine, self.cnn, self.metadata = db.connect_to_postgres(self.logger, self.DB)
		self.create_users_table(self.logger)
		return self





if __name__ == '__main__':
	UsersManager().init()