#!/usr/bin/env bash
#
# Qji Peak Monitor — installer
#
# 実行ファイル一式を ~/.local/share/qji-peak-monitor/ に配置し、
# ランチャースクリプトを ~/.local/bin/ に、
# デスクトップエントリを ~/.local/share/applications/ と ~/デスクトップ に
# 作成します。システム全体(/opt や /usr/share)には触れないため、
# sudo は不要です。
#
set -euo pipefail

# ダブルクリック(Terminal=true の .desktop 経由)で起動された場合、
# 処理が終わった瞬間にターミナルウィンドウが閉じてしまうと、成功しても
# 失敗してもメッセージを読めないまま消えてしまう。正常終了・異常終了の
# どちらでも、必ず Enter キー待ちで一時停止してから閉じるようにする。
_pause_before_exit() {
    # update.sh から呼び出された場合は、update.sh 側で最後に一時停止するため
    # ここでは重ねて止めない。
    if [ "${QJI_SKIP_PAUSE:-0}" = "1" ]; then
        return
    fi
    echo
    read -r -p "Enterキーを押すとこのウィンドウを閉じます… " _dummy || true
}
trap _pause_before_exit EXIT

# ── パス設定 ─────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_NAME="qji-peak-monitor"
APP_DISPLAY_NAME="Qji Peak Monitor"
INSTALL_DIR="${HOME}/.local/share/${APP_NAME}"
BIN_DIR="${HOME}/.local/bin"
DESKTOP_FILE_DIR="${HOME}/.local/share/applications"
LAUNCHER="${BIN_DIR}/${APP_NAME}"
UPDATE_LAUNCHER="${BIN_DIR}/${APP_NAME}-update"
DESKTOP_ENTRY="${DESKTOP_FILE_DIR}/${APP_NAME}.desktop"
UPDATE_DESKTOP_ENTRY="${DESKTOP_FILE_DIR}/${APP_NAME}-update.desktop"
MAIN_SCRIPT="qji_audio_peak_monitor_qng_hayakumo_stereo.py"

echo "=============================================="
echo " ${APP_DISPLAY_NAME} インストーラー"
echo "=============================================="
echo

# ── 1. 依存関係の確認 ────────────────────────────────────
echo "[1/5] 依存関係を確認しています…"

if ! command -v python3 >/dev/null 2>&1; then
    echo "  ✗ python3 が見つかりません。先に python3 をインストールしてください。"
    exit 1
fi

MISSING_PY_MODULES=()
NUMPY_CONFLICT_DETECTED=0
for mod in tkinter matplotlib numpy; do
    # エラーメッセージ本文も見たいので、標準エラー出力を捕捉しておく。
    IMPORT_ERR=""
    if ! IMPORT_ERR="$(python3 -c "import ${mod}" 2>&1 1>/dev/null)"; then
        MISSING_PY_MODULES+=("${mod}")
        # 「pipでユーザー領域に入った新しいNumPyと、aptのmatplotlib(NumPy 1.x
        # 向けビルド)が衝突している」という、よくあるパターンのエラー文言に
        # 一致するかどうかを確認する。
        if echo "${IMPORT_ERR}" | grep -qi \
            "numpy\.core\.multiarray failed to import\|compiled using NumPy 1\.x"; then
            NUMPY_CONFLICT_DETECTED=1
        fi
    fi
done

