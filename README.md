# 猜手機號碼 Discord Bot + 遊戲系統

簡介：一個多功能 Discord Bot，包含手機號碼猜測遊戲、種族系統、費波那契數列遊戲與金幣系統。

---

## 快速上手

### 1. 安裝相依

```bash
python -m pip install -r requirements.txt
```

### 2. 設定 Bot Token

Windows PowerShell：

```powershell
$env:DISCORD_TOKEN = "你的_bot_token"
python GuessPhoneNumber.py
```

或直接執行時手動輸入 token：

```powershell
python GuessPhoneNumber.py
```

---

## 主要指令

### 手機號碼猜測遊戲

- `/create_account <username> <phonenumber>`
  - 建立遊戲帳號（phone 必須以 09 開頭且共 10 碼；username 不可重複）
  - 一個 Discord 帳號可建立多個遊戲帳號

- `/guess <username> <phonenumber>`
  - 猜測指定 username 的手機號碼
  - 系統回傳與答案不同的位數
  - 每人每小時限 8 次，超過限制會被阻止
  - 已經正確猜過的玩家無法再猜同一個帳號
  - 每次猜測後顯示**剩餘次數**

- `/stats <username>`
  - 顯示該 username 的手機號碼已被正確猜到幾次

- `/accounts [user]`
  - 查看指定 Discord 用戶建立的所有遊戲帳號
  - 不指定用戶則查看自己的帳號

### 種族與檔案系統

- `/profile [user]`
  - 查看指定用戶的種族、金幣數與每個遊戲的遊玩次數
  - 預設查看自己的檔案
  - 種族每天 00:00 隨機更新一次：**主人**、**寧寧**、**阿尼的哥哥**

- `/coins [user]`
  - 查看指定用戶的金幣數量
  - 預設查看自己的

### 遊戲 1：費波那契數列

- `/game1`
  - **遊戲規則**：
    - 系統隨機選 0~9999 的整數當起點
    - 玩家需連續輸入 20 個數字（第 1 項到第 20 項）
    - 每一項的期望值 = 上一項的結果 + 該項的費波那契數
    - 輸入框只讀一個數字，輸入完後清空
    - 畫面實時顯示：起點、當前步驟（i）與該步費波那契數
    - 任何錯誤立即失敗，遊戲終止
    - 全部正確才算成功

  - **遊玩限制**（每日 00:00 重新計算）：
    - 主人：40% 機率玩 2 次、60% 玩 1 次
    - 寧寧：20% 玩 2 次、20% 玩 0 次、60% 玩 1 次
    - 阿尼的哥哥：30% 玩 0 次、70% 玩 1 次

  - **獎勵**：
    - 成功：20 金幣 × 種族倍率
      - 主人：×1.5（30 金幣）
      - 寧寧：×1（20 金幣）
      - 阿尼的哥哥：×0.5（10 金幣）
    - 失敗：0 金幣
    - 小數部分無條件捨去

---

## 資料儲存

所有資料存於同目錄的 `guess_data.json`。

---

## 種族系統說明

每個 Discord 帳號每天 00:00 會自動分配一個種族，不同種族會影響：
1. **每日遊玩次數上限**（不同遊戲各自計算）
2. **金幣獲得倍率**

---

## Discord Bot 設定

1. 前往 [Discord Developer Portal](https://discord.com/developers/applications)
2. 建立新 Application，並新增 Bot
3. 複製 Bot Token（保持機密）
4. 設定 Bot 權限：
   - 邀請連結範例（把 `CLIENT_ID` 換成你的 ID）：
   ```
   https://discord.com/oauth2/authorize?client_id=CLIENT_ID&scope=bot%20applications.commands&permissions=3072
   ```
5. 邀請 Bot 加入伺服器

---

## 使用指令例

1. 建立帳號：`/create_account test1 0912345678`
2. 猜測：`/guess test1 0912345670`
3. 查看統計：`/stats test1`
4. 查看自己的種族：`/profile`
5. 查看他人帳號：`/accounts @某用戶`
6. 玩費波那契遊戲：`/game1`

