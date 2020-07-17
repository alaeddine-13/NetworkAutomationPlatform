import  sqlalchemy as db
import logging
import re
from utilities.db import connect_to_mysql, connect_to_postgres
import os
from queue import Queue


mysql_url = os.getenv('mysql_DB', None)
postgres_url = os.getenv('postgres_DB', None)
postgres_DB_users = os.getenv('postgres_DB_users', None)

def get_stations():
	station_antennas = {}
	stations_set = set()
	engine, cnn = connect_to_mysql(mysql_url)
	query = '''
		SELECT username FROM rm_users WHERE username LIKE %(val)s and enableuser=1
	'''
	res = cnn.execute(query, {"val" : 'ant.%'})
	antennas = res.fetchall()
	for antenna in antennas :
		z = re.match("ant\.([0-9]*[a-zA-Z]+)([0-9]+)", antenna[0])
		if(z):
			if(z.group(1) in station_antennas):
				station_antennas[z.group(1)].append(z.group(2))
			else :
				station_antennas[z.group(1)] = [z.group(2)]
			stations_set.add(z.group(1))
	stations_list = list(stations_set)
	print(len(stations_list))
	return station_antennas, stations_list

def get_antenna_ip(station_key, access_point):
	engine, cnn = connect_to_mysql(mysql_url)
	query = '''
		SELECT staticipcpe FROM rm_users WHERE username= %(username)s
	'''
	res = cnn.execute(query, {"username" : "ant.{0}{1}".format(station_key, access_point)})
	ip = res.fetchone()[0]
	return ip

def ssh_standardize_accounts(payload, logs_queue):

	from features.standardize_accounts.ssh_standardize_accounts import SSHStandardizeAccounts
	from threading import Thread
	from time import sleep
	from flask import jsonify
	try :
		SSHStandardizeAccounts_task = SSHStandardizeAccounts(**payload, logs_queue = logs_queue)
		thread = Thread(target = SSHStandardizeAccounts_task.run).start()
		while(SSHStandardizeAccounts_task.task_id == None):
			sleep(0.3)
		return {"result": True, "status": "started", "task_id" : SSHStandardizeAccounts_task.task_id}
	except Exception as e :
		print(str(e))
		return {"result":False, "status":"failed", "task_id":None}

def execute_commands(payload, logs_queue):

	from features.execute_commands.execute_commands import ExecuteCommands
	from threading import Thread
	from time import sleep
	from flask import jsonify
	try :
		ExecuteCommands_task = ExecuteCommands(**payload, logs_queue = logs_queue)
		thread = Thread(target = ExecuteCommands_task.run).start()
		while(ExecuteCommands_task.task_id == None):
			sleep(0.3)
		return {"result": True, "status": "started", "task_id" : ExecuteCommands_task.task_id}
	except Exception as e :
		print(str(e))
		return {"result":False, "status":"failed", "task_id":None}

def get_filtered_accounts(status='%', start_ip = "0.0.0.0", end_ip = "255.255.255.255",
		ip_pattern = "x.x.x.x", task_id = None):
	import ipaddress
	from utilities.utils import tuple_list_key_list_to_dict_list
	filtered_accounts = []
	engine, cnn, metadata = connect_to_postgres(logging, postgres_url)
	ip_pattern = ip_pattern.replace('.','\.')
	ip_pattern = re.sub('x+','x', ip_pattern)
	ip_pattern = ip_pattern.replace('x','[^\.]+?')
	query = '''
		SELECT * FROM accounts WHERE "status" LIKE %(status)s and "IP" ~ %(ip_pattern)s
	'''
	if(len(task_id)>0):
		query = '''
			SELECT * FROM accounts WHERE "status" LIKE %(status)s and "IP" ~ %(ip_pattern)s and "task_id" = %(task_id)s
		'''
	res = cnn.execute(query, {"status" : status, "ip_pattern" : ip_pattern, "task_id" : task_id})
	accounts = res.fetchall()
	for account in accounts :
		in_range = int(ipaddress.IPv4Address(start_ip))<=int(ipaddress.IPv4Address(account[2])) and int(ipaddress.IPv4Address(account[2]))<int(ipaddress.IPv4Address(end_ip))
		print(in_range)
		if(in_range):
			filtered_accounts.append(list(account))
	res = tuple_list_key_list_to_dict_list(filtered_accounts, 
		["username", "password", "IP", "status", "date", "version", "task_id", "mac"])
	return res


