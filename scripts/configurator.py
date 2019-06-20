#!/usr/bin/python

#
# This script is used for configuring Zabbix server by using API
#

import argparse, json, logging, MySQLdb, os, pycurl, re, socket, time
from pyzabbix import ZabbixAPI, ZabbixAPIException
from StringIO import StringIO
from jinja2 import Template

parser = argparse.ArgumentParser(prog="./configurator.py", description="Zabbix configurator")
parser.add_argument("--debug", action="store_true", help="Enable debug mode")
args = parser.parse_args()
options = vars(args)

logging.basicConfig()
logger = logging.getLogger("Configurator")
logger.setLevel("DEBUG" if options["debug"] else "INFO")

def check_email(email_address):
    if re.match(r"(^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$)", email_address):
        return 1
    else:
        error("Email address %s is incorrect."%email_address)

def error(msg=""):
    logger.error(msg)
    exit(1)

class Configurator:
    def __init__(self):
        self.grafana_password = os.environ["GF_SECURITY_ADMIN_PASSWORD"]
        self.grafana_datas_yaml = os.environ["GRA_DSOURCE_YAML"]
        self.grafana_dashb_yaml = os.environ["GRA_DBOARD_YAML"]
        self.grafana_hostname = os.environ["GRA_HOST"]
        self.grafana_pt_dashboards = os.environ["GRA_PATH_TO_DASHBOARDS"]
        self.url = os.environ["ZBX_SERVER_URL"]
        self.server_host = os.environ["ZBX_SERVER_HOST"]
        self.default_admin_username = "admin"
        self.default_admin_password = "zabbix"
        self.admin_password = os.environ["ZBX_ADMIN_PASSWORD"] if "ZBX_ADMIN_PASSWORD" in os.environ else self.default_admin_password
        self.guest_username = "guest"
        self.disable_guest = bool(os.environ["ZBX_DISABLE_GUEST"].lower() == "true" ) if "ZBX_DISABLE_GUEST" in os.environ else false
        self.uid = ""
        self.hostname = "Zabbix server"
        self.agent_dns_name = os.environ["ZBX_AGENT_HOSTNAME"]
        self.agent_ip_address = socket.gethostbyname(self.agent_dns_name)
        self.default_agent_port = 10050
        self.default_server_port = 10051
        # If server is unreachable than try to reconnect self.attempts_max_count times after wait timeout
        self.connect_attempt_wait_timeout = 5
        self.connect_attempts_max_count = 30
        # SMTP settings
        self.smtp_server = os.environ["SMTP_SERVER"]
        self.smtp_email = os.environ["SMTP_EMAIL"]
        if check_email(self.smtp_email):
            self.smtp_helo = os.environ["SMTP_EMAIL"].split("@")[1]
            logger.debug("SMTP_HELO value is: %s."%(self.smtp_helo))
        self.admin_email_address = os.environ["ADMIN_EMAIL_ADDRESS"]
        self.default_notify_period = "1-7,00:00-24:00"
        self.default_severity = int("111100",2)
        self.default_admin_group = "Zabbix administrators"
        self.default_user_group = "Operation managers"
        self.default_report_action = "Report problems to "+self.default_admin_group
        self.configuration_folder = os.environ["CONFIGURATION_FOLDER"] if "CONFIGURATION_FOLDER" in os.environ else ""
        self.zabbix_config_folder = os.environ["ZBX_CONFIG_FOLDER"] if "ZBX_CONFIG_FOLDER" in os.environ else "/etc/zabbix"
        # This custom config for zabbix agent will be used for auto discovery purposes, for automatic cleaning data, if it is required
        # Custom config structure: examples/custom.json.example
        self.zabbix_custom_config = self.zabbix_config_folder + "/" + os.environ["ZBX_CUSTOM_CONFIG"] if "ZBX_CUSTOM_CONFIG" in os.environ else "custom.json"
        self.custom_config_json = dict()
        # Auto registration
        self.host_metadata = "Linux "+os.environ["DEFAULT_HOST_SECRET"] if "DEFAULT_HOST_SECRET" in os.environ and os.environ["DEFAULT_HOST_SECRET"].strip() != "" else ""
        # Web scenario list
        self.url_list = json.loads(os.environ["URL_LIST"]) if "URL_LIST" in os.environ and os.environ["URL_LIST"].strip() != "" else []
        #
        self.zapi = ZabbixAPI(self.url)
        logger.info("Waiting while Zabbix server will be reachable.")
        for attempt in range(0,self.connect_attempts_max_count):
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            result = sock.connect_ex((self.server_host,self.default_server_port))
            if result == 0:
                logger.debug("Server is reachable.")
                break
            else:
                logger.debug("Waiting for while Zabbix will be reachable %d/%d with %d sec interval."%(attempt+1, self.connect_attempts_max_count, self.connect_attempt_wait_timeout))
                time.sleep(self.connect_attempt_wait_timeout)
        logger.info("Connecting to Zabbix database.")
        try:
            self.db = MySQLdb.connect(
                host = os.environ["DB_SERVER_HOST"],
                user = os.environ["MYSQL_USER"],
                passwd = os.environ["MYSQL_PASSWORD"],
                db = os.environ["MYSQL_DATABASE"]
            )
        except:
            error("Could not connect to Zabbix database")
        self.default_authentication_type = 0
        self.authentication_type = self.get_configuration()["authentication_type"]
        self.configuration = json.loads(os.environ["ZBX_CONFIG"]) if "ZBX_CONFIG" in os.environ and os.environ["ZBX_CONFIG"].strip() != "" else []
        self.admin_users = json.loads(os.environ["ZBX_ADMIN_USERS"]) if "ZBX_ADMIN_USERS" in os.environ and os.environ["ZBX_ADMIN_USERS"].strip() != "" else []
        self.additional_templates = [x.strip() for x in os.environ["ZBX_ADDITIONAL_TEMPLATES"].split(",")] if "ZBX_ADDITIONAL_TEMPLATES" in os.environ else []

    def grafana_plugin_on(self):
        logger.debug("Grafana Plugin Curl Start")
        plugURL = ("{0}:3000/api/plugins/alexanderzobnin-zabbix-app/settings?enabled=true".format(self.grafana_hostname))
        c = pycurl.Curl()
        c.setopt(c.USERPWD, "%s:%s" % ("admin", self.grafana_password))
        c.setopt(c.URL, plugURL)
        c.setopt(c.POSTFIELDS, '{ '' }')
        c.setopt(c.VERBOSE, True)
        c.perform()

    def grafana_dashboard_starred(self):
        logger.debug("Grafana Dashboard Starred")
        path, dirs, files = os.walk(self.grafana_pt_dashboards).next()
        file_count = len(files)
        print (file_count)

        dashboard_id = 1
        #Condition for find more then one dashboard.json file (need for add to favorite)
        while dashboard_id <= file_count:
              #print (dashboard_id)
              plugURL = ("{0}:3000/api/user/stars/dashboard/{1}".format(self.grafana_hostname, dashboard_id))
              c = pycurl.Curl()
              c.setopt(c.USERPWD, "%s:%s" % ("admin", self.grafana_password))
              c.setopt(c.URL, plugURL)
              c.setopt(c.POSTFIELDS, '{ '' }')
              c.setopt(c.VERBOSE, True)
              c.perform()
              dashboard_id = dashboard_id + 1 #So simply :)

    def grafana_configurator(self):

        #Datasource.yaml Template generation
        with open(self.configuration_folder+"/datasource.yaml.tmpl", 'r') as myfile:
            data = myfile.read().format(self.url, self.admin_password)
            ds_file = open(self.grafana_datas_yaml, "w")
            ds_file.write(data)
            ds_file.close()

        #Dashboard.yaml Template generation
        with open(self.configuration_folder+"/dashboard.yaml.tmpl", 'r') as myfile:
            data = myfile.read()
            db_file = open(self.grafana_dashb_yaml, "w")
            db_file.write(data)
            db_file.close()


        #Grafana Port Checker (need for check, if server start?)
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        timeconn = 1
        timeconn_timeout = 10
        while True:
            time.sleep(1)

            if timeconn == timeconn_timeout:
                break

            result = sock.connect_ex((self.grafana_hostname,3000))
            if result == 0:
                logger.debug("Grafana Server is Started")
                self.grafana_plugin_on() #Enable Plugin
                self.grafana_dashboard_starred() #Add all dashboards to favorite
                break
            else:
                logger.debug("Grafana Server still not start, Try...")
                timeconn = timeconn + 1
        sock.close()


    def login(self):
        logger.debug("Login into Zabbix server (%s)."%(self.url))
        login_error = False
        for attempt in range(0,self.connect_attempts_max_count):
            if login_error:
                logger.info("Login attemtp %d/%d with %d sec inteval."%(attempt+1, self.connect_attempts_max_count, self.connect_attempt_wait_timeout))
                time.sleep(self.connect_attempt_wait_timeout)
            try:
                self.zapi.login(self.default_admin_username, self.default_admin_password)
                login_error = False
                break
            except:
                try:
                    self.zapi.login(self.default_admin_username, self.admin_password)
                    self.default_admin_password=self.admin_password
                    login_error = False
                    break
                except:
                    login_error = True
        if login_error:
            error("Can not login into Zabbix server after %d attemtps."%(attempt))
        self.uid = self.zapi.user.get(filter={"alias": self.default_admin_username})[0]["userid"]

    def logout(self):
        logger.debug("Logout from Zabbix server.")
        self.zapi.logout

    def relogin(self):
        self.logout()
        self.login()

    def change_default_password(self):
        if self.default_admin_password != self.admin_password:
            logger.info("Changing the default admin password.")
            self.zapi.user.update(userid=self.uid, passwd=self.admin_password)
            return 1
        else:
            logger.info("Skip updating the admin password.")
            return 0

    def create_group(self, group_name):
        group = self.zapi.usergroup.get(filter={"name": group_name})
        if len(group)>0:
            logger.debug("Group with name %s is already exist."%(group_name))
            return group[0]["usrgrpid"]
        else:
            logger.debug("Creating group with name: %s."%(group_name))
            return self.zapi.usergroup.create({
                "name": group_name,
                "gui_access": 0,
                "users_status": 0
            })["usrgrpids"][0]

    def add_user_to_group(self, username, group_name):
        uid=self.zapi.user.get(filter={"alias": username})[0]["userid"]
        logger.debug("Check user is already in group %s."%(group_name))
        try:
            group = self.zapi.usergroup.get(filter={"name": group_name},selectUsers=group_name)[0]
        except:
            error("Can not retrieve information from group: %s."%(group_name))
        users_ids = group["users"]
        ids=[]
        if len(users_ids)>0:
            for element in users_ids:
                ids.append(element["userid"])
        if not uid in ids:
            logger.debug("Adding user %s into group %s."%(username, group_name))
            logger.debug("Current list of users in group: "+str(ids if len(ids)>0 else "list is empty")+".")
            ids.append(uid)
            self.zapi.usergroup.update(usrgrpid=group["usrgrpid"], userids=ids)
        else:
            logger.debug("User %s is already included into group %s."%(username, group_name))
            return 0
        return 1

    def disable_user(self, username):
        group_name="Disabled"
        if self.add_user_to_group(username, group_name):
            logger.info("Disabled user: %s."%(username))
        else:
            logger.info("User %s is already disabled."%(username))

    def get_host_info(self, hostname="", host_id=""):
        logger.debug("Retrieving information about host %s."%(hostname))
        rule = {"host": hostname} if hostname != "" else {"hostid": host_id}
        return self.zapi.host.get(filter=rule, selectParentTemplates=[])

    def enable_host(self, host_id):
        host = self.get_host_info(host_id=host_id)
        if host[0]["status"] != "0":
            logger.debug("Enabling host with id %s."%(host_id))
            self.zapi.host.update(hostid=host_id, status=0)
            return 1
        logger.debug("Host with id %s is already enabled."%(host_id))
        return 0

    def update_host_addr(self, host_id, dns="", ip="", use_ip=1):
        interface = self.zapi.hostinterface.get(hostids=[host_id])[0]
        interface_id = interface["interfaceid"]
        if (interface["ip"] != ip) or (interface["dns"] != dns):
            logger.debug("Setting new addresses for host with id %s."%(host_id))
            self.zapi.hostinterface.update(interfaceid=interface_id, ip=ip, dns=dns, port=self.default_agent_port, useip=use_ip)
            return 1
        else:
            return 0

    def update_mediatype(self, name, data=dict()):
        try:
            media=self.zapi.mediatype.get(filter={"description": name})[0]
            data["mediatypeid"] = media["mediatypeid"]
            logger.debug("Updating media with next data:")
            logger.debug(data)
            self.zapi.mediatype.update(data)
        except:
            error("Could not update mediatype with name: %s."%(name))
        return 1

    def update_user_email_settings(self, username, email):
        uid = self.zapi.user.get(filter={"alias": username})[0]["userid"]
        medias = []
        if email.strip() != "":
            logger.debug("Adding new email setting for user %s (uid: %s)."%(username,uid))
            delimiter = ","
            for email_address in email.split(delimiter):
                if check_email(email_address):
                    logger.debug("Adding email address: %s"%(email_address))
                    medias.append({
                        "mediatypeid": 1,
                        "sendto": email_address,
                        "active": 0,
                        "severity": self.default_severity,
                        "period": self.default_notify_period
                    })
            logger.debug("Cleanup current media for user.")
            self.zapi.user.updatemedia(users=[{"userid": uid}], medias=[])
            self.zapi.user.updatemedia(
                users=[{"userid": uid}],
                medias=medias
            )
            return 1
        return 0

    def enable_action(self, name):
        try:
            logger.debug("Trying to get actionid with name: %s."%(name))
            action = self.zapi.action.get(filter={"name": name})[0]
            action_id = action["actionid"]
            logger.debug("ActionID is: %s"%(action_id))
        except:
            logger.debug("Could not retrive action_id.")
            return 0

        if int(action["status"]) != 0:
            logger.debug("Action with id %s is disabled, activating it."%(action_id))
            if self.zapi.action.update(actionid=action_id, status=0):
                logger.debug("Action was successfuly activated.")
        elif int(action["status"]) == 0:
            logger.debug("Action is already activated. Skipped.")
            return 0
        return 1

    def add_action(self, data):
        # Check if exist current action or no
        action = self.zapi.action.get(filter={"name": data["name"]})
        if len(action)>0:
            logger.debug("Action is updated with next data:")
            #  Could not be updated with below element in dict
            del data["eventsource"]
            data["actionid"] = int(action[0]["actionid"])
            logger.debug(data)
            return self.zapi.action.update(data)
        else:
            logger.debug("Action is created.")
            return self.zapi.action.create(data)

    def add_auto_discovery_action(self, metadata=""):
        if metadata != "":
            logger.debug("Generating conditions from metadate elements.")
            conditions = [ { "conditiontype": 24, "operator": 2, "value": data} for data in metadata.split(" ") ]
            logger.debug("Adding auto registration action for hosts with metadata: %s."%(metadata if metadata != "" else "not defined" ))
            data = {
                "name": "Auto registration rules for Linux servers",
                "eventsource": 2,
                "status": 0,
                "operations": [
                    { "operationtype": 2 },
                    { "operationtype": 4, "opgroup": [ self.zapi.hostgroup.get(filter={"name": "Linux servers"})[0]["groupid"] ] },
                    { "operationtype": 6, "optemplate": [ { "templateid": self.zapi.template.get(filter={"name": "Template OS Linux"})[0]["templateid"] } ] },
                    {
                        "operationtype": 0,
                        "opmessage_grp": [{ "usrgrpid": self.zapi.usergroup.get(filter={"name": self.default_admin_group})[0]["usrgrpid"] }],
                        "opmessage": { "mediatypeid": 0, "default_msg": 1}
                    }
                ],
                "def_shortdata": "Auto registration: {HOST.HOST}",
                "def_longdata":
'''
Host name: {HOST.HOST}
Host IP: {HOST.IP}
Agent port: {HOST.PORT}''',
                "filter": {
                    "evaltype": 1,
                    "conditions": conditions
                }
            }
            return self.add_action(data)
        else:
            logger.debug("Host metadata empty, such action is impossible to add because of security reason.")
            return 0

    def add_web_scenario(self, host_id, url_list):
        logger.debug("Processing adding urls for monitoring.")
        self.custom_config_json["web"] = list()
        if len(url_list)>0:
            host_name = self.get_host_info(host_id=host_id)[0]["name"]
            for item in url_list:
                logger.debug(item)
                priority = item["priority"] if "priority" in item else 1
                http_test = self.zapi.httptest.get(filter={"name": item["name"]}, hostids=host_id, selectSteps="extend")
                self.custom_config_json["web"].append({"name": item["name"], "url": item["url"], "priority": priority})
                template = {
                    "hostid": host_id,
                    "name": item["name"],
                    "delay": 60,
                    "retries": 3,
                    "steps": [{
                        "no": 1,
                        "name": "Step #1",
                        "url": item["url"],
                        "status_codes": "200",
                        "follow_redirects": 1,
                        "retrieve_mode": 0
                    }]
                }
                if len(http_test) > 0:
                    if http_test[0]["name"] == template["name"] and http_test[0]["steps"][0]["url"] == template["steps"][0]["url"]:
                        logger.debug("No changed were detected. Skipped updating the web scenario.")
                    else:
                        template["httptestid"] = http_test[0]["httptestid"]
                        del template["hostid"]
                        self.zapi.httptest.update(template)
                else:
                    self.zapi.httptest.create(template)

                trigger = {
                    "description": "Health status of %s"%(item["name"]),
                    "expression": "{"+host_name+":web.test.fail["+item["name"]+"].last(0)} <> 0",
                    "priority": priority,
                    "url": item["url"]
                }

                current_trigger = self.zapi.trigger.get(filter={"description": trigger["description"]})
                if len(current_trigger)>0:
                    trigger["triggerid"] = current_trigger[0]["triggerid"]
                    try:
                        self.update_trigger(trigger)
                    except:
                        error("Can not update the trigger with id %s."%(trigger["triggerid"]))
                else:
                    try:
                        self.create_trigger(trigger)
                    except:
                        error("Can not create the trigger.")
            return 1
        else:
            return 0

    def cleanup_undefined_web_scenario(self, host_id, url_list):
        http_test = self.zapi.httptest.get(hostids=host_id)
        cleanup = False
        for item in http_test:
            key = next((index for (index, d) in enumerate(url_list) if d["name"] == item["name"]), None)
            if (key is None):
                logger.debug("Removing web check for item with name: %s."%(item["name"]))
                self.zapi.httptest.delete(int(item["httptestid"]))
                cleanup = True
        if (cleanup):
            return 1
        return 0

    def create_item(self, data):
        item = self.zapi.item.get(filter={"name": data["name"]})
        if len(item)==0:
            logger.debug("Creating item")
            return self.zapi.item.create(data)
        else:
            data["itemid"] = item[0]["itemid"]
            return self.update_item(data)

    def update_item(self, data):
        logger.debug("Updating item")
        return self.zapi.item.update(data)

    def create_trigger(self, data):
        data["type"] = 0
        trigger = self.zapi.trigger.get(filter={"description": data["description"]})
        if len(trigger)==0:
            logger.debug("Creating trigger.")
            logger.debug(data)
            return self.zapi.trigger.create(data)
        else:
            data["triggerid"] = trigger[0]["triggerid"]
            return self.update_trigger(data)

    def update_trigger(self, data):
        logger.debug("Updating trigger.")
        logger.debug(data)
        return self.zapi.trigger.update(data)

    def get_configuration(self):
        cur = self.db.cursor()
        cur.execute("SELECT * FROM config")
        field = [i[0] for i in cur.description]
        result=dict()
        for i, row in enumerate(cur.fetchone()):
              result[field[i]]=row
        cur.close()
        return result

    def update_configuration(self, config=dict()):
        current = self.get_configuration()
        logger.debug("Comparasing desired config with current.")
        if len(config)>0:
            for key, value in config.items():
                if current[key] == value:
                    del config[key]
        if len(config)>0:
            logger.debug("Updating configuration.")
            logger.debug(config)
            query = "UPDATE config SET "
            i = 0
            length = len(config)
            for key, value in config.iteritems():
                i += 1
                if isinstance(value,int):
                    query += "%s=%d"%(key,value)
                else:
                    query += "%s='%s'"%(key,value)
                if i<length:
                    query += ","

            logger.debug(query)
            cur = self.db.cursor()
            cur.execute(query)
            self.db.commit()
            cur.close()
            return 1
        return 0

    def add_user(self, user=dict(), groups=list(), user_type=1):
        # Check if such user is already exist in database
        u = self.zapi.user.get(filter={"alias": user["name"]})
        if len(u) == 0:
            logger.debug("Such user does not exist. Adding.")
            self.zapi.user.create({
                "alias": user["name"],
                "passwd": user["password"],
                "usrgrps": groups,
                "type": user_type
            })
            return 1
        return 0

    def import_configuration(self):
        configuration_format = "xml"
        files_list = []
        rules = {
            "applications": {
                "createMissing": True
            },
            "discoveryRules": {
                "createMissing": True,
                "updateExisting": True
            },
            "graphs": {
                "createMissing": True,
                "updateExisting": True
            },
            "groups": {
                "createMissing": True
            },
            "hosts": {
                "createMissing": True,
                "updateExisting": True
            },
            "images": {
                "createMissing": True,
                "updateExisting": True
            },
            "items": {
                "createMissing": True,
                "updateExisting": True
            },
            "maps": {
                "createMissing": True,
                "updateExisting": True
            },
            "screens": {
                "createMissing": True,
                "updateExisting": True
            },
            "templateLinkage": {
                "createMissing": True
            },
            "templates": {
                "createMissing": True,
                "updateExisting": True
            },
            "templateScreens": {
                "createMissing": True,
                "updateExisting": True
            },
            "triggers": {
                "createMissing": True,
                "updateExisting": True
            },
        }
        logger.debug("Finding configuration in folder: %s."%(self.configuration_folder))
        if os.access(self.configuration_folder, os.R_OK):
            templates_count = 0
            for filename in os.listdir(self.configuration_folder):
                if filename.endswith(configuration_format):
                    files_list.append(filename)
                    with open(self.configuration_folder+"/"+filename) as f:
                        source = f.read()
                        try:
                            self.zapi.confimport(configuration_format, source, rules)
                        except ZabbixAPIException as e:
                            error(e)
                    logger.debug("Configuration %s was imported/updated."%(filename))
                    templates_count += 1
            if templates_count == 0:
                logger.debug("No configuration was found.")
                return 0
            logger.debug("Was found next list of configratuin templates:")
            logger.debug(files_list)
        else:
            error("Could not access to configuration folder.")

        return 1

    def save_json_config(self, source_json_object = dict(), target_file = ""):
        logger.debug("Saving json object into %s"%target_file)
        if (len(source_json_object) == 0):
            logger.debug("No elements were found in json object.")
            return 0
        logger.debug(source_json_object)
        try:
            with open(target_file, "w") as target:
                json.dump(source_json_object, target, indent=4, sort_keys=True)
                logger.debug("Custom config file was created.")
        except:
            logger.error("JSON object can not be saved into file.")
        return 1

    def get_template_info(self, name="", id=""):
        logger.debug("Retrieving information about template {:s}.".format(name))
        rule = {"host": name} if name != "" else {"id": id}
        return self.zapi.template.get(filter=rule)

    def assign_template(self, host_id, template_name):
        template_id = self.get_template_info(name=template_name)[0]["templateid"]
        logger.debug("Template id: {:s}".format(template_id))
        logger.debug("Assigning template {:s} with host id {:s}".format(template_name,host_id))
        current_templates = self.get_host_info(host_id=host_id)[0]["parentTemplates"]
        data = {
            "hostid": host_id,
            "templates": current_templates
        }
        for item in current_templates:
            if (item["templateid"] == template_id):
                data = {}
                break
        if ("templates" in data):
            data["templates"].append({"templateid": template_id})
        if (len(data) > 0):
            try:
                self.zapi.host.update(data)
            except:
                return 0
        else:
            logger.debug("Template {:s} was already assigned before. Skipped.".format(template_name))
        return 1

    def main(self):
        self.grafana_configurator()
        if self.authentication_type != self.default_authentication_type:
            logger.debug("Changing authentication_type to default to use api with basic credentials.")
            self.update_configuration(config={"authentication_type":self.default_authentication_type})

        self.login()
        if self.change_default_password():
            self.relogin()

        if self.disable_guest:
            self.disable_user(self.guest_username)

        host_id = self.get_host_info(hostname=self.hostname)[0]["hostid"];
        logger.debug("%s has such id: %s."%(self.hostname, host_id))
        logger.info("Associate local agent with %s."%(self.hostname) if self.update_host_addr(host_id, self.agent_dns_name, self.agent_ip_address, 0) else "Skipped address updating %s."%(self.hostname))
        logger.info("Enabled %s host."%(self.hostname) if self.enable_host(host_id) else "Skipped enabling %s."%(self.hostname))
        logger.info("Configured default email media type." if self.update_mediatype(name="Email",data={"smtp_server": self.smtp_server, "smtp_email": self.smtp_email, "smtp_helo": self.smtp_helo}) else "Skipped configuring default media type.")
        logger.info("Updated %s user email settings."%(self.default_admin_username) if self.update_user_email_settings(username=self.default_admin_username, email=self.admin_email_address) else "Skipped updating email settings")
        logger.info("Enabled default notify action." if self.enable_action(self.default_report_action) else "Skipped activating the default notify action.")
        logger.info("Added/Updated auto discovery action." if self.add_auto_discovery_action(self.host_metadata) else "Skipped adding auto discovery action.")
        logger.info("Initialization checking web urls." if self.add_web_scenario(host_id=host_id, url_list=self.url_list) else "Skipped initialization of web urls.")
        logger.info("Cleanup undefined web urls." if self.cleanup_undefined_web_scenario(host_id=host_id, url_list=self.url_list) else "Skipped cleanup of web urls. Nothing was found.")
        logger.info("Adding zabbix configuration templates." if self.configuration_folder != "" and self.import_configuration() else "No configuration templates folder was identified.")

        logger.info("Creating default user group %s."%(self.default_user_group))
        group_id = self.create_group(self.default_user_group)
        if len(self.admin_users)>0:
            for user in self.admin_users:
                logger.info("Adding user %s as administrator."%(user["name"]))
                if not self.add_user(user=user, groups = [{ "usrgrpid": group_id }], user_type=3):
                    logger.info("Skipped.")

        logger.info("Updating Zabbix configuration" if self.update_configuration(self.configuration) else "Nothing to update. Skipped.")
        if self.authentication_type != self.default_authentication_type:
            logger.debug("Returned authentication_type to initial state.")
            self.update_configuration(config={"authentication_type": self.authentication_type})
        # This step must be the last, when custom_config_json is already prepared for saving
        logger.info("Creating custom config." if self.save_json_config(self.custom_config_json, self.zabbix_custom_config) else "Skipped. Nothing to be saved.")
        for template_name in self.additional_templates:
            logger.info("Assigning templates with %s default host."%self.hostname if self.assign_template(host_id, template_name) else "Cannot assign template with host %s."%self.hostname)

        return self.logout()

if __name__ == "__main__":
    app = Configurator()
    try:
        exit(app.main())
    except KeyboardInterrupt:
        error("Interrupted by user.")
    except Exception:
        raise
