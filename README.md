# project_3_parking

> **校園車輛與停車管理系統** — 資料庫課程專題

前端以 Bootstrap + Jinja2 呈現，透過 `fetch()` 呼叫 Flask 的 JSON API，所有業務資料存取集中在 SQLAlchemy / Service Layer。

## 功能

- 五個停車業務實體：CampusUser、Vehicle、ParkingPermit、ParkingArea、ParkingRecord
- 獨立 LoginAccount 表：Flask-Login Session 認證，Admin / Viewer 角色
- JSON REST API (`/api/v1`)：CRUD、車輛進場／離場、停車證付款、停車費結算
- 分析 Dashboard：停車區域、進場時段、停留時間、即時容量、停車證、已付款臨停收入

## Miniworld 範圍

1. 僅考慮汽車、機車，未考慮重機、大型車輛。
2. **車輛管理只包含曾辦理學年度停車證的校內車輛**，並須關聯一位 CampusUser；辦理首次停車證時會同步建立 Vehicle。來賓臨停不建立 Vehicle 或車主資料。
3. 一個停車區域僅供一種車型，如海堤汽車停車區、海堤機車停車區。
4. 校內使用者可登記多台車；未登記車主的車輛可臨停，不考慮現實世界可能有車輛轉讓的狀況。
5. 停車證**僅包含學年度證**：同一車輛同一學年最多一張。付費且於停車期間有效時，不另收單次停車費。
6. 無有效且已付款停車證的車輛，離場依所在區域 `hourly_rate × 向上取整停車小時數` 計費。
7. 車輛進場時，後端會自動選用當日有效且已付款的學年度證。
8. 停車紀錄對應一車、一區域；一車不能同時有兩筆未離場紀錄。
9. 不考慮臨時停車證、分期付款、退款、跨區停車、夜間／假日費率、特殊車位。
10. 登入帳號與 CampusUser **互不關聯**；前者是網站操作身分，後者是業務資料。


## 1. 本機安裝 (Python 3.12 建議)

```bash
# 下載後，進入專案
cd project_3_parking
python -m venv .venv

# macOS/Linux
source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1

pip install -r requirements-dev.txt
cp .env.example .env   # Windows 可手動複製
```

編輯 `.env`；填寫學校 PostgreSQL 的 **主機、資料庫、帳號、密碼、TLS 參數**。請勿上傳 `.env`。

```dotenv
DATABASE_URL=postgresql+psycopg://USERNAME:PASSWORD@DB_HOST:5432/DB_NAME?sslmode=require
SECRET_KEY=PASTE_A_LONG_RANDOM_VALUE
COOKIE_SECURE=0
BEHIND_PROXY=0
```

因使用Flask-Login，故需產生 Session Secret，用於保護Session Cookie：

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

如密碼含 `@ : / ? #` 等特殊字元，需先對密碼做 URL 編碼。若資料庫提供 CA 憑證，請使用正確的 TLS 驗證設定（例如 `sslmode=verify-full`）。


```bash

# 建立資料表
flask --app wsgi db upgrade
flask --app wsgi create-admin
flask --app wsgi run --debug --port 8000
```

在 `create-admin` 互動式提示輸入管理員名稱與長度至少 12 字元的密碼；不提供預設密碼。

