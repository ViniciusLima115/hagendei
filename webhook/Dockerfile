FROM docker:27-cli

RUN apk add --no-cache git bash curl gettext

RUN WEBHOOK_VERSION=2.8.0 && \
    wget -qO /tmp/webhook.tar.gz \
    https://github.com/adnanh/webhook/releases/download/${WEBHOOK_VERSION}/webhook-linux-amd64.tar.gz && \
    tar -xzf /tmp/webhook.tar.gz -C /tmp && \
    mv /tmp/webhook-linux-amd64/webhook /usr/local/bin/webhook && \
    chmod +x /usr/local/bin/webhook && \
    rm -rf /tmp/webhook*

WORKDIR /app

EXPOSE 9000
CMD ["sh", "-c", "envsubst < /hooks/hooks.json.tpl > /tmp/hooks.json && webhook -hooks /tmp/hooks.json -port 9000 -verbose"]
