import re
import os
import sys
import  sqlalchemy as db
import logging
import logging.handlers
import datetime
from utilities.utils import ask_to_leave
import logging
import datetime

task_table_name = "task"
postgres_url = os.getenv('postgres_DB', None)

def connect_to_postgres(logger, DB):
	logger.info('Connecting to the Postgres database . . .')
	try :
		engine = db.create_engine(DB, use_batch_mode=True)
		cnn = engine.connect()
		metadata = db.MetaData()
		return engine, cnn, metadata
	except Exception as e :
		logger.info('Something went wrong when connecting to database')
		logger.info('Error: {}'.format(e))
		ask_to_leave()
		return None

def connect_to_mysql(DB, logger = logging) :
	logger.info('Connecting to MySQL database . . .')
	try :
		engine = db.create_engine(DB)
		cnn = engine.connect()
		return engine, cnn
	except Exception as e :
		logger.info('Something went wrong when connecting to database')
		logger.info('Error: {}'.format(e))
		raise e
		return None

def create_task_table(logger, cnn):
	query = '''
	CREATE TABLE IF NOT EXISTS public.{0}(
		"task_id" SERIAL PRIMARY KEY,
		"task_name" text,
		"run_time" timestamp,
		"status" text,
		"ip_range" text
	);
	'''.format(task_table_name)
	logger.info ("Creating {} table if not exist".format(task_table_name))
	try :
		cnn.execute(query)
	except Exception as e:
		logger.info('Something went wrong when creating table'.format(task_table_name))
		logger.info('Error: {}'.format(e))
		ask_to_leave()

def insert_task_processing(logger, cnn, task_name, run_time, start_ip, end_ip, use_range=True):
	create_task_table(logger, cnn)
	task = {
		"task_name" : task_name,
		"run_time" : run_time,
		"status" : "Processing",
		"ip_range" : "{0} -> {1}".format(start_ip, end_ip)
	}
	if (not use_range):
		task = {
		"task_name" : task_name,
		"run_time" : run_time,
		"status" : "Processing",
		"ip_range" : start_ip
	}
	query  = '''
		INSERT INTO public.{} ("task_name", "run_time", "status", "ip_range") 
		VALUES (%(task_name)s, %(run_time)s, %(status)s, %(ip_range)s)
		RETURNING "task_id";
	'''.format(task_table_name)
	logger.info("Adding task to database . . .")
	try :
		res = cnn.execute(query, task)
		return res.fetchall()[0][0]

	except Exception as e:
		logger.error ("Something went wrong trying to update values in table {0}. {1}".format(task_table_name, e))
		sys.exit(0)

def update_task_completed(logger, cnn, task_id, status="Completed"):
	logger.info("Updating task to Completed in database . . .")
	try :
		query = '''
			UPDATE public.{0} SET "status" = %(status)s
			WHERE public.{0}."task_id" = %(task_id)s 
		'''.format(task_table_name)
		cnn.execute(query, {"task_id" : task_id, "status" : status})
	except Exception as e:
		logger.info("Error occured when updating row with id {0} in table {1}. {2}"
			.format(task_id, task_table_name, e)
		)

def create_errors_table(cnn, errors_table_name = "errors"):
	query = '''
		CREATE TABLE IF NOT EXISTS public.{0} (
			"error_id" SERIAL PRIMARY KEY,
			"datetime" timestamp,
			"error_msg" text,
			"traceback" text
		)
	'''.format(errors_table_name)
	try :
		cnn.execute(query)
	except Exception as e:
		print('Something went wrong when creating table {}'.format(errors_table_name))
		print('Error: {}'.format(e))

def insert_error(cnn, error_msg, traceback, errors_table_name = "errors"):
	query  = '''
		INSERT INTO public.{} ("datetime", "error_msg", "traceback") 
		VALUES (%(datetime)s, %(error_msg)s, %(traceback)s)
		RETURNING "error_id";
	'''.format(errors_table_name)
	try :
		cnn.execute(query, {"error_msg" : error_msg, "traceback" : traceback, "datetime" : datetime.datetime.now()})
	except Exception as e:
		print('Something went wrong when inserting to table'.format(errors_table_name))
		print('Error: {}'.format(e))

def get_from_postgres_basic(table_name, fields_list):
	from utilities.utils import tuple_list_key_list_to_dict_list
	traffic_monitors = []
	engine, cnn, metadata = connect_to_postgres(logging, postgres_url)
	
	query = '''
		SELECT * FROM {}
	'''.format(table_name)
	
	res = cnn.execute(query)
	results = res.fetchall()
	print(results)

	res = tuple_list_key_list_to_dict_list(results, fields_list)
	return res

