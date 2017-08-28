FROM python:3.6-alpine

#RUN mkdir -p /usr/src/app
WORKDIR /usr/src/app/

COPY . /usr/src/app

VOLUME /usr/src/app/config
VOLUME /usr/src/app/log

RUN pip install -r /usr/src/app/requirements.txt

CMD rtmbot -c /usr/src/app/config/rtmbot.conf



