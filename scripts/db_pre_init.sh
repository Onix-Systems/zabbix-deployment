#!/bin/bash

CONFIG_FILE=${HOME}/.my.cnf
OPT_FILE=/etc/mysql/conf.d/inno.cnf
if [ ! -z "MYSQL_ROOT_PASSWORD" ] && [ ! -e "${CONFIG_FILE}" ]; then
    echo "Creating ${HOME}/.my.cnf file..."
    cat << EOF > ${CONFIG_FILE}
[client]
user=root
password=${MYSQL_ROOT_PASSWORD}
EOF

cat << EOF > ${OPT_FILE}

[mysqld]
innodb_flush_method=O_DSYNC
innodb_force_recovery=1
innodb_flush_log_at_trx_commit = 0
innodb_log_file_size = 512M
innodb_log_files_in_group = 3
innodb_strict_mode=0
EOF


fi
