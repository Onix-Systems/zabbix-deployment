#!/usr/bin/python

import argparse, json, logging

parser = argparse.ArgumentParser(prog="./web.py", description="Web extension")
parser.add_argument("--debug", action="store_true", help="Enable debug mode")
parser.add_argument("--config", default="web_list.json", help="JSON list of web urls")
args = parser.parse_args()
options = vars(args)

logging.basicConfig()
logger = logging.getLogger("WebExtension")
logger.setLevel("DEBUG" if options["debug"] else "INFO")

class Web:
    def __init__(self, options=dict()):
        self.config_file = options["config"]
        self.debug = options["debug"]
        self.url_list = self.read_config()

    def read_config(self):
        with open(self.config_file,"r") as config_file:
            return json.load(config_file)
        return 0

    def main(self):
        logger.debug("Reading url list from config file.")
        logger.debug(self.url_list)
        return 0

if __name__ == "__main__":
    app = Web(options)
    try:
        exit(app.main())
    except KeyboardInterrupt:
        logger.error("Interrupted by user.")
    except:
        raise
