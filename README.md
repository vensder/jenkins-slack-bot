# Jenkins Slack Bot

Bot can help you to deploy custom branches (or tags) of docker images on differents environments.

## Build the bot.

```bash
docker build -t mybot .
```

## Run the bot

```bash
docker run --rm -v "$PWD"/config:/usr/src/app/config mybot \
    cp rtmbot.conf.example config/rtmbot.conf
```

```bash
docker run -d --rm -v "$PWD"/config:/usr/src/app/config \
    -v "$PWD"/log:/usr/src/app/log mybot
```

```bash
docker run -d --rm -e PYTHONUNBUFFERED=0 --rm \
    -v "$PWD"/log:/usr/src/app/log mybot
```

```bash
docker run -d -e PYTHONUNBUFFERED=0 --restart on-failure:30 \
    -v "$PWD"/config:/usr/src/app/config \
    -v "$PWD"/log:/usr/src/app/log <hub.docker.com.user>/jenkins-bot
```

