from functools import wraps
import logging
import os 
from utilities import db
from main import logs_queue
def log_errors(errors_table_name):
	def log_errors_(func):
		@wraps(func)
		def func_wrapper(*args, **kwargs):
			try:
				return func(*args, **kwargs)
			except Exception as e:
				import traceback
				DB = os.getenv('postgres_DB', None)
				engine, cnn, metadata =db.connect_to_postgres(logging, DB)
				db.create_errors_table(cnn)
				db.insert_error(cnn, str(e), traceback.format_exc(), errors_table_name = errors_table_name)
				logs_queue.put(('error', str(e)))
				return 0
		return func_wrapper
	return log_errors_