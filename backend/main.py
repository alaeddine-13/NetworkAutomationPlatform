#!/usr/bin/env python
# coding: utf-8

import click
import logging
from datetime import datetime
from flask import Flask, request
from flask import jsonify
import json
import os
import pandas as pd
from sqlalchemy import create_engine
from auth.decorators import requires_auth
from flask_socketio import SocketIO
from queue import Queue
from flask_cors import CORS

app = Flask(__name__)

cors = CORS(app, resources={r"/*": {"origins": "*"}})

postgres_DB = os.getenv('postgres_DB', None) 
postgres_DB_users = os.getenv('postgres_DB_users', None)

PORT = os.getenv('PORT', 5000)
socketio = SocketIO(app, async_mode="threading")
thread = None

logs_queue = Queue()

def background_thread():
    count = 0
    while True:
        socketio.sleep(0.2)
        while(not logs_queue.empty()):
            message = logs_queue.get()
            print("emitting obj", message)
            socketio.emit(message[0], message[1])

socketio.start_background_task(background_thread)

@app.route("/Test", methods=['POST', 'GET'])
@requires_auth(["admin"])
def test():
    from utilities.utils import log_setup
    logger = log_setup("test route", False, logs_queue = socketio)
    logger.info("Test")
    return jsonify({"result" : True})

@app.route("/Login", methods=['POST'])
@requires_auth(["admin", "installer", "approver"])
def login(user_role, user_id):
    return jsonify({"result" : True, "role" : user_role, "user_id" : user_id})

@app.route("/SSHStandardizeAccounts", methods=['POST', 'GET'])
@requires_auth(["admin"])
def ssh_standardize_accounts_endpoint():
    from rest.api import ssh_standardize_accounts

    if request.method == 'POST':
        return jsonify(ssh_standardize_accounts(request.form, logs_queue))
    else :
        task_id = SSHStandardizeAccounts({}, None).run()
        return jsonify({"result": True, "status" : "completed", "task_id" : task_id})

@app.route("/ExecuteCommands", methods=['POST', 'GET'])
@requires_auth(["admin"])
def execute_commands_endpoint():
    from rest.api import execute_commands

    if request.method == 'POST':
        return jsonify(execute_commands(request.form, logs_queue))
    else :
        task_id = ExecuteCommands().run()
        return jsonify({"result": True, "status" : "completed", "task_id" : task_id})


@app.route("/GetStations", methods=['GET', 'POST'])
@requires_auth(["admin", "installer", "approver"])
def get_stations():
    from rest.api import get_stations as get
    try :
        station_antennas, stations_list = get()
        response = {"antennas" : station_antennas, "stations" : stations_list, "result" : True}
        return jsonify(response)
    except Exception as e:
        return jsonify({"result" : False, "error" : str(e)})

@app.route("/InsertUser", methods=['POST'])
def insert_user():
    import pandas as pd
    from utilities.db import connect_to_postgres
    try :
        engine, cnn, metadata = connect_to_postgres(logging, postgres_DB_users)
        data = dict(request.get_json(force=True))
        data_df = pd.DataFrame([data])
        data_df.to_sql("users", cnn, if_exists='append')
        response = {'payload' : data, 'result' : True}
        return jsonify(response)
    except Exception as e:
        return jsonify({"result" : False, "error" : str(e)})

@app.route("/User", methods=['POST'])
def user():
    try :
        url = "webservice.myfi.com.tr:5454/api/User"
        payload = dict(request.get_json(force=True))
        headers = {
            "Content-Type" : "application/json"
        }
        response = requests.request("POST", url, data=json.dumps(payload), headers=headers)
        return response.text
    except Exception as e:
        return jsonify({"result" : False, "error" : str(e)}) 



@app.route("/userlogin", methods=['POST'])
def userlogin():
    

    from utilities.db import connect_to_postgres
    from rest.api import getemails
    try :
        engine, cnn, metadata = connect_to_postgres(logging, postgres_DB_users)
        data = dict(request.form) #hedhi el data fha el hajt ela jet fil request
         # w hna idha el login shih yrjalo fil data bidha mta request chnmlo biha ehan hjtna bsh yrjalk el token w hdhi 5dma o5ra
        response = {'payload' : data, 'result' : True, "login" : getemails (data["userName"], data["password"])}
        return jsonify(response)
    except Exception as e:
        return jsonify({"result" : False, "error" : str(e)})








@app.route("/test_endpoint", methods=['POST'])
def test_endpoint():
    from utilities.db import connect_to_postgres
    from rest.api import get_filtered_accounts
    try :
        engine, cnn, metadata = connect_to_postgres(logging, postgres_DB_users)
        data = dict(request.form)
        
        response = {'payload' : data, 'result' : True}
        return jsonify(response)
    except Exception as e:
        return jsonify({"result" : False, "error" : str(e)})

@app.route("/AddCPE", methods=['POST'])
@requires_auth(["admin"])
def add_cpe():
    from features.add_to_access_list.add_to_access_list import AddToAccessList
    from rest.api import get_antenna_ip
    station_ip = get_antenna_ip(request.form["stations"], request.form["access_point"])
    task_id = AddToAccessList(request.form["mac"], request.form["comment"], ip = station_ip).run()
    return jsonify({"result":"done", "task_id" : task_id})

@app.route("/GetAccounts", methods=['POST'])
@requires_auth(["admin"])
def get_accounts():
    from rest.api import get_filtered_accounts
    try :
        print(request.form)
        filtered_accounts = get_filtered_accounts(**request.form)
        response = {
            "result" : True,
            "accounts" : filtered_accounts
        }
        return jsonify(response)
    except Exception as e:
        import traceback
        response = {
            "result" : False,
            "error" : str(e),
            "error_details" : traceback.format_exc()
        }
        return jsonify(response)

@app.route("/installer/RequestAddCPE", methods=["POST"])
@requires_auth(["admin", "installer"])
def installerRequestAddCPE():
    from features.add_cpe_requests.add_cpe_requests import AddCPERequests
    try:
        print(request.form)
        add_cpe_request_id = AddCPERequests().init().request_add_cpe_request(
            request.form["installer_id"], request.form["mac"], request.form["comment"],
            request.form["station_key"], request.form["access_point"])
        return jsonify({"result":"Requested", "add_cpe_request_id" : add_cpe_request_id})
    except Exception as e :
        return jsonify({"result" : "error", "details" : str(e)})

@app.route("/approver/ApproveAddCPERequest", methods=["POST"])
@requires_auth(["admin", "approver"])
def approverApproveRequestAddCPE():
    from features.add_cpe_requests.add_cpe_requests import AddCPERequests
    try:
        task_id = AddCPERequests().init().approve_add_cpe_request(
            request.form["approver_id"], request.form["add_cpe_request_id"])
        return jsonify({"result":"Executed", "task_id" : task_id})
    except Exception as e :
        return jsonify({"result" : "error", "details" : str(e)})

@app.route("/approver/RejectAddCPERequest", methods=["POST"])
@requires_auth(["admin", "approver"])
def approverRejectAddCPERequest():
    from features.add_cpe_requests.add_cpe_requests import AddCPERequests
    try:
        AddCPERequests().init().reject_add_cpe_request(
            request.form["approver_id"], request.form["add_cpe_request_id"])
        return jsonify({"result":"True"})
    except Exception as e :
        return jsonify({"result" : "error", "details" : str(e)})

@app.route("/approver/DeleteAddCPERequest", methods=["POST"])
@requires_auth(["admin", "approver"])
def approverDeleteAddCPERequest():
    from features.add_cpe_requests.add_cpe_requests import AddCPERequests
    try:
        AddCPERequests().init().delete_add_cpe_request(request.form["add_cpe_request_id"])
        return jsonify({"result":"True"})
    except Exception as e :
        return jsonify({"result" : "error", "details" : str(e)})

@app.route("/approver/GetAddCPERequest", methods=["GET"])
@requires_auth(["admin", "approver"])
def approverGetAddCPERequest():
    from features.add_cpe_requests.add_cpe_requests import AddCPERequests
    try:
        res = AddCPERequests().init().get_add_cpe_request()
        return jsonify({"result":"True", "data": res})
    except Exception as e :
        return jsonify({"result" : "error", "details" : str(e)})

@app.route("/approver/GetApproverAddCPERequest", methods=["GET"])
@requires_auth(["admin", "approver"])
def approverGetApproverAddCPERequest():
    from features.add_cpe_requests.add_cpe_requests import AddCPERequests
    try:
        res = AddCPERequests().init().get_add_cpe_request_by_approver_id(request.form["approver_id"])
        return jsonify({"result":"True", "data": res})
    except Exception as e :
        return jsonify({"result" : "error", "details" : str(e)})

