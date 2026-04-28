#!/bin/bash
# Gideon entrypoint — clones axona-brain at runtime if BRAIN_PATH is set
# but the directory doesn't exist yet (first run on Fly volume).
set -e

if [ -n "$BRAIN_PATH" ]; then
    if [ ! -d "$BRAIN_PATH/.git" ]; then
        echo "🧠 Brain not found at $BRAIN_PATH — cloning axona-brain..."
        if [ -z "$BRAIN_GIT_KEY_B64" ]; then
            echo "⚠️ BRAIN_GIT_KEY_B64 secret missing — cannot clone private repo"
            echo "   Bot will start without brain integration"
        else
            mkdir -p ~/.ssh
            echo "$BRAIN_GIT_KEY_B64" | base64 -d > ~/.ssh/brain_key
            chmod 600 ~/.ssh/brain_key
            cat > ~/.ssh/config <<EOF
Host github.com
    IdentityFile ~/.ssh/brain_key
    StrictHostKeyChecking no
    UserKnownHostsFile=/dev/null
EOF
            chmod 600 ~/.ssh/config
            git config --global user.email "gideon@axonadigital.se"
            git config --global user.name "gideon-bot"
            git clone git@github.com:Axona-Digital/axona-brain.git "$BRAIN_PATH" || \
                echo "⚠️ Clone failed — bot starts without brain"
        fi
    else
        echo "🧠 Brain found at $BRAIN_PATH — pulling latest"
        cd "$BRAIN_PATH" && git pull --quiet --rebase || true
        cd /app
    fi
fi

exec python bot.py
