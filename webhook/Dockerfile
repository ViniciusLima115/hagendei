FROM docker:27-cli

RUN apk add --no-cache git bash curl gettext

RUN WEBHOOK_VERSION=2.8.1 && \
    wget -qO /usr/local/bin/webhook \
    https://github.com/adnanh/webhook/releases/download/${WEBHOOK_VERSION}/webhook-linux-amd64 && \
    chmod +x /usr/local/bin/webhook

WORKDIR /app

EXPOSE 9000
CMD ["sh", "-c", "envsubst < /hooks/hooks.json.tpl > /tmp/hooks.json && webhook -hooks /tmp/hooks.json -port 9000 -verbose"]