@app.route("/installer/GetAddCPERequest", methods=["POST"])
@requires_auth(["admin", "installer"])
def installerGetAddCPERequest():
    from features.add_cpe_requests.add_cpe_requests import AddCPERequests
    try:
        res = AddCPERequests().init().get_add_cpe_request_by_installer_id(request.form["installer_id"])
        return jsonify({"result":"True", "data": res})
    except Exception as e :
        return jsonify({"result" : "error", "details" : str(e)})

@app.route("/GetTrafficMonitors", methods=["GET"])
@requires_auth(["admin"])
def getTrafficMonitors():
    from rest.api import get_traffic_monitors
    try:
        res = get_traffic_monitors()
        return jsonify({"result":"True", "data": res})
    except Exception as e :
        return jsonify({"result" : "error", "details" : str(e)})

@app.route("/GetTrafficMonitor/<link_id>/<field_name>", methods=["GET"])
@requires_auth(["admin"])
def getTrafficMonitorField(link_id, field_name):
    from rest.api import get_traffic_monitor_field
    try:
        values = get_traffic_monitor_field(link_id, field_name)
        res = []
        for value in values:
            res.append(value)
        return jsonify({"result":"True", "data": res})
    except Exception as e :
        return jsonify({"result" : "error", "details" : str(e)})

@app.route("/AddLink", methods=["POST"])
@requires_auth(["admin"])
def addLink():
    from features.real_time_traffic_monitoring.links_editor import LinksEditor
    from features.real_time_traffic_monitoring.real_time_device_traffic import RealTimeMonitor
    try:
        link_name = request.form["link_name"]
        server_ip = request.form["server_ip"]
        client_ip = request.form["client_ip"]

        try :
            RealTimeMonitor(client_ip = client_ip, server_ip = server_ip, link_name= link_name + "_test",
            insert_to_db = False).run()
        except Exception as e:
            return jsonify({"result" : False,
                "error" : "traffic test failed, make sure API service is enabled and devices are standardized",
                "details" : str(e)}
                )

        LinksEditor().init().insert({"server_ip":server_ip, "client_ip" : client_ip, "link_name" : link_name})
        return jsonify({"result":True})

    except Exception as e :
        return jsonify({"result" : False, "error" : "database insertion failed, make sure this link doesn't already exist", "details" : str(e)})

@app.route("/DeleteLink", methods=["POST"])
@requires_auth(["admin"])
def deleteLink():
    from features.real_time_traffic_monitoring.links_editor import LinksEditor
    try:
        link_id = request.form["link_id"]
        LinksEditor().init().delete(link_id)
        return jsonify({"result":True})
    except Exception as e :
        return jsonify({"result" : False, "details" : str(e)})

@app.route("/GetLinks", methods=["GET"])
@requires_auth(["admin"])
def getLinks():
    from rest.api import get_links
    try:
        links = get_links()
        return jsonify({"result" : True, "data" : links})
    except Exception as e:
        return jsonify({"result" : False, "details" : str(e)})

@app.route("/AddUser", methods=["POST"])
@requires_auth(["admin"])
def addUser():
    from features.users_manager.users_manager import UsersManager
    try:
        username = request.form["username"]
        password = request.form["password"]
        role = request.form["role"]
        UsersManager().init().insert({"username" : username, "password" : password, "role" : role})
        return jsonify({"result":True})
    except Exception as e :
        return jsonify({"result" : False, "details" : str(e)})

@app.route("/DeleteUser", methods=["POST"])
@requires_auth(["admin"])
def deleteUser():
    from features.users_manager.users_manager import UsersManager
    try:
        user_id = request.form["user_id"]
        UsersManager().init().delete(user_id)
        return jsonify({"result":True})
    except Exception as e :
        return jsonify({"result" : False, "details" : str(e)})

@app.route("/EditUser", methods=["POST"])
@requires_auth(["admin"])
def editUser():
    from features.users_manager.users_manager import UsersManager
    try:
        user_id = request.form["user_id"]
        username = request.form["username"]
        password = request.form["password"]
        role = request.form["role"]
        UsersManager().init().edit({"user_id" : user_id, "username" : username, "password" : password, "role" : role})
        return jsonify({"result":True})
    except Exception as e :
        return jsonify({"result" : False, "details" : str(e)})

