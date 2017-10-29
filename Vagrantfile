# -*- mode: ruby -*-
# vi: set ft=ruby :

Vagrant.configure("2") do |config|
  config.vm.box = "ubuntu/xenial64"
  config.vm.network "private_network", ip: "192.168.33.102"
  config.vm.network "forwarded_port", guest: 80, host: 8080
  config.vm.provider "virtualbox" do |vb|
      vb.memory = "2048"
  end
  config.vm.provision "shell", inline: <<-SHELL
      set -e
      APT_FILE="/etc/apt/sources.list"
      [ ! -e "${APT_FILE}.orig" ] && cp ${APT_FILE} ${APT_FILE}.orig
      sed -i 's,http://archive,http://ua.archive,g' ${APT_FILE}
      # Set our native time zone in VM
      ln -sf /usr/share/zoneinfo/Europe/Kiev /etc/localtime
      # mc repo
      echo "deb http://www.tataranovich.com/debian $(lsb_release -cs) main" > /etc/apt/sources.list.d/mc.list
      apt-key adv --keyserver pool.sks-keyservers.net --recv-keys 0x836CC41976FB442E
      apt-get update
      apt-get install -y \
          apt-transport-https \
          ca-certificates \
          curl \
          software-properties-common
      curl -fsSL https://download.docker.com/linux/ubuntu/gpg | apt-key add -
      add-apt-repository "deb [arch=amd64] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable"
      apt-key fingerprint 0EBFCD88
      apt-get install -y \
          docker-ce \
          iotop \
          htop \
          mc
      #
      echo "Getting docker-compose from official repository..."
      if [ ! -e "/usr/local/bin/docker-compose" ]; then
          curl -L https://github.com/docker/compose/releases/download/1.16.1/docker-compose-`uname -s`-`uname -m` -o /usr/local/bin/docker-compose
          chmod +x /usr/local/bin/docker-compose
      else
          echo "Skip this step, because docker-compose is already exist!"
      fi
      mkdir -p /var/lib/data
      ln -sf /var/lib/data /vagrant/data
      cd /vagrant
      ./scripts/setup-server.sh
  SHELL

end
