#!/bin/bash

printf "Checking OS compartible. "
docker version &> /dev/null
if [ "$?" -ne 0 ]; then echo "Failed (docker-engine could not be found)."; exit 1; fi
docker-compose --version &> /dev/null
if [ "$?" -ne 0 ]; then echo "Failed (please install docker-compose)."; exit 1; fi
echo "Done."

set -e

cd $(dirname $0/)

# Setting default variables
SUBNET_PREFIX=172.15.0.
# Loading project options and overriding default variables
if [ -e "../.env" ];  then source ../.env; fi
SERVER=${SUBNET_PREFIX}254

printf "Building, launching and configuring Zabbix server. "
docker-compose build &> /dev/null
docker-compose up -d &> /dev/null
echo "Done."
echo "Installing and configuring host's agent."
./setup-agent.sh -s ${SERVER} -l ${SUBNET_PREFIX}1