def getemails(userName, password):


	engine, cnn, metadata = connect_to_postgres(logging, postgres_DB_users)

	query = '''
		SELECT * FROM users WHERE "userName" = %(userName)s and "password" = %(password)s
	'''
	res = cnn.execute(query, {"userName" : userName, "password" : password})

	users = res.fetchall()
	print(users)
	if(len(users)>0):
		return True
	else :
		return False
	

def get_traffic_monitors_basic():
	from utilities.db import get_from_postgres_basic
	return get_from_postgres_basic("traffic_monitor", ["id", "server_ip", "client_ip", "send_tx_max", "send_tx_avg",
			"send_tx_min", "receive_rx_max","receive_rx_avg", "receive_rx_min", "both_tx_max", "both_tx_avg",
			"both_tx_min", "both_rx_max", "both_rx_avg", "both_rx_min", "datetime", "link_name"
		])

def get_traffic_monitors(traffic_monitor_table_name = "traffic_monitor", link_table_name = "link"):
	from utilities.utils import tuple_list_key_list_to_dict_list
	traffic_monitors = []
	engine, cnn, metadata = connect_to_postgres(logging, postgres_url)
	
	query = '''
		select public.{0}.*, public.{1}.server_ip, public.{1}.client_ip, public.{1}.link_name from public.{0}, public."{1}"
		where 
		"{1}".link_id = "{0}".link_id
		order by {0}."datetime" Desc
	'''.format(traffic_monitor_table_name, link_table_name)
	
	res = cnn.execute(query)
	results = res.fetchall()
	print(results)

	res = tuple_list_key_list_to_dict_list(results, ["id", "send_tx_max", "send_tx_avg",
			"send_tx_min", "receive_rx_max","receive_rx_avg", "receive_rx_min", "both_tx_max", "both_tx_avg",
			"both_tx_min", "both_rx_max", "both_rx_avg", "both_rx_min", "datetime", "link_id", "status",
			"error_details", "server_ip", "client_ip", "link_name"
		])
	return res

def get_links():
	from utilities.db import get_from_postgres_basic
	return get_from_postgres_basic("link", ["link_id", "server_ip", "client_ip", "link_name"])

def get_traffic_monitor_field(link_id, field_name, traffic_monitor_table_name = "traffic_monitor", link_table_name = "link"):
	from utilities.utils import tuple_list_key_list_to_dict_list
	traffic_monitors = []
	engine, cnn, metadata = connect_to_postgres(logging, postgres_url)
	
	query = '''
		select public.{0}.{2}, EXTRACT(EPOCH FROM public.{0}.datetime)::bigint, public.{1}.server_ip, public.{1}.client_ip,
		public.{1}.link_name from public.{0}, public."{1}"
		where 
		"{1}".link_id = "{0}".link_id
		and "{0}".link_id = %(link_id)s
		and "{0}".status = 'done'
		order by {0}."datetime" Desc
	'''.format(traffic_monitor_table_name, link_table_name, field_name)
	
	res = cnn.execute(query, {"link_id" : link_id})
	results = res.fetchall()
	print(results)

	res = tuple_list_key_list_to_dict_list(results, [field_name ,"datetime", "link_id", "server_ip",
			"client_ip", "link_name"
		])
	return res

def get_users():
	from utilities.db import get_from_postgres_basic
	return get_from_postgres_basic("users", ["user_id", "username", "password", "role"])

def get_cpe_registration_traffic(logs_queue, station_key, access_point, username):
	from features.execute_commands.execute_commands import ExecuteCommands
	from utilities import utils
	ip = get_antenna_ip(station_key, access_point)
	obj = ExecuteCommands(logs_queue = logs_queue)
	message_tag = "@{0}@{1}{2}\n".format(username, station_key, access_point)
	registration_table_response = obj.execute_api_command_onestep("/interface/wireless/registration-table/print", ip, log_tag = "#registration"+message_tag)
	traffic_response = obj.execute_api_command_onestep("/interface/monitor-traffic\r\n=interface=ether1\r\n=once", ip, log_tag = "#traffic"+message_tag, end_signal = "#get_cpe_info_completed"+message_tag)