if [ "${#MISSING_PY_MODULES[@]}" -ne 0 ]; then
    echo "  ✗ 不足しているPythonモジュールがあります: ${MISSING_PY_MODULES[*]}"
    echo

    if [ "${NUMPY_CONFLICT_DETECTED}" -eq 1 ]; then
        echo "  ⚠ NumPyのバージョン競合が検出されました。"
        echo "    以前 pip 等でユーザー領域(~/.local)に新しいバージョンのNumPyが"
        echo "    インストールされており、それが apt 由来の matplotlib(古い"
        echo "    NumPy 1.x向けにビルドされたもの)と衝突している可能性が高いです。"
        echo
        echo "    以下を試してから、もう一度このインストーラーを実行してください:"
        echo
        echo "      python3 -m pip uninstall --break-system-packages numpy"
        echo "      sudo apt install python3-numpy"
        echo
        echo "    (--break-system-packages は、システム保護機構を一時的に"
        echo "     解除するオプションです。今回は『後から個人的に追加された"
        echo "     重複パッケージを取り除く』操作なので安全です)"
        echo
    fi

    echo "  以下のコマンドでインストールしてから、再度このスクリプトを実行してください:"
    echo
    echo "    sudo apt update"
    echo "    sudo apt install python3-tk python3-matplotlib python3-numpy"
    echo
    echo "  ※ 上記を実行済みでも同じメッセージが出る場合、Anaconda/pyenv等の"
    echo "    別のPython環境が優先されている可能性があります。以下の情報を"
    echo "    参考に確認してください(python3 の場所が /usr/bin/python3 以外"
    echo "    になっている場合は、その別のPython環境が原因です):"
    echo
    echo "    which python3 → $(command -v python3)"
    echo "    python3 --version → $(python3 --version 2>&1)"
    echo "    python3 の実体 → $(python3 -c 'import sys; print(sys.executable)' 2>&1)"
    echo
    exit 1
fi
echo "  ✓ python3 / tkinter / matplotlib / numpy — OK"
echo

