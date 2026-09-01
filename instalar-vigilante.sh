#!/usr/bin/env bash
# Instala el vigilante diario como LaunchAgent, con las rutas de ESTA máquina.
#
#   ./instalar-vigilante.sh           instala y carga
#   ./instalar-vigilante.sh quitar    descarga y borra
#
# El plist lleva rutas absolutas y no hay forma de que sean portables: por eso
# se genera aquí en vez de venir escrito en el repo.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ETIQUETA="com.publish-linkedin.vigilante"
PLIST="$HOME/Library/LaunchAgents/$ETIQUETA.plist"
DATOS="${PUBLISH_LINKEDIN_HOME:-$HOME/.config/publish-linkedin}"

if [ "${1:-}" = "quitar" ]; then
  launchctl unload "$PLIST" 2>/dev/null || true
  rm -f "$PLIST"
  echo "✓ Vigilante desinstalado"
  exit 0
fi

[ "$(uname)" = "Darwin" ] || { echo "✗ LaunchAgent es solo de macOS."; \
  echo "  En Linux usa cron:  15 9 * * *  $REPO/vigilante.sh"; exit 1; }

mkdir -p "$HOME/Library/LaunchAgents" "$DATOS"
cat > "$PLIST" <<XML
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$ETIQUETA</string>
  <key>ProgramArguments</key>
  <array><string>$REPO/vigilante.sh</string></array>
  <key>StartCalendarInterval</key>
  <dict><key>Hour</key><integer>9</integer><key>Minute</key><integer>15</integer></dict>
  <key>StandardOutPath</key><string>$DATOS/vigilante.out</string>
  <key>StandardErrorPath</key><string>$DATOS/vigilante.err</string>
</dict>
</plist>
XML

launchctl unload "$PLIST" 2>/dev/null || true
launchctl load "$PLIST"
echo "✓ Vigilante instalado — corre todos los días a las 9:15"
echo "  Repo:  $REPO"
echo "  Log:   $DATOS/vigilante.log"
echo "  Quitar: $0 quitar"
