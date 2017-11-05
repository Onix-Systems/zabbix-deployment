#!/bin/bash

printf "Checking OS compartible. "
docker version &> /dev/null
if [ "$?" -ne 0 ]; then echo "Failed, docker-engine could not be found."; exit 1; fi
docker-compose --version &> /dev/null
if [ "$?" -ne 0 ]; then echo "Failed, docker-compose could not be found."; exit 1; fi
echo "Done."

# set -e

cd $(dirname $0/)

# Setting default variables
SUBNET_PREFIX=172.15.0.
DEFAULT_HOST_SECRET=""
# Loading project options and overriding default variables
if [ -e ".env" ];  then source .env; fi
SERVER=${SUBNET_PREFIX}254

printf "Building, launching and configuring Zabbix server. "
docker-compose build &> /dev/null
docker-compose up -d &> /dev/null
echo "Done."
echo "Installing and configuring host's agent."
echo $DEFAULT_HOST_METADATA
./x-setup-agent.sh \
    -s ${SERVER} \
    -l ${SUBNET_PREFIX}1 \
    --hostname $(hostname -f) \
    -m "Linux ${DEFAULT_HOST_SECRET}" \
    --enable-docker-module \
    --enable-ssl-params
