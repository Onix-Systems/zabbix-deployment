ARG BROWSER=chrome

FROM selenium/standalone-${BROWSER}-debug

LABEL maintainer="devops@onix-systems.com"

ENV SELENIUM_ADDRESS=127.0.0.1 \
    SELENIUM_PORT=4444

USER root
RUN apt-get update && \
    apt-get install -y \
      python \
      python-pip && \
    pip install selenium && \
    wget -q https://raw.githubusercontent.com/pgrange/bash_unit/master/bash_unit -O /usr/local/bin/bash_unit && \
    chmod +x /usr/local/bin/bash_unit

USER seluser
