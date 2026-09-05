#!/usr/bin/env bash
#
# Qji Peak Monitor — update checker
#
# Compares the VERSION file on GitHub with the locally installed version,
# and if a newer one is available, downloads it and re-runs install.sh
# after confirmation.
#
# GitHub上の VERSION ファイルと、ローカルにインストール済みのバージョンを
# 比較し、新しいバージョンがあれば確認のうえダウンロード → install.sh を
# 再実行します。
#
set -euo pipefail

APP_NAME="qji-peak-monitor"
APP_DISPLAY_NAME="Qji Peak Monitor"
INSTALL_DIR="${HOME}/.local/share/${APP_NAME}"

# ── Update source repository / アップデート元リポジトリ ──
REPO_OWNER="yasuhito3"
REPO_NAME="Qji-peak-monitor"
REPO_BRANCH="main"
RAW_VERSION_URL="https://raw.githubusercontent.com/${REPO_OWNER}/${REPO_NAME}/${REPO_BRANCH}/VERSION"
ZIP_URL="https://github.com/${REPO_OWNER}/${REPO_NAME}/archive/refs/heads/${REPO_BRANCH}.zip"

TMP_DIR=""
_cleanup_and_pause() {
    if [ -n "${TMP_DIR}" ] && [ -d "${TMP_DIR}" ]; then
        rm -rf "${TMP_DIR}"
    fi
    # Only pause when update.sh itself was launched directly (e.g. by
    # double-click). When install.sh is invoked from here, install.sh
    # pauses on its own, so we don't want to pause twice.
    # update.sh 自身が直接ダブルクリック等で起動された場合のみ一時停止する
    # (install.sh から呼ばれる側では、install.sh 自身が最後に一時停止するため
    #  ここでは重ねて止めない)
    if [ "${QJI_SKIP_PAUSE:-0}" != "1" ]; then
        echo
        read -r -p "Press Enter to close this window... / Enterキーを押すとこのウィンドウを閉じます… " _dummy || true
    fi
}
trap _cleanup_and_pause EXIT

echo "=============================================="
echo " ${APP_DISPLAY_NAME} Update Check / アップデート確認"
echo "=============================================="
echo

# ── 1. Check the local version / ローカルのバージョンを確認 ──
LOCAL_VERSION="unknown"
if [ -f "${INSTALL_DIR}/VERSION" ]; then
    LOCAL_VERSION="$(tr -d '[:space:]' < "${INSTALL_DIR}/VERSION")"
fi
echo "Current version / 現在のバージョン: ${LOCAL_VERSION}"

# ── 2. Check for curl / wget ─────────────────────────────
if command -v curl >/dev/null 2>&1; then
    _fetch() { curl -fsSL "$1"; }
elif command -v wget >/dev/null 2>&1; then
    _fetch() { wget -qO- "$1"; }
else
    echo "✗ Neither curl nor wget was found."
    echo "  Install one, then try again: sudo apt install curl"
    echo "✗ curl または wget が見つかりません。"
    echo "  以下でインストールしてから再試行してください: sudo apt install curl"
    exit 1
fi

# ── 3. Get the latest version from GitHub / GitHub上の最新バージョンを取得 ──
echo "Checking the latest version on GitHub... / GitHubで最新バージョンを確認しています…"
REMOTE_VERSION="$(_fetch "${RAW_VERSION_URL}" 2>/dev/null | tr -d '[:space:]' || true)"
if [ -z "${REMOTE_VERSION}" ]; then
    echo "✗ Could not fetch the latest version info. Check your internet connection."
    echo "✗ 最新バージョン情報の取得に失敗しました。インターネット接続を確認してください。"
    exit 1
fi
echo "Latest version on GitHub / GitHub上の最新バージョン: ${REMOTE_VERSION}"
echo

