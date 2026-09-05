# Qji Peak Monitor

**[English](README.md) | 日本語**

Qji（奏在）の最終出力段をリアルタイムに可視化する、スタンドアロンのオーディオ
ピークメーターです。`ffmpeg`の`astats`フィルターが書き出すログを読み取り、
アナログVUメーター風のステレオ針メーター・水平レベルバー・信号履歴グラフを
表示します。

![screenshot placeholder](assets/icon_256.png)

## 特徴

- ステレオ針メーター(L/R)＋水平ピークレベルメーター
- 直近の信号推移を表示する SIGNAL PROFILE グラフ
- しきい値超えを検知する PEAK HIT カウンター
- DSP再生時など、実際に音が聞こえるタイミングと表示のズレを補正する
  **ディスプレイディレイ機能**
  - 起動時に`--display-delay`で秒数指定
  - 起動後も矢印キーでリアルタイム微調整(← → で0.1秒刻み、↑ ↓ で0.5秒刻み)
  - 数字キーで直接入力してEnterで確定も可能(例: `9` → `.` → `5` → Enter)
  - `r`キーで起動時の値にリセット
- 常に最前面表示、初期ウィンドウサイズのカスタマイズに対応

## 動作環境

- Linux(Xubuntu / Ubuntu等、X11環境を想定)
- Python 3
- `python3-tk`
- `matplotlib`
- `numpy`
- `ffmpeg`(Qji本体側で`astats`ログを出力していること)

## インストール

### 方法A: ダブルクリックでインストール(ターミナル操作不要)

1. このリポジトリをZIPでダウンロード(または`git clone`)して展開する
2. 展開したフォルダの中にある **「Qji Peak Monitor をインストール」**(`INSTALL.desktop`)を
   ダブルクリックする
3. 初回は「信頼して起動しますか?」といった確認ダイアログが出ることがあるので、
   「起動する / Trust and Launch」を選ぶ
4. ターミナルが開いてインストールが進み、完了すると「Enterキーを押すと閉じます…」と
   表示されるので、Enterキーを押して閉じる

これでアプリケーションメニューとデスクトップに「Qji Peak Monitor」のアイコンが
追加され、以後はそのアイコンをダブルクリックするだけで起動できます。

> ダブルクリックしても何も起こらない、または「開くアプリケーションの選択」と
> 聞かれてしまう場合は、方法Bのターミナルからのインストールをお試しください。
> (ファイルマネージャーの設定によっては、`.desktop`ファイルの実行が既定で
> 許可されていないことがあります)

### 方法B: ターミナルからインストール

```bash
git clone https://github.com/<your-username>/qji-peak-monitor.git
cd qji-peak-monitor
bash install.sh
```

> `./install.sh`ではなく`bash install.sh`のように実行すると、実行権限(実行属性)が
> 失われていても(例: GitHubの「Download ZIP」でダウンロードした場合や、
> GitHubのWeb画面上でファイルを移動した場合など)、そのまま動かせます。
> `chmod`も`sudo`も不要です。

どちらの方法でも、`install.sh`は以下を行います:

- 依存パッケージ(`python3-tk` / `matplotlib` / `numpy`)の有無を確認
- 本体一式を `~/.local/share/qji-peak-monitor/` に配置
- 起動用ランチャーを `~/.local/bin/qji-peak-monitor` に作成
- アプリケーションメニューへの登録(`~/.local/share/applications/`)
- デスクトップへのショートカット作成

いずれもユーザーのホームディレクトリ配下への配置のみのため、`sudo`は不要です
(依存パッケージが不足している場合のみ、インストールコマンドの案内が表示されます)。

### アンインストール

```bash
bash uninstall.sh
```

