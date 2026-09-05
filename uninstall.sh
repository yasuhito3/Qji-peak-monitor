#!/usr/bin/env bash
#
# Qji Peak Monitor — uninstaller
#
# install.sh が作成したファイル(本体・ランチャー・デスクトップエントリ・
# デスクトップショートカット)を削除します。
#
set -euo pipefail

_pause_before_exit() {
    echo
    read -r -p "Enterキーを押すとこのウィンドウを閉じます… " _dummy || true
}
trap _pause_before_exit EXIT

APP_NAME="qji-peak-monitor"
INSTALL_DIR="${HOME}/.local/share/${APP_NAME}"
BIN_DIR="${HOME}/.local/bin"
LAUNCHER="${BIN_DIR}/${APP_NAME}"
UPDATE_LAUNCHER="${BIN_DIR}/${APP_NAME}-update"
DESKTOP_FILE_DIR="${HOME}/.local/share/applications"
DESKTOP_ENTRY="${DESKTOP_FILE_DIR}/${APP_NAME}.desktop"
UPDATE_DESKTOP_ENTRY="${DESKTOP_FILE_DIR}/${APP_NAME}-update.desktop"

echo "=============================================="
echo " Qji Peak Monitor アンインストーラー"
echo "=============================================="
echo

read -r -p "本当にアンインストールしますか？ [y/N]: " CONFIRM
case "${CONFIRM}" in
    [yY]|[yY][eE][sS]) ;;
    *) echo "中止しました。"; exit 0 ;;
esac
echo

if [ -d "${INSTALL_DIR}" ]; then
    rm -rf "${INSTALL_DIR}"
    echo "  ✓ ${INSTALL_DIR} を削除しました"
fi

if [ -f "${LAUNCHER}" ]; then
    rm -f "${LAUNCHER}"
    echo "  ✓ ${LAUNCHER} を削除しました"
fi

if [ -f "${UPDATE_LAUNCHER}" ]; then
    rm -f "${UPDATE_LAUNCHER}"
    echo "  ✓ ${UPDATE_LAUNCHER} を削除しました"
fi

if [ -f "${DESKTOP_ENTRY}" ]; then
    rm -f "${DESKTOP_ENTRY}"
    echo "  ✓ ${DESKTOP_ENTRY} を削除しました"
fi

if [ -f "${UPDATE_DESKTOP_ENTRY}" ]; then
    rm -f "${UPDATE_DESKTOP_ENTRY}"
    echo "  ✓ ${UPDATE_DESKTOP_ENTRY} を削除しました"
fi

# デスクトップ上のショートカットも探して削除
for DESKTOP_DIR in "${XDG_DESKTOP_DIR:-}" "${HOME}/Desktop" "${HOME}/デスクトップ"; do
    if [ -n "${DESKTOP_DIR}" ] && [ -f "${DESKTOP_DIR}/${APP_NAME}.desktop" ]; then
        rm -f "${DESKTOP_DIR}/${APP_NAME}.desktop"
        echo "  ✓ ${DESKTOP_DIR}/${APP_NAME}.desktop を削除しました"
    fi
done

echo
echo "アンインストールが完了しました。"
