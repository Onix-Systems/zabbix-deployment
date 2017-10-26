#!/usr/bin/python

#
# This script is used for configuring Zabbix server by using API
#

import os, logging, argparse, socket
from pyzabbix import ZabbixAPI

parser = argparse.ArgumentParser(prog="./configurator.py", description="Zabbix configurator")
parser.add_argument("--debug", action="store_true", help="Enable debug mode")
args = parser.parse_args()
options = vars(args)

logging.basicConfig()
logger = logging.getLogger('Configurator')
logger.setLevel("DEBUG" if options["debug"] else "INFO")

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

        self.zapi = ZabbixAPI(self.url)

    def login(self):
        logger.debug('Login into Zabbix server (%s)'%(self.url))
        try:
            self.zapi.login(self.default_admin_username, self.default_admin_password)
        except:
            try:
                self.zapi.login(self.default_admin_username, self.admin_password)
                self.default_admin_password=self.admin_password
            except:
                logger.critical("Can not login into Zabbix server.")
                exit(1)
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

    def add_user_to_group(self,username,group_name):
        uid=self.zapi.user.get(filter={"alias": username})[0]["userid"]
        logger.debug("Check user is already in group %s"%(group_name))
        try:
            group = self.zapi.usergroup.get(filter={"name": group_name},selectUsers=group_name)[0]
        except:
            logger.error("Can not retrieve information from group: %s"%(group_name))
            exit(1)
        users_ids = group["users"]
        ids=[]
        if len(users_ids)>0:
            for element in users_ids:
                ids.append(element["userid"])
        if not uid in ids:
            logger.debug("Adding user %s into group %s."%(username, group_name))
            logger.debug("Current list of users in group: "+str(ids if len(ids)>0 else 'list is empty.'))
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
        logger.debug("Retrieving inforation about host %s"%(hostname))
        rule = {"host": hostname} if hostname != "" else {"hostid": host_id}
        return self.zapi.host.get(filter=rule)

    def enable_host(self, host_id):
        host = self.get_host_info(host_id=host_id)
        if host[0]["status"] != "0":
            logger.debug("Enabling host with id %s"%(host_id))
            self.zapi.host.update(hostid=host_id, status=0)
            return 1
        logger.debug("Host with id %s is already enabled"%(host_id))
        return 0

    def update_host_addr(self, host_id, dns="", ip="", use_ip=1):
        interface = self.zapi.hostinterface.get(hostids=[host_id])[0]
        interface_id = interface["interfaceid"]
        if (interface["ip"] != ip) or (interface["dns"] != dns):
            logger.debug("Setting new addresses for host with id %s"%(host_id))
            self.zapi.hostinterface.update(interfaceid=interface_id, ip=ip, dns=dns, port=self.default_agent_port, useip=use_ip)
            return 1
        else:
            return 0

    def main(self):
        self.login()
        if self.change_default_password():
            self.relogin()

        if self.disable_guest:
            self.disable_user(self.guest_username)

        host_id = self.get_host_info(hostname=self.hostname)[0]["hostid"];
        logger.debug("%s has such id: %s"%(self.hostname, host_id))
        logger.info("Associate local agent with %s"%(self.hostname) if self.update_host_addr(host_id, self.agent_dns_name, self.agent_ip_address, 0) else "Skipped address updating %s"%(self.hostname))
        logger.info("Enabled %s host"%(self.hostname) if self.enable_host(host_id) else "Skipped enabling %s"%(self.hostname))

        return self.logout()

if __name__ == "__main__":
    app = Configurator()
    try:
        exit(app.main())
    except KeyboardInterrupt:
        logger.critical("Interrupted by user.")
        exit(1)
    except Exception:
        raise
