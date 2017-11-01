#!/usr/bin/python

#
# This script is used for configuring Zabbix server by using API
#

import argparse, json, logging, os, re, socket, time
from pyzabbix import ZabbixAPI

parser = argparse.ArgumentParser(prog="./configurator.py", description="Zabbix configurator")
parser.add_argument("--debug", action="store_true", help="Enable debug mode")
args = parser.parse_args()
options = vars(args)

logging.basicConfig()
logger = logging.getLogger('Configurator')
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
        self.url = os.environ["ZBX_SERVER_URL"]
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
        # If server is unreachable than try to reconnect self.attempts_max_count times after wait timeout
        self.login_attempt_wait_timeout = 5
        self.login_attempts_max_count = 10
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
        self.default_report_action = "Report problems to "+self.default_admin_group
        # Auto registration
        self.host_metadata = "Linux "+os.environ["DEFAULT_HOST_SECRET"] if "DEFAULT_HOST_SECRET" in os.environ and os.environ["DEFAULT_HOST_SECRET"].strip() != "" else ""
        # Web scenario list
        self.url_list = json.loads(os.environ["URL_LIST"]) if "URL_LIST" in os.environ and os.environ["URL_LIST"].strip() != "" else []
        #
        self.zapi = ZabbixAPI(self.url)

    def login(self):
        logger.debug("Login into Zabbix server (%s)."%(self.url))
        login_error = False
        for attempt in range(0,self.login_attempts_max_count):
            if login_error:
                logger.info("Login attemtp %d/%d with %d sec inteval."%(attempt+1, self.login_attempts_max_count, self.login_attempt_wait_timeout))
                time.sleep(self.login_attempt_wait_timeout)
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
        logger.debug("Retrieving inforation about host %s."%(hostname))
        rule = {"host": hostname} if hostname != "" else {"hostid": host_id}
        return self.zapi.host.get(filter=rule)

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
        if len(url_list)>0:
            host_name = self.get_host_info(host_id=host_id)[0]["name"]
            for item in url_list:
                logger.debug(item)
                http_test = self.zapi.httptest.get(filter={"name": item["name"]}, hostids=host_id, selectSteps="extend")
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
                        logger.debug("No changed were detected. Skipped updating the web scenario")
                        continue
                    template["httptestid"] = http_test[0]["httptestid"]
                    del template["hostid"]
                    self.zapi.httptest.update(template)
                else:
                    self.zapi.httptest.create(template)
                trigger = {
                    "description": "Availability of %s by url"%(item["name"]),
                    "expression": "{"+host_name+":web.test.fail["+item["name"]+"].last(0)} <> 0",
                    "priority": item["priority"] if "priority" in item else 1,
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

    def create_trigger(self, data):
        data["type"] = 0
        logger.debug("Creating trigger.")
        logger.debug(data)
        return self.zapi.trigger.create(data)

    def update_trigger(self, data):
        logger.debug("Updateing trigger.")
        logger.debug(data)
        return self.zapi.trigger.update(data)

    def main(self):
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

        return self.logout()

if __name__ == "__main__":
    app = Configurator()
    try:
        exit(app.main())
    except KeyboardInterrupt:
        error("Interrupted by user.")
    except Exception:
        raise
