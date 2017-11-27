#!/usr/bin/python

import argparse, json, logging, os, sys

CMD_DISCOVERY = "discovery"
ALL = -1

parser = argparse.ArgumentParser(prog="./%s"%(os.path.basename(sys.argv[0])), description="External script for Zabbix agent")
parser.add_argument(CMD_DISCOVERY, help="URL discovery command")
parser.add_argument("--debug", action="store_true", help="Enable debug mode")
parser.add_argument("--config", default="url_list.json", help="JSON list of web urls")
parser.add_argument("--protocol", default=ALL, choices=[ALL,"http","https"], help="Limit url discovery mode by url protocol")
parser.add_argument("--priority", default=ALL, type=int, help="Limit url discovery mode by url checking priority")

args = parser.parse_args()
options = vars(args)

logging.basicConfig()
logger = logging.getLogger("WebExtension")
logger.setLevel("DEBUG" if options["debug"] else "INFO")

logger.debug("Current options are next:")
logger.debug(options)

class Web:
    def __init__(self, options=dict()):
        self.config_file = options["config"]
        self.debug = options["debug"]
        self.protocol = options["protocol"]
        self.priority = options["priority"]
        self.url_list = self.read_config()
        if CMD_DISCOVERY in options:
            self.command = CMD_DISCOVERY

    def read_config(self):
        with open(self.config_file,"r") as config_file:
            return json.load(config_file)
        return 0

    def discovery(self, protocol = ALL, priority = ALL):
        logger.debug("Discoverying of url list.")
        result = []
        for item in self.url_list:
            if protocol != ALL and item["url"].split(":")[0] != protocol:
                continue
            if priority != ALL and int(item["priority"]) != priority:
                continue
            result.append({
                "{#DESCRIPTION}": item["name"],
                "{#URL}": item["url"]
            })
        return {"data": result}

    def main(self):
        logger.debug("Reading url list from config file.")
        logger.debug(self.url_list)
        if self.command == CMD_DISCOVERY:
            print self.discovery(protocol = self.protocol, priority = self.priority)
        return 0

if __name__ == "__main__":
    app = Web(options)
    try:
        exit(app.main())
    except KeyboardInterrupt:
        logger.error("Interrupted by user.")
    except:
        raise