> `INSTALL.desktop`をダブルクリックしても反応しない場合も、たいてい同じ
> 実行権限の問題です。ターミナルから`bash install.sh`を試してみてください。
> (実行権限そのものを直したい場合は
> `chmod +x install.sh uninstall.sh INSTALL.desktop`でも直せます。
> こちらはsudoは不要です — もしsudoを付けて実行された場合、作成される
> ファイルの所有者がrootになってしまうことがあるのでご注意ください。)

## アップデート

一度インストールすれば、以後は毎回ZIPを再ダウンロードしたり`git clone`し直したり
する必要はありません。インストール時に、アプリケーションメニューへ自動的に
「アップデート確認」の項目が追加されます。

- **アプリケーションメニューから**:「Qji Peak Monitor アップデート確認」
- **ターミナルから**: `qji-peak-monitor-update`(または`~/.local/bin/qji-peak-monitor-update`)

このリポジトリの`VERSION`ファイルを確認し、新しいバージョンがあれば確認のうえ
自動的にダウンロード・再インストールします(最新のファイルで`install.sh`を
実行し直すのと同じことが行われます)。すでに最新版の場合は、その旨を表示して
終了します。

## 言語について / Language

インストーラー・アンインストーラー・アップデーターは、すべてのメッセージを
英語・日本語の両方で表示するため、使用言語の設定に関わらず同じ内容が読めます。
アプリケーションメニューの項目(アプリ本体、および「アップデート確認」)は、
お使いのデスクトップの言語設定に応じて自動的に英語/日本語が切り替わります。

The installer, uninstaller, and updater print every message in both English
and Japanese, so they work the same way regardless of your system language.
Application-menu entries (the app icon and the "Check for Updates" icon)
switch automatically between English and Japanese based on your desktop's
language setting.

## 使い方

デスクトップアイコン、またはアプリケーションメニューから起動できます。

ターミナルから起動する場合:

```bash
qji-peak-monitor [オプション]
```

### 主なオプション

| オプション | 説明 | デフォルト |
|---|---|---|
| `--log-glob` | 監視するastatsログファイルのglobパターン | (スクリプト内既定値) |
| `--threshold` | ピークヒット判定のしきい値(dBFS) | (スクリプト内既定値) |
| `--window` | SIGNAL PROFILEグラフの表示秒数 | 20.0 |
| `--floor` | メーターの下限(dBFS) | (スクリプト内既定値) |
| `--width-scale` | 初期ウィンドウ横幅の倍率 | 0.5 |
| `--height-scale` | 初期ウィンドウ高さの倍率 | 1.0 |
| `--no-topmost` | 常に最前面表示を無効化 | (最前面表示が既定) |
| `--display-delay` | 表示を遅らせる秒数(実際に聞こえるタイミングに合わせる) | 0.0 |
| `--refresh-ms` | 画面更新間隔(ミリ秒) | 100 |

例(DSP再生時、2.5秒遅らせて起動):

```bash
qji-peak-monitor --display-delay 2.5
```

### キーボード操作(起動後)

| キー | 動作 |
|---|---|
| `0`〜`9`、`.` | ディスプレイディレイの数値直接入力モードを開始 |
| `Enter` | 入力した数値を確定 |
| `Backspace` | 入力中の一文字を削除 |
| `Esc` | 入力をキャンセル |
| `←` / `→` | ディスプレイディレイを0.1秒刻みで調整 |
| `↑` / `↓` | ディスプレイディレイを0.5秒刻みで調整 |
| `r` | ディスプレイディレイを起動時の値にリセット |

## 仕組み

`astats`フィルターはffmpegのフィルターチェーンの最終段(音声を次段へ渡す直前)
で計測しているため、SIGNAL PROFILEグラフの右端は「ffmpegが処理を終えて次段
(ALSA出力やDSPループバック)へ渡した瞬間」を表します。実際にスピーカーで
聞こえるまでには、ALSAバッファやDSPのキューといった下流の遅延が加わるため、
`--display-delay`でその分を補正して表示できます。

## ライセンス

MIT — [LICENSE](./LICENSE) を参照してください。