@app.route("/GetUsers", methods=["GET"])
@requires_auth(["admin"])
def getUsers():
    from rest.api import get_users
    try:
        users = get_users()
        return jsonify({"result" : True, "data" : users})
    except Exception as e:
        return jsonify({"result" : False, "details" : str(e)})

@app.cli.command()
def update_nas_pppoe_job():
    from features.update_nas_pppoe_tables.update_nas_pppoe import UpdateNasPPPOE
    UpdateNasPPPOE().run()

@app.cli.command()
def monitor_traffic():
    from features.real_time_traffic_monitoring.real_time_device_traffic import RealTimeMonitor
    from rest.api import get_links
    links = get_links()
    for link in links :
        RealTimeMonitor(client_ip = link["client_ip"], server_ip = link["server_ip"],
            link_name = link["link_name"], link_id = link["link_id"]).run()

"""    ##RealTimeMonitor(client_ip = '172.16.24.137', server_ip = '172.16.24.138', link_name= 'essen-skss').run()
    RealTimeMonitor(client_ip = '172.16.24.105', server_ip = '172.16.24.106', link_name= 'essen-sabiha1').run()
    ##RealTimeMonitor(client_ip = '172.16.24.113', server_ip = '172.16.24.114', link_name= 'essen-sabiha2').run()
    RealTimeMonitor(client_ip = '172.16.23.105', server_ip = '172.16.23.106', link_name= 'essen-kirantepe').run()
    RealTimeMonitor(client_ip = '172.16.24.41', server_ip = '172.16.24.42', link_name= 'essen-bayraktepe').run()

    RealTimeMonitor(client_ip = '172.16.23.81', server_ip = '172.16.23.82', link_name= 'merkez-mavidurak').run()
    RealTimeMonitor(client_ip = '172.16.24.1', server_ip = '172.16.24.2', link_name= 'merkez-kirantepe').run()
    RealTimeMonitor(client_ip = '172.16.23.73', server_ip = '172.16.23.74', link_name= 'merkez-adatepe').run()
    RealTimeMonitor(client_ip = '172.16.23.9', server_ip = '172.16.23.10', link_name= 'merkez-hilmikayin').run()
    RealTimeMonitor(client_ip = '172.16.23.1', server_ip = '172.16.23.2', link_name= 'merkez-sabiha').run()
    RealTimeMonitor(client_ip = '172.16.23.17', server_ip = '172.16.23.18', link_name= 'merkez-muhtar').run()
    RealTimeMonitor(client_ip = '172.16.23.25', server_ip = '172.16.23.26', link_name= 'merkez-caybasi').run()
    RealTimeMonitor(client_ip = '172.16.23.41', server_ip = '172.16.23.42', link_name= 'merkez-serdivan').run()
    RealTimeMonitor(client_ip = '172.16.23.49', server_ip = '172.16.23.50', link_name= 'merkez-unfabrikasi').run()
    RealTimeMonitor(client_ip = '172.16.23.57', server_ip = '172.16.23.58', link_name= 'merkez-yildiztepe').run()
    RealTimeMonitor(client_ip = '172.16.23.33', server_ip = '172.16.23.34', link_name= 'merkez-adatepe').run()
    RealTimeMonitor(client_ip = '172.16.23.129', server_ip = '172.16.23.130', link_name= 'peksenler-sapanca').run()
    RealTimeMonitor(client_ip = '172.16.23.97', server_ip = '172.16.23.98', link_name= 'peksenler-caybasi').run()
    RealTimeMonitor(client_ip = '172.16.23.169', server_ip = '172.16.23.170', link_name= 'peksenler-arifiye2').run()
"""

@socketio.on('message')
def print_message(message):
    print(message)
    socketio.emit('message', message)

@socketio.on('stop')
def stop_cmd(task_id):
    print("received stop command to stop task {}".format(task_id))

@socketio.on('get_cpe_info')
def get_cpe_info(message):
    from rest.api import get_cpe_registration_traffic
    message = message.split("#")
    station_key = message[0]
    access_point = message[1]
    username = message[2]
    get_cpe_registration_traffic(logs_queue, station_key, access_point, username)

@app.route('/message')
def ping():
    socketio.emit('message', {'data': 42})
    return {"result" : True}


if __name__ == '__main__':
    socketio.run(app, host="0.0.0.0", port=PORT, debug = True)