# ── 4. Compare versions (simple semantic-version compare) ──
# ── バージョン比較(簡易セマンティックバージョニング) ──
# Returns 0 (true) if arg1 > arg2, 1 otherwise.
# 戻り値 0 : 第1引数 > 第2引数 / 戻り値 1 : それ以外
_version_gt() {
    [ "$1" = "$2" ] && return 1
    local IFS=.
    local -a ver1 ver2
    read -r -a ver1 <<< "$1"
    read -r -a ver2 <<< "$2"
    local len=${#ver1[@]}
    [ "${#ver2[@]}" -gt "${len}" ] && len=${#ver2[@]}
    local i a b
    for ((i = 0; i < len; i++)); do
        a="${ver1[i]:-0}"
        b="${ver2[i]:-0}"
        if ((10#${a} > 10#${b})); then return 0; fi
        if ((10#${a} < 10#${b})); then return 1; fi
    done
    return 1
}

if [ "${LOCAL_VERSION}" != "unknown" ] && ! _version_gt "${REMOTE_VERSION}" "${LOCAL_VERSION}"; then
    echo "✓ You're already up to date. No update needed."
    echo "✓ すでに最新バージョンです。アップデートの必要はありません。"
    exit 0
fi

if [ "${LOCAL_VERSION}" = "unknown" ]; then
    echo "Qji Peak Monitor doesn't appear to be installed, or its version"
    echo "couldn't be determined."
    echo "現在インストールされていないか、バージョン情報が確認できませんでした。"
    read -r -p "Install the latest version (${REMOTE_VERSION})? / 最新版(${REMOTE_VERSION})をインストールしますか？ [y/N]: " ANSWER
else
    echo "🆕 A newer version is available (current: ${LOCAL_VERSION} → latest: ${REMOTE_VERSION})."
    echo "🆕 新しいバージョンがあります(現在: ${LOCAL_VERSION} → 最新: ${REMOTE_VERSION})。"
    read -r -p "Update now? / アップデートしますか？ [y/N]: " ANSWER
fi
case "${ANSWER}" in
    [yY]|[yY][eE][sS]) ;;
    *) echo "Cancelled. / 中止しました。"; exit 0 ;;
esac
echo

# ── 5. Check for unzip / unzip の確認 ────────────────────
if ! command -v unzip >/dev/null 2>&1; then
    echo "✗ unzip was not found."
    echo "  Install it, then try again: sudo apt install unzip"
    echo "✗ unzip が見つかりません。"
    echo "  以下でインストールしてから再試行してください: sudo apt install unzip"
    exit 1
fi

# ── 6. Download and extract the latest version ──
# ── 最新版をダウンロード・展開 ────────────────────────
echo "Downloading the latest version... / 最新版をダウンロードしています…"
TMP_DIR="$(mktemp -d)"
if ! _fetch "${ZIP_URL}" > "${TMP_DIR}/update.zip"; then
    echo "✗ Download failed. Check your internet connection."
    echo "✗ ダウンロードに失敗しました。インターネット接続を確認してください。"
    exit 1
fi

echo "Extracting... / 展開しています…"
unzip -q "${TMP_DIR}/update.zip" -d "${TMP_DIR}"

EXTRACTED_DIR="$(find "${TMP_DIR}" -mindepth 1 -maxdepth 1 -type d | head -n 1)"
if [ -z "${EXTRACTED_DIR}" ] || [ ! -f "${EXTRACTED_DIR}/install.sh" ]; then
    echo "✗ Couldn't find install.sh in the extracted files."
    echo "✗ 展開したファイルの中に install.sh が見つかりませんでした。"
    exit 1
fi
echo "  ✓ Done / 展開完了"
echo

# ── 7. Re-run install.sh (tell it to skip its own pause) ──
# ── install.sh を再実行(自身の一時停止はスキップさせる) ──
echo "Running the installer... / インストーラーを実行しています…"
echo "----------------------------------------------"
QJI_SKIP_PAUSE=1 bash "${EXTRACTED_DIR}/install.sh"
echo "----------------------------------------------"
echo

echo "=============================================="
echo " Update complete! / アップデート完了！ (${LOCAL_VERSION} → ${REMOTE_VERSION})"
echo "=============================================="
