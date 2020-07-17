from flask import Flask, request
from functools import wraps
from flask import abort
from rest.api import get_users
import inspect

def requires_auth(roles):
	def requires_auth_(func):
		@wraps(func)
		def func_wrapper(*args, **kwargs):
			if (not 'Authorization' in request.headers):
				abort(401)
			users = get_users()
			logged_user = None
			for user in users :
				if(user["username"] == request.authorization["username"] and user["password"] == request.authorization["password"]):
					logged_user = user
			if(not logged_user):
				abort(401)
			if(not logged_user["role"] in roles):
				abort(401)
			if ("user_role" in inspect.getargspec(func).args and "user_id" in inspect.getargspec(func).args):
				return func(logged_user["role"], logged_user["user_id"], *args, **kwargs)
			else :
				return func(*args, **kwargs)
		return func_wrapper
	return requires_auth_

