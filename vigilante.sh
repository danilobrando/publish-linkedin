#!/usr/bin/env bash
# Vigilante de publish-linkedin.
#
# Corre el doctor una vez al día. Si algo está mal —o el token está por
# vencerse— avisa por notificación de macOS y deja constancia.
#
# Existe porque este conector no tiene refresh_token: el token muere a los ~60
# días y LinkedIn no avisa. Sin esto, te enteras el día que necesitas publicar.
set -uo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY="$REPO/.venv/bin/python"
LOG="${PUBLISH_LINKEDIN_HOME:-$HOME/.config/publish-linkedin}/vigilante.log"
mkdir -p "$(dirname "$LOG")"

salida="$("$PY" "$REPO/doctor.py" --quiet 2>&1)"
codigo=$?
marca="$(date '+%Y-%m-%dT%H:%M:%S')"
echo "$marca	$salida" >> "$LOG"

if [ "$codigo" -eq 0 ]; then
  exit 0
fi

# Intento de auto-reparación antes de molestar a nadie.
"$PY" "$REPO/doctor.py" fix --quiet >> "$LOG" 2>&1
salida="$("$PY" "$REPO/doctor.py" --quiet 2>&1)"
codigo=$?
echo "$marca	tras-fix	$salida" >> "$LOG"
[ "$codigo" -eq 0 ] && exit 0

detalle="$("$PY" "$REPO/doctor.py" 2>&1 | grep -E '^\s+[!✗]' | head -3)"
osascript -e "display notification \"$(echo "$detalle" | head -1 | tr -d '"')\" with title \"publish-linkedin necesita atención\"" 2>/dev/null || true
echo "$marca	AVISADO	$detalle" >> "$LOG"
exit "$codigo"
