import paramiko
import re
import os
import sys
import  sqlalchemy as db
import logging
import logging.handlers
import datetime
import ipaddress
from flask_socketio import SocketIO
from queue import Queue
from threading import Thread

def ip_is_up(ip):
	response = os.system("ping -c 1 {}".format(ip))
	if(response == 0):
		return True
	else :
		return False

def ask_to_leave():
	answer = input("Do you want to continue? (y/n)\n").strip().lower()
	if(answer=='n'):
		sys.exit(0)

def log_setup(app_name, enable_logging, logs_queue = None):
	"""
	Sets up a logger object with configured with a stream handler and a file handler
	OUTPUT :
		returns a logger object
	"""
	logger = logging.getLogger(app_name)
	logger.setLevel(logging.DEBUG)

	formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

	if(len(logger.handlers) == 0):
		ch = logging.StreamHandler()
		ch.setLevel(logging.DEBUG)
		ch.setFormatter(formatter)
		logger.addHandler(ch)
		if(logs_queue != None):
			class SocketIOHandler(logging.Handler):
				def emit(self, record):
					logs_queue.put(('message', record.getMessage()))

			sio = SocketIOHandler()
			sio.setLevel(logging.DEBUG)
			sio.setFormatter(formatter)
			logger.addHandler(sio)

		if(enable_logging) :
			file_handler = logging.FileHandler(
				datetime.datetime.now().strftime('logs/{}%d_%m_%Y %H_%M.log'.format(app_name)),
				mode='w'
				)
			file_handler.setLevel(logging.DEBUG)
			file_handler.setFormatter(formatter)
			logger.addHandler(file_handler)

	logger.setLevel(logging.INFO)

	return logger

def process_response(response, to_add_params = {}) :
	res = []
	for record in response :
		if(record[0] =="!re"):
			dictionnary = record[1]
			dictionnary = dict((key.replace("=", "").replace("-","_").replace(".",""), value) for (key, value) in dictionnary.items())
			for key, value in zip(to_add_params.keys(), to_add_params.values()):
				dictionnary[key] = value
			res.append(dictionnary)
	return res

def ssh_connect(logger, ip, username, password):
	#attempts to connect with username and password, otherwise connects with standard account
	logger.info("Connecting to device via SSH using credentials {0} {1} . . .".format(username, password))
	ssh = paramiko.SSHClient()
	ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
	try:
		result = ssh.connect(ip, port = 22, username = username, password = password, timeout = 6)
	except:
		logger.error("Connection failed to {0} with credentials {1} {2}".format(ip, username, password))
		return None, False

	stdin, stdout, stderr = ssh.exec_command('/system resource print')
	output = stdout.readlines()
	output=''.join(output)
	version = re.findall("version:.*\n", output)[0][9:-2]
	print("version", version)
	return ssh ,True

def get_account_pairs(users):
	res = []
	for user in users :
		for password in user["passwords"]:
			res.append((user["username"], password))
	return res

def tuple_list_key_list_to_dict_list(tuple_list, key_list):
	res = []
	for _tuple in tuple_list :
		dictionnary = {}
		for i in range(0, len(_tuple)):
			dictionnary [key_list[i]] = _tuple[i]
		res.append(dictionnary)
	return res

def queue_to_list(q):
	res = []
	while q.qsize() > 0:
		res.append(q.get())
	return res

def batch_ip_scanner_multi_threaded(start_ip_str, end_ip_str, num_worker_threads = 200, ip_version = 'ipv4'):
	from timeutils import Stopwatch
	sw = Stopwatch(start = True)
	IPAddress = ipaddress.IPv4Address
	if(ip_version == "ipv6"):
		IPAddress = ipaddress.IPv6Address
	def scan(ip_address):
		if(ip_is_up(ip_address)):
			res_queue.put((ip_address, "up"))
		else:
			res_queue.put((ip_address, "down"))

	def worker():
		while True:
			item = task_queue.get()
			scan(item)
			task_queue.task_done()
	task_queue = Queue()
	res_queue = Queue()
	for i in range(num_worker_threads):
		t = Thread(target=worker)
		t.daemon = True
		t.start()

	start_ip = IPAddress(start_ip_str)
	end_ip = IPAddress(end_ip_str)
	for ip_int in range(int(start_ip), int(end_ip)):
		ip_str = str(IPAddress(ip_int))
		task_queue.put(ip_str)
	
	task_queue.join()
	print("time taken : {} seconds".format(sw.elapsed_seconds))
	return queue_to_list(res_queue)

def batch_ip_scanner_single_threaded(start_ip_str, end_ip_str, num_worker_threads = 100, ip_version = 'ipv4'):
	from timeutils import Stopwatch
	sw = Stopwatch(start = True)
	IPAddress = ipaddress.IPv4Address
	if(ip_version == "ipv6"):
		IPAddress = ipaddress.IPv6Address
	def scan(ip_address):
		if(ip_is_up(ip_address)):
			res_queue.put((ip_address, "up"))
		else:
			res_queue.put((ip_address, "down"))

	res_queue = Queue()

	start_ip = IPAddress(start_ip_str)
	end_ip = IPAddress(end_ip_str)
	for ip_int in range(int(start_ip), int(end_ip)):
		ip_str = str(IPAddress(ip_int))
		scan(ip_str)
	
	print("time taken : {} seconds".format(sw.elapsed_seconds))
	return queue_to_list(res_queue)

def filter_up_ips(ip_status_list, ip_version = 'ipv4'):
	IPAddress = ipaddress.IPv4Address
	if(ip_version == "ipv6"):
		IPAddress = ipaddress.IPv6Address

	res = []
	for ip_status in ip_status_list:
		if(ip_status[1]=='up'):
			res.append(ip_status[0])

	return sorted(res, key = lambda ip_str: int(IPAddress(ip_str)))

def get_up_ips(logger, start_ip_str, end_ip_str, num_worker_threads = 200, ip_version = 'ipv4'):
	logger.info("Scanning ip range")
	up_ips = filter_up_ips(
		batch_ip_scanner_multi_threaded(start_ip_str, end_ip_str, num_worker_threads = num_worker_threads,
			ip_version = ip_version), ip_version)
	logger.info("UP IPs : {}".format(", ".join(up_ips)))
	return up_ips