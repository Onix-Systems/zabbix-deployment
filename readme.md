### About
Repository contain docker-compose project for running zabbix server on your own server
Also there is Dockerfile that contains zabbix agent

Zabbix server 3.4
MariaDB 10.3

###
Requirements

1. docker-ce
1. docker-compose

### Run Zabbix server

```shell
$ cd server
$ docker-compose up -d
```

Frontend url is: http://localhost if you launch project on your local machine.

Default user for zabbix is: admin / zabbix

To run project with specific options, please see `server/.env.example` file.
To apply non default option, copy `server/.env.example` file to `server/.env` and
edit necessary values there.
