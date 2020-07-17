# SSH Standardize Accounts
## Overview
This script can be run on a range of IPs.
For each IP address, it executes PING test. If the IP is up, it tries a set of passwords and usernames and attempts to connect via SSH with username/password pairs. Once the connection is established, the script will store a backup file and send it to FTP server, create a standard account, delete all other accounts in the device except for account `admin` and the `standard account`. Then, it will configure IP services (`api`, `winbox` and `ssh` are the only services enabled). The script will also configure `NTP` on each device. Finally, it stores the changes in the database (see **Database Section** for more info)
## How it works
You can run this script from the web interface or by making a customized `POST`request.
* First make sure the main script `main.py` is running and listening to API calls :
    On linux :
    ```shell
    cd app
    export FLASK_APP=main.py
    python main.py
    ``` 
    On windows :
    ```shell
    cd app
    set FLASk_APP=main.py
    python main.py
    ```
* You can then start making API calls to the script in order to run tasks. Thus, you can call `ssh_standardize_accounts.py` script by making a call to the endpoint `127.0.0.1:5000/SSHStandardizeAccounts`. The easiest way, is to use the web interface by filling the form and clicking the submit button. Alternatively, you can use any tool/library to call the endpoint. 
For example (linux command) :
    ```shell
    curl --data "ip_version=<ip_version>&start_ip=<start_ip>&end_ip=<end_ip>" 127.0.0.1:5000/SSHStandardizeAccounts
    ```
    To learn more about the `POST` parameters used, check the **Parameters Section**
## Parameters
In order to run the script `ssh_standardize_accounts.py`, a `POST` request to `127.0.0.1:5000/SSHStandardizeAccounts` is needed. The parameters are `ip_version`, `start_ip` and `end_ip`.
* `ip_version` : defines the type of version to be used. Values can be `ipv4` and `ipv6`.
* `start_ip` : defines the first IP address in the IP range
* `end_ip` : defines the last IP address in the IP range. Please note that `end_ip` is excluded

For example for `ip_version` = ipv4, `start_ip` = 192.168.0.1 and `end_ip` = 192.168.0.4, the script will be execute on IPs : 192.168.0.1, 192.168.0.2 and 192.168.0.3
## Database
After the script is excuted, new records are inserted in the database. If you are using the web interface, it will automatically redirect you to a web page showing the results that took effect in the database, once the script is finished.
The script operates on 2 tables :
* `task` table : a `task` record is inserted identifying the script execution, with column `task_name` = `"SSH Standardize accounts"`
* `account` table : for each IP address, the script creates a standard account. An account is identified by an IP address and an account username. Thus, for each IP address, an account record is *upserted* (see definition here https://wikidiff.com/insert/upsert). You can retrieve all added accounts in the database by executing the following query :
    ```SQL
    SELECT * FROM accounts where task_id = '<task_id>'
    ```
    where <task_id> is the value of the lastest task record in the database.
