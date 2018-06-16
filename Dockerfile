FROM httpd:2.4

MAINTAINER dcmartin <github@dcmartin.com>

RUN apt-get update && apt-get install -q -y --no-install-recommends \
    apt-utils \
    bc \
    tcsh \
    git \
    gawk \
    sysstat \
    rsync \
    ssh \
    curl \
    dateutils \
    imagemagick \
    python2.7-dev \
    python-pip \
    python-dev \
    python-pip \
    python-setuptools \
    build-essential \
    gcc \
    make \
    automake \
    libtool \
    bison \
    flex \
    wget \
    dh-autoreconf \
    debhelper \
    libtool-bin \
    valgrind \
    rake \
    ruby-ronn \
    libonig-dev

# update pip
RUN pip install --upgrade pip
RUN pip install --upgrade setuptools
RUN pip install --upgrade csvkit --ignore-installed six

# install JQ
RUN git clone https://github.com/stedolan/jq.git && cd jq && autoreconf -i && ./configure --disable-maintainer-mode && make && make install

###
### AAH 
###

# variables
ARG AAHDIR=/var/lib/age-at-home 
ARG CREDIR=/usr/local/etc

# environment
ENV DIGITS_HOST 192.168.1.40:32769
ENV CAMERA_IMAGE_WIDTH 640
ENV CAMERA_IMAGE_HEIGHT 480
ENV MODEL_IMAGE_WIDTH 224
ENV MODEL_IMAGE_HEIGHT 224
ENV CAMERA_MODEL_TRANSFORM CROP
ENV CREDENTIALS ${CREDIR}
ENV TMP /tmp

# temporary files & credentials
RUN mkdir -p ${AAHDIR} ${CREDIR}
RUN chmod 777 ${AAHDIR} && chmod 755 ${CREDIR}

VOLUME ["${AAHDIR}"]

# credentials
COPY ./.cloudant_url ${CREDIR}
RUN chmod 444 ${CREDIR}/.cloudant_url
COPY ./.watson.visual-recognition.json ${CREDIR}
RUN chmod 444 ${CREDIR}/.watson.visual-recognition.json
COPY ./.ftp_url ${CREDIR}
RUN chmod 444 ${CREDIR}/.ftp_url

# html
COPY ./public/ /usr/local/apache2/htdocs/

# cgi
COPY ./cgi/aah-*.csh /usr/local/apache2/cgi-bin/
COPY ./cgi/aah-*.cgi /usr/local/apache2/cgi-bin/
COPY ./cgi/aah-*.bash /usr/local/apache2/cgi-bin/

# httpd
COPY ./httpd.conf /usr/local/apache2/conf/httpd.conf
