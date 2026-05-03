[
  {
    "id": "deploy",
    "execute-command": "/hooks/deploy.sh",
    "command-working-directory": "/app",
    "pass-environment-to-command": [
      {
        "source": "entire-payload",
        "envname": "WEBHOOK_PAYLOAD"
      }
    ],
    "trigger-rule": {
      "and": [
        {
          "match": {
            "type": "payload-hmac-sha256",
            "secret": "${WEBHOOK_SECRET}",
            "parameter": {
              "source": "header",
              "name": "X-Hub-Signature-256"
            }
          }
        },
        {
          "match": {
            "type": "value",
            "value": "refs/heads/main",
            "parameter": {
              "source": "payload",
              "name": "ref"
            }
          }
        }
      ]
    }
  }
]
