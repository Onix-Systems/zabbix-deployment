### About
Repository contain docker-compose project for running zabbix server on your own server
Also there is Dockerfile that contains zabbix agent

1. Zabbix server 3.4
1. Zabbix frontend
1. Zabbix agent (will be installed on host, not run inside the docker container)
1. MariaDB 10.3
1. Exim4 SMTP service

PS: Are used official docker images: https://hub.docker.com/u/zabbix/

###
Requirements

1. Debian family OS (scripts limits)
1. docker-ce (1.13.0+)
1. docker-compose

### Preparing configuration file for server

If default options are not enough, then please use `.env.example` to create own environment configuration file.

### Run Zabbix server

```shell
$ ./x-setup-server.sh
```
After server will be launched, this script will call `./x-setup-agent.sh` to install
Zabbix agent on host machine, where Zabbix server works inside the docker environment.

#### Run and configured only server components
```shell
$ docker-compose up -d
```

### Install and configured external agent

For server it is not necessary to run below described command, `./setup-server.sh` will launch it by self.

```shell
$ ./x-setup-agent.sh --help
...
$ ./x-setup-agent.sh -m "Linux ${DEFAULT_HOST_SECRET}" -s zabbix.local --hostname $(hostname -f)
```

Frontend url is: http://localhost if you launch project on your local machine.

Default user for zabbix is: admin / zabbix

To run project with specific options, please see `.env.example` file.
To apply non default option, copy `.env.example` file to `.env` and
edit necessary values there.

#### Testing a deployment of environment

Project contains Vagrantfile that can be used for testing running the project.

If VM does not exist yes, launch next command:
```
$ vagrant up
```

After succesfully completed provision scenario it is possible to get access to
Zabbix UI by url: http://localhost:8080.

Repeat provision scenario
```
$ vagrant provision
```