瀏覽 [http://127.0.0.1:8000](http://127.0.0.1:8000)。

### 載入示範資料 (Optional)

僅限空白且已獲授權的**測試資料庫**，執行以下命令產生，資料包含 **49 個虛構停車區、1,500 位使用者、3,500 台車、1,200 張停車證與 30,000 筆停車紀錄（其中 450 筆尚未離場）**：

```bash
flask --app wsgi seed-demo --yes
```

`seed-demo` 若偵測到已有資料，會拒絕匯入。

資料涵蓋 **2026/05/01–2026/10/31** 的虛構歷史停車紀錄，以及執行當下的少量未離場紀錄。預設使用固定亂數種子 `20261103`，模擬開學／暑假、平假日及進場尖峰差異；資料產生器會防止同車停車時間重疊、車種與停車區不符、停車場容量超額，以及使用無效停車證。不同環境執行的「進行中」紀錄時間會依實際執行時間調整。

若希望連進行中紀錄的時間都完全相同，可明確指定快照時間：

```bash
flask --app wsgi seed-demo --yes --records 30000 --active 450 --seed 20261103 --as-of '2026-11-03T18:00:00+08:00'
```

`--records` 是包含進行中紀錄的總筆數。初始匯入使用每 1,000 筆 flush、最後一次 commit；若中途失敗會 rollback，請勿在既有資料庫上重複執行。

### 離線產生 CSV（不連接資料庫）

若想先檢查 30,000 筆資料，可直接使用純 Python 產生五份 CSV：

```bash
python scripts/export_demo_csv.py --output demo_data_30000
python scripts/validate_demo_data.py
```

產出的五份 CSV 包括 `campus_user.csv`、`vehicle.csv`、`parking_area.csv`、`parking_permit.csv` 與 `parking_record.csv`，另附 `summary.json`。**CSV 的 `id` 與 `*_ref` 是離線資料的相互參照鍵；直接用 SQL COPY 匯入含 identity 欄位的正式 Schema 時還需處理主鍵序列與 FK 匯入順序，因此建議優先使用 `seed-demo` 完成資料庫匯入。**

所有停車區名稱、費率與紀錄都是虛構資料。49 個停車區按車種分為汽車 28 個、機車 21 個；總容量依先前討論設定為汽車 870 位、機車 6,306 位，但每區容量與名稱為示範分配，**不是官方停車區清冊**。

## 2. Render 免費雲端部署

1. 將此目錄上傳到自己的 GitHub Repository；再次確認 `.env` 已被 `.gitignore` 排除。
2. 在 Render 建立 **Blueprint**，選擇 Repository 的 `render.yaml`。如果你的帳號支援 Free Web Service，選用免費方案。Render 的免費服務可能閒置休眠／冷啟動，也可能隨方案政策調整。
3. 在 Render 設定 `DATABASE_URL`（指向學校 PostgreSQL），`SECRET_KEY` 由 Blueprint 隨機產生；`COOKIE_SECURE=1`、`BEHIND_PROXY=1` 已設定。
4. **部署前**先用本機指向同一個有權限的 PostgreSQL Schema 執行 `flask --app wsgi db upgrade`，確保六張資料表存在；建立第一個管理員帳號。
5. Render 在 `https://<service-name>.onrender.com/login` 提供 HTTPS 登入網址。

> 本專案預設 **不在雲端每次啟動時執行 Migration**，避免服務休眠喚醒或重新部署時未經確認就變更學校資料庫。未來 Schema 升級，請先備份並手動執行 `flask db upgrade`。



## 3. REST API

全部 API 前綴：`/api/v1`。除登入外均需 Session 登入；資料修改及帳號管理只允許 ADMIN。詳見 [`docs/API.md`](docs/API.md)。

| 功能 | API |
|---|---|
| 登入 / 登出 | `POST /auth/login`，`POST /auth/logout` |
| 目前帳號 | `GET /auth/me` |
| 帳號管理 | `GET/POST /accounts`、`GET/PATCH /accounts/{id}` |
| 業務 CRUD | `/campus-users`、`/vehicles`、`/parking-permits`、`/parking-areas` |
| 停車紀錄 | `/parking-records`、`/{id}/exit`、`/{id}/pay` |
| 停車證付款 | `/parking-permits/{id}/pay` |
| 分析 | `/analytics/overview`、`by-area`、`by-hour`、`duration`、`occupancy`、`permits`、`revenue` |

API 回傳 `{"data":...}`，列表回傳 `pagination`；錯誤回傳 `{"error":{"code":...,"message":...}}`。列表查詢預設 20 筆，每頁最多 100 筆。

**安全性：** 使用同源 Session Cookie，不使用 JWT；所有狀態變更 API（含登入）必須帶 `X-CSRFToken`，取自網頁中的 `<meta name="csrf-token">`；網站已由 `api.js` 自動處理。管理員角色在後端檢查，前端隱藏按鈕只是便利性，不是權限措施。請勿把帳號密碼寫進 JS/HTML。公開展示時建議建立唯讀 Viewer 帳號。正式上線前建議再加入登入嘗試限制、監控與備份。

## 4. 測試

測試環境強制使用獨立 SQLite 暫存檔，**不會連到學校 PostgreSQL**：

```bash
pytest -q
```

`tests/test_auth.py`、`tests/test_parking.py` 驗證 Flask 主要流程；`tests/test_static_structure.py` 驗證必要檔案與模型；PostgreSQL 特有的 Alembic migration、時間欄位與 SQL 聚合仍建議在**授權的空白 PostgreSQL 測試 Schema**做整合驗收。

## 5. 目錄結構

```text
project_3_parking/
├── app/
│   ├── __init__.py       # Application Factory / CLI
│   ├── extensions.py     # DB, LoginManager, CSRF, Migrate
│   ├── models/           # 六張資料表
│   ├── api/              # Auth, Accounts, CRUD, Parking, Analytics
│   ├── services/         # 業務邏輯、虛構測試資料
│   ├── web/routes.py     # HTML 頁面
│   ├── templates/        # Bootstrap + Jinja2
│   └── static/           # JavaScript / CSS
├── migrations/           # Alembic 初始 migration
├── sql/schema.sql        # PostgreSQL Schema 參考版
├── docs/                # ERD + API 文件
├── tests/               # pytest
├── config.py
├── wsgi.py
├── requirements.txt
├── requirements-dev.txt
├── render.yaml
├── Dockerfile
└── .env.example
```

## 限制與注意事項

- 沒有提供自動註冊功能，請使用 CLI 或 ADMIN 建立 LoginAccount。
- 為避免歷史紀錄失真，已離場／已付款的停車紀錄不可刪除；開放中的紀錄可編輯進場時間或取消。
- 部分跨資料表條件（車種相符、停車證有效）由 Service 層驗證；寫入資料請通過 API，避免直接 SQL 繞過規則。
- Chart.js 與 Bootstrap 的 JS/CSS 經由 CDN 載入，離線本機部署需自行下載並改用本地靜態檔案。
- 即時使用率是「目前未離場車輛 / 區域容量」，不是尖峰期間的平均使用率；Dashboard 的日期篩選按進場日計算，收入按付款日計算。
- 本專案只作課堂示範，不是學校正式收費規則或官方即時車位資訊。
