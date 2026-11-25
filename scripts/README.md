# scripts

## build_dmg.sh：打包 macOS DMG

把 Python 後端（PyInstaller）和 Tauri 外殼打包成 `.app` 和 `.dmg`，並做 ad-hoc 簽章（未公證）。

### 需要先安裝

| 工具 | 版本要求 | 確認指令 |
|---|---|---|
| Xcode 或 Xcode Command Line Tools | — | `xcode-select -p` |
| **Python** | **3.10 – 3.14**（建議 3.13） | `python3 --version` |
| Node.js | 18 以上，建議用 LTS | `node --version` |
| Rust（rustup 或 Homebrew） | — | `cargo --version` |

Python 的版本範圍來自 `requirements.txt` 裡的套件：

- `starlette==0.50.0` 需要 **≥ 3.10**，所以 macOS 內建的 3.9 不能用。
- `pyinstaller==6.20.0` 只支援 **< 3.15**，所以 3.15 以上也不能用。

### 執行

在 repo 根目錄執行。如果你的預設 `python3` 版本不在 3.10 到 3.14 之間，用 `PYTHON_BIN` 指定另一個 Python 的**完整路徑**。

#### 用 pyenv 的 Python

```bash
pyenv install 3.13          # 已經裝過可略過
rm -rf .venv-build          # 換 Python 版本時要先刪掉舊環境
PYTHON_BIN="$(pyenv prefix 3.13)/bin/python3" ./scripts/build_dmg.sh 2>&1 | tee build.log
# Dipeko: /Users/agent/.pyenv/versions/3.13.18
```

路徑要寫到實際的執行檔，例如 `~/.pyenv/versions/3.13.x/bin/python3`。不要寫 `~/.pyenv/shims/python3`，shim 會依照 pyenv 的全域設定挑版本，可能抓到別的版本。

#### 用 python.org 安裝檔的 Python（正式發佈建議用這個）

```bash
rm -rf .venv-build
PYTHON_BIN=/Library/Frameworks/Python.framework/Versions/3.13/bin/python3 ./scripts/build_dmg.sh 2>&1 | tee build.log
```

#### 預設的 python3 版本已經符合要求

```bash
./scripts/build_dmg.sh 2>&1 | tee build.log
```

`PYTHON_BIN=...` 寫在指令前面，只對這一次執行有效。腳本、pyenv 設定和 shell 環境都不會被改到。

腳本開頭會印出 `Python  : Python 3.13.x at ...`，可以從這裡確認用的是哪一個 Python。

`2>&1 | tee build.log` 會把所有輸出同時顯示在畫面上並存進 `build.log`，出錯時把這個檔案提供出來即可。

### 產出

```
Alfred/src-tauri/target/release/bundle/macos/loki-alfred.app
Alfred/src-tauri/target/release/bundle/dmg/*.dmg
```

**舊的 DMG 不會被自動清掉。** DMG 檔名裡有版本號（例如 `loki-alfred_0.1.0_aarch64.dmg`）。版本號沒變時，新檔會直接覆蓋舊檔；改過版本號的話，`bundle/dmg/` 裡會同時留著新舊兩個。腳本結尾印出的 `DMG :` 只會挑其中一個，不一定是最新的。改版本號後，建置前先清掉舊的：

```bash
rm -rf Alfred/src-tauri/target/release/bundle/dmg
```

### 注意事項

- **`.venv-build` 會被沿用**：腳本發現 `.venv-build` 已經存在時，會直接沿用，不會改用新指定的 `PYTHON_BIN`。換 Python 版本前要先執行 `rm -rf .venv-build`。
- **8001 埠不能被占用**：腳本會啟動打包好的後端做冒煙測試。執行前請參考下方「[確認 8001 埠沒有被占用](#確認-8001-埠沒有被占用)」。
- **Finder 排版預設跳過**：腳本預設用 `CI=true` 建置，會跳過用 AppleScript 控制 Finder 排列 DMG 視窗的步驟，不需要 Finder 權限，遠端也能跑。DMG 內容（`.app` 和 Applications 捷徑）不受影響，只是打開時沒有排好的版面。想要排好的版面，先在本機允許 Terminal 控制 Finder（系統設定 → 隱私權與安全性 → 自動化），再執行 `CI=false ./scripts/build_dmg.sh`。
- **Python 的來源會影響相容性**：pyenv 和 Homebrew 的 Python 是在本機編譯的，打出來的 App 可能只能在相同或更新版本的 macOS 上執行。自己測試沒問題，正式發佈請改用 python.org 的版本。
- **只支援 Apple Silicon（arm64）**：產出的 App 只能在 Apple Silicon Mac 上執行，不支援 Intel Mac。腳本一開始會檢查三件事，任何一項不是 arm64 就會停止：
  - Mac 本身（`uname -m`）。在 Rosetta 模式的 Terminal 裡也會顯示 x86_64，所以同樣會被擋下。
  - `PYTHON_BIN` 指定的 Python。`/usr/local` 底下的 Intel 版 Homebrew Python 不能用。
  - Rust 工具鏈（必須是 `aarch64-apple-darwin`）。

### 確認 8001 埠沒有被占用

腳本會用下面這行指令檢查 8001 埠，被占用時會直接停止。跑腳本前可以自己先查一次：

```bash
lsof -iTCP:8001 -sTCP:LISTEN
```

- **沒有任何輸出**：埠沒有被占用，可以直接跑腳本。
- **有輸出**：輸出會像這樣：
  ```
  COMMAND   PID   USER  ...  NAME
  backend  12345  you   ...  localhost:8001 (LISTEN)
  ```
  看 `COMMAND` 欄是哪個程式。通常是還開著的 Alfred App，或是手動執行的 `backend.py`、`app.py`。

關掉占用的程式：

1. 如果是 Alfred App，從選單列或 Dock 結束它。
2. 其他程式用查到的 PID 結束：
   ```bash
   kill 12345
   ```
   `kill` 之後還在的話，可以用 `kill -9 12345` 強制結束。執行前先確認 `COMMAND` 是你認得的程式，避免誤殺其他服務。
3. 再執行一次 `lsof -iTCP:8001 -sTCP:LISTEN`。沒有輸出，就表示已經沒有程式占用了。

### 測試 DMG

1. 打開 DMG，把 App 拖進 Applications。
2. 第一次開啟時，因為沒有公證，Gatekeeper 會阻擋。在 App 上按右鍵選「打開」，或執行：
   ```bash
   xattr -dr com.apple.quarantine /Applications/loki-alfred.app
   ```
3. 確認 App 能啟動，畫面能連上後端。
4. 要測試搜尋和 AI 功能的話，需要另外安裝 **Recoll** 和 **Ollama**（加上至少一個模型）。DMG 裡沒有包含這兩個。
