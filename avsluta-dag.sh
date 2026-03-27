#!/bin/bash

# Avsluta Dag - Auto commit & push till GitHub
# Användning: ./avsluta-dag.sh

WORKSPACE_PATH="${WORKSPACE_PATH:-$HOME}"
cd "$WORKSPACE_PATH" || exit 1

echo "📦 Avslutar arbetsdagen..."
echo "📁 Workspace: $WORKSPACE_PATH"
echo ""

# Kolla git status
echo "🔍 Kollar ändringar..."
git status --short

if ! git diff-index --quiet HEAD -- 2>/dev/null; then
    echo ""
    echo "📊 Ändrade filer:"
    git diff --stat
    echo ""

    # Auto-generera commit-meddelande baserat på ändringar
    echo "✍️  Genererar commit-meddelande..."

    # Enkel heuristik för commit-meddelande
    CHANGED_FILES=$(git diff --name-only --cached 2>/dev/null)
    UNSTAGED_FILES=$(git diff --name-only 2>/dev/null)
    UNTRACKED_FILES=$(git ls-files --others --exclude-standard 2>/dev/null)

    ALL_FILES="$CHANGED_FILES $UNSTAGED_FILES $UNTRACKED_FILES"

    # Hitta mest frekvent mapp
    MAIN_DIR=$(echo "$ALL_FILES" | grep -o '^[^/]*' | sort | uniq -c | sort -rn | head -1 | awk '{print $2}')

    if [ -z "$MAIN_DIR" ]; then
        COMMIT_MSG="Uppdateringar från arbetsdag $(date +%Y-%m-%d)"
    else
        COMMIT_MSG="Arbete på $MAIN_DIR - $(date +%Y-%m-%d)"
    fi

    echo "💬 Commit-meddelande: \"$COMMIT_MSG\""
    echo ""

    # Git add
    echo "➕ Lägger till ändringar..."
    git add .

    # Git commit
    echo "💾 Commit:ar..."
    git commit -m "$COMMIT_MSG"

    # Git push
    echo "☁️  Pushar till GitHub..."
    if git push; then
        echo ""
        echo "✅ Allt sparat och synkat till GitHub!"
        echo "🎉 Bra jobbat idag!"
    else
        echo ""
        echo "⚠️  Push misslyckades. Kolla git remote och behörigheter."
        exit 1
    fi
else
    echo ""
    echo "✅ Inga ändringar att spara - allt redan synkat!"
    echo "👋 Ha en bra kväll!"
fi