# ── 2. 本体ファイルの配置 ────────────────────────────────
echo "[2/5] 本体ファイルを ${INSTALL_DIR} に配置しています…"
mkdir -p "${INSTALL_DIR}/assets"
cp -f "${SCRIPT_DIR}/${MAIN_SCRIPT}" "${INSTALL_DIR}/${MAIN_SCRIPT}"
if [ -d "${SCRIPT_DIR}/assets" ]; then
    cp -f "${SCRIPT_DIR}"/assets/*.png "${INSTALL_DIR}/assets/" 2>/dev/null || true
fi
chmod +x "${INSTALL_DIR}/${MAIN_SCRIPT}"

# バージョン情報とアップデートスクリプトも一緒に配置しておく
# (update.sh が「今インストールされているバージョン」を知るために使う)
if [ -f "${SCRIPT_DIR}/VERSION" ]; then
    cp -f "${SCRIPT_DIR}/VERSION" "${INSTALL_DIR}/VERSION"
else
    echo "unknown" > "${INSTALL_DIR}/VERSION"
fi
if [ -f "${SCRIPT_DIR}/update.sh" ]; then
    cp -f "${SCRIPT_DIR}/update.sh" "${INSTALL_DIR}/update.sh"
    chmod +x "${INSTALL_DIR}/update.sh"
fi
echo "  ✓ 配置完了"
echo

# ── 3. 起動ランチャーの作成 ──────────────────────────────
echo "[3/5] 起動用ランチャーを ${LAUNCHER} に作成しています…"
mkdir -p "${BIN_DIR}"
cat > "${LAUNCHER}" << EOF
#!/usr/bin/env bash
exec python3 "${INSTALL_DIR}/${MAIN_SCRIPT}" "\$@"
EOF
chmod +x "${LAUNCHER}"
echo "  ✓ 作成完了"

if [ -f "${INSTALL_DIR}/update.sh" ]; then
    cat > "${UPDATE_LAUNCHER}" << EOF
#!/usr/bin/env bash
exec bash "${INSTALL_DIR}/update.sh"
EOF
    chmod +x "${UPDATE_LAUNCHER}"
    echo "  ✓ アップデート確認用ランチャーも作成しました (${UPDATE_LAUNCHER})"
fi

if [[ ":${PATH}:" != *":${BIN_DIR}:"* ]]; then
    echo "  ※ ${BIN_DIR} が PATH に含まれていません。"
    echo "     ターミナルから直接 '${APP_NAME}' コマンドで起動したい場合は、"
    echo "     ~/.bashrc などに以下を追加してください:"
    echo "       export PATH=\"\${HOME}/.local/bin:\${PATH}\""
fi
echo

# ── 4. デスクトップエントリ(アプリケーションメニュー)の作成 ──
echo "[4/5] デスクトップエントリを作成しています…"
mkdir -p "${DESKTOP_FILE_DIR}"
ICON_PATH="${INSTALL_DIR}/assets/icon_256.png"
cat > "${DESKTOP_ENTRY}" << EOF
[Desktop Entry]
Type=Application
Version=1.0
Name=${APP_DISPLAY_NAME}
Comment=Qji Audio Peak Monitor — Real-time Peak Level Monitor for Final Output
Comment[ja]=Qji オーディオ ピークモニター — 最終出力のリアルタイムピークレベルモニター
Exec=${LAUNCHER}
Icon=${ICON_PATH}
Terminal=false
Categories=AudioVideo;Audio;Utility;
StartupNotify=true
EOF
chmod +x "${DESKTOP_ENTRY}"
echo "  ✓ アプリケーションメニューに登録しました"

# gio があればメニュー側にも "信頼済み" として認識させる(無くても問題ない)
if command -v gio >/dev/null 2>&1; then
    gio set "${DESKTOP_ENTRY}" "metadata::trusted" true >/dev/null 2>&1 || true
fi

# アップデート確認用のメニューエントリも作成する
if [ -f "${UPDATE_LAUNCHER}" ]; then
    cat > "${UPDATE_DESKTOP_ENTRY}" << EOF
[Desktop Entry]
Type=Application
Version=1.0
Name=${APP_DISPLAY_NAME} アップデート確認
Name[en]=${APP_DISPLAY_NAME} - Check for Updates
Comment=GitHub上の最新バージョンを確認し、必要ならアップデートします
Comment[en]=Check GitHub for a newer version and update if available
Exec=${UPDATE_LAUNCHER}
Icon=system-software-update
Terminal=true
Categories=Utility;
StartupNotify=true
EOF
    chmod +x "${UPDATE_DESKTOP_ENTRY}"
    if command -v gio >/dev/null 2>&1; then
        gio set "${UPDATE_DESKTOP_ENTRY}" "metadata::trusted" true >/dev/null 2>&1 || true
    fi
    echo "  ✓ 「アップデート確認」もアプリケーションメニューに登録しました"
fi
echo

# ── 5. デスクトップへのショートカット作成 ────────────────
echo "[5/5] デスクトップへショートカットを作成しています…"
DESKTOP_DIR=""
if [ -n "${XDG_DESKTOP_DIR:-}" ]; then
    DESKTOP_DIR="${XDG_DESKTOP_DIR}"
elif command -v xdg-user-dir >/dev/null 2>&1; then
    DESKTOP_DIR="$(xdg-user-dir DESKTOP 2>/dev/null || true)"
fi
if [ -z "${DESKTOP_DIR}" ] || [ ! -d "${DESKTOP_DIR}" ]; then
    DESKTOP_DIR="${HOME}/Desktop"
fi

if [ -d "${DESKTOP_DIR}" ]; then
    DESKTOP_SHORTCUT="${DESKTOP_DIR}/${APP_NAME}.desktop"
    cp -f "${DESKTOP_ENTRY}" "${DESKTOP_SHORTCUT}"
    chmod +x "${DESKTOP_SHORTCUT}"
    if command -v gio >/dev/null 2>&1; then
        gio set "${DESKTOP_SHORTCUT}" "metadata::trusted" true >/dev/null 2>&1 || true
    fi
    echo "  ✓ ${DESKTOP_SHORTCUT} を作成しました"
    echo "    ※ Xfce/Thunar 環境では、初回はアイコンを右クリックして"
    echo "      「起動を許可する(Allow Launching)」を選ぶ必要がある場合があります。"
else
    echo "  ※ デスクトップフォルダが見つからなかったため、"
    echo "    デスクトップへのショートカット作成はスキップしました。"
    echo "    アプリケーションメニューからは起動できます。"
fi
echo

echo "=============================================="
echo " インストール完了！"
echo "=============================================="
echo
echo "起動方法:"
echo "  ・アプリケーションメニュー、またはデスクトップアイコンから起動"
echo "  ・ターミナルから: ${LAUNCHER} [オプション]"
echo
echo "例:"
echo "  ${LAUNCHER} --display-delay 2.5"
echo
if [ -f "${UPDATE_LAUNCHER}" ]; then
    echo "アップデートの確認:"
    echo "  ・アプリケーションメニューの「${APP_DISPLAY_NAME} アップデート確認」から"
    echo "  ・またはターミナルから: ${UPDATE_LAUNCHER}"
    echo
fi
echo "アンインストールする場合は uninstall.sh を実行してください。"
