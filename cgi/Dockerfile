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
    sysstat \
    rsync \
    ssh \
    curl \
    python2.7-dev \
    python-pip \
    python-dev \
    python-pip \
    python-setuptools \
    build-essential
#
# update pip
#
RUN pip install --upgrade pip
RUN pip install --upgrade setuptools
# pip install --upgrade csvkit
#
# install CSVKIT
#
RUN git clone https://github.com/wireservice/csvkit; cd csvkit; pip install .

#
# Copy "AAH" scripts & credentials
#
COPY *.cgi *.csh *.bash ~_www/CGI/
COPY ~/.cloudant_url ~_www/

#
# Ports for CGI access
#
EXPOSE 80

#
# Create volume to store cache'd copies and temporary files
#
ENV TMP /var/lib/age-at-home
WORKDIR ${TMP}
VOLUME ["${TMP}"]

#
# invoke web server
#
CMD [ "/usr/bin/fortune" ]
