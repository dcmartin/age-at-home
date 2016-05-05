FROM ubuntu:latest

MAINTAINER dcmartin <github@dcmartin.com>

#
# install packages for "motion" and mail support
#
RUN apt-get update && apt-get install -q -y --no-install-recommends \
    apt-utils \
    tcsh \
    git \
    jq \
    gawk \
    sysstat rsync ssh \
    curl \
    python2.7-dev \
    python-pip

RUN git clone https://github.com/wireservice/csvkit; cd csv kit; pip install .

#
# install data-dog (X86 container)
#
RUN sh -c "$(curl -L https://raw.githubusercontent.com/DataDog/dd-agent/master/packaging/datadog-agent/source/setup_agent.sh)"
RUN mv ~/.datadog-agent/agent/datadog.conf.example ~/.datadog-agent/agent/datadog.conf \
    && sed -i -e"s/^.*non_local_traffic:.*$/non_local_traffic: yes/" ~/.datadog-agent/agent/datadog.conf \
    && sed -i -e"s/^.*log_to_syslog:.*$/log_to_syslog: no/" ~/.datadog-agent/agent/datadog.conf \
    && rm ~/.datadog-agent/agent/conf.d/network.yaml.default

#
# install IBM IoTF quickstart (Raspberry Pi)
#
#
# RUN echo "#! /bin/sh\nexit 0" > /usr/sbin/policy-rc.d
# RUN curl -LO https://github.com/ibm-messaging/iot-raspberrypi/releases/download/1.0.2.1/iot_1.0-2_armhf.deb
# RUN dpkg -i iot_1.0-2_armhf.deb

#
# Copy "AAH" scripts & credentials
#
COPY * ~_www/CGI/
COPY ~/.cloudant_url ~_www/

#
# Ports for motion (control and stream)
#
EXPOSE 80

#
# Create volume to store cache'd copies and temporary files
#
ENV TMP /var/lib/aah
WORKDIR ${TMP}
VOLUME ["${TMP}"]

#
# invoke web server
#
CMD [ "/usr/bin/fortune" ]
