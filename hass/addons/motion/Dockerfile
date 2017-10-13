FROM %%BASE_IMAGE%%
#FROM homeassistant/amd64-base:latest

ENV LANG C.UTF-8
#LABEL io.hass.version="00"

RUN echo "@testing http://nl.alpinelinux.org/alpine/edge/testing" >> /etc/apk/repositories

RUN apk update

RUN apk add motion@testing

# REQUIRED: packages
RUN apk add mosquitto-clients jq

# Copy "motion" scripts 
COPY scripts/* /usr/local/bin/
COPY motion.conf /etc/motion/motion.conf

# Ports for motion (control and stream)
EXPOSE 8080 8081

# Create volume to store images & videos
VOLUME ["/var/lib/motion"]

# set working directory
WORKDIR /var/lib/motion

# invoke motion detection script (NOT as daemon; re-direct logging to STDERR)
CMD [ "/usr/local/bin/run.sh" ]

