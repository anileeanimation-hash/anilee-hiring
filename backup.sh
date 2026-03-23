#!/bin/bash
# ─────────────────────────────────────────────────────────────
# Anilee Hiring Portal — Local Backup Script
# Run anytime: bash backup.sh
# Backs up: database, OAuth token, credentials, secrets
# ─────────────────────────────────────────────────────────────

PORTAL="/Users/shagunsalunkhe/Documents/Claude/hiring_portal"
BACKUP="/Users/shagunsalunkhe/Documents/Claude/hiring_portal_backup"
STAMP=$(date +"%Y-%m-%d_%H-%M")

echo "🔒 Anilee Hiring Portal — Backup Starting..."
echo "📅 Timestamp: $STAMP"
echo ""

mkdir -p "$BACKUP"
mkdir -p "$BACKUP/history"

# ── Current backup (always overwritten — latest version) ─────
cp "$PORTAL/hiring.db"                "$BACKUP/hiring.db"        && echo "✅ hiring.db"
cp "$PORTAL/token.pkl"                "$BACKUP/token.pkl"        && echo "✅ token.pkl"
cp "$PORTAL/credentials.json"         "$BACKUP/credentials.json" && echo "✅ credentials.json"
cp "$PORTAL/.streamlit/secrets.toml"  "$BACKUP/secrets.toml"     && echo "✅ secrets.toml"
cp "$PORTAL/.streamlit/config.toml"   "$BACKUP/config.toml"      && echo "✅ config.toml"

# ── Timestamped snapshot (keeps history, never overwritten) ──
SNAP="$BACKUP/history/$STAMP"
mkdir -p "$SNAP"
cp "$PORTAL/hiring.db"                "$SNAP/hiring.db"
cp "$PORTAL/token.pkl"                "$SNAP/token.pkl"         2>/dev/null
cp "$PORTAL/credentials.json"         "$SNAP/credentials.json"  2>/dev/null
cp "$PORTAL/.streamlit/secrets.toml"  "$SNAP/secrets.toml"      2>/dev/null

echo ""
echo "📦 Snapshot saved to: $SNAP"
echo ""

# ── DB Summary ───────────────────────────────────────────────
echo "📊 Database Contents:"
python3 -c "
import sqlite3
conn = sqlite3.connect('$PORTAL/hiring.db')
c = conn.cursor()
tables = ['candidates','screening_questions','candidate_responses','interviews','activity_log']
for t in tables:
    try:
        c.execute(f'SELECT COUNT(*) FROM {t}')
        print(f'   {t}: {c.fetchone()[0]} rows')
    except: pass
conn.close()
"

echo ""
echo "✅ Backup complete! All files saved to:"
echo "   $BACKUP"
echo ""
echo "💡 To restore after a crash:"
echo "   cp $BACKUP/hiring.db $PORTAL/hiring.db"
echo "   cp $BACKUP/token.pkl $PORTAL/token.pkl"
echo "   cp $BACKUP/secrets.toml $PORTAL/.streamlit/secrets.toml"
