# Polymarket 事件驱动候选单系统

> 研究 / 候选单 / 风控 / 仓位管理 / 执行 / 监控 / 报告

基于事件驱动架构的 Polymarket 量化交易候选单系统。系统从外部事件源（如 6551 OpenNews）采集信号，经过规则引擎、交易论点生成、风控审核、仓位计算后，生成候选订单并执行（默认 dry-run 模式）。

## ⚠️ 安全原则 与 运行模式

- **禁止浏览器自动化交易**：为了确保确定性及交易效率，系统仅通过 Polymarket 官方 Python SDK 在后端封装执行交易。
- **不包含任何真实密钥**：所有凭证必须通过环境变量注入。

### 三种运行模式支持 (Execution Modes)

为满足开发到生产的全周期，核心 Execution 层提供了三层切换保护：
1. **Paper Mode (Dry-Run)**: 当设定环境变量 `DRY_RUN=true` 时自动启动。此模式使用 `PolymarketPaperAdapter`，所有订单将会**在内存网格中本地模拟撮合**，完全模拟 `place -> fill` 的生命周期，**零风险**用于测试。
2. **Live Mode (实盘撮合)**: 当 `DRY_RUN=false` 时，启用 `PolymarketLiveAdapter`。该模式将严苛依赖官方 Python SDK (`py-clob-client`) 发送订单。
   > [!WARNING]
   > 必须配置全部环境变量 `POLYMARKET_PRIVATE_KEY` / `POLYMARKET_API_KEY` / `POLYMARKET_API_SECRET` / `POLYMARKET_PASSPHRASE` 才能发起实盘订单，否则服务将因无有效凭证而主动驳回。
3. **隔离审计机制**: 无论触发何种模式，每一次对订单发起的执行变迁与错误日志均被写入数据库 `ExecutionRecord` 作为不可抹除的全局 Audit Log 台账。

## 技术栈

| 组件       | 技术            |
|------------|----------------|
| 语言       | Python 3.11+   |
| Web 框架   | FastAPI        |
| 数据库     | PostgreSQL 16  |
| ORM        | SQLAlchemy 2.x |
| 数据迁移   | Alembic        |
| 数据校验   | Pydantic v2    |
| 缓存       | Redis 7        |
| 日志       | structlog      |
| 测试       | pytest         |

## 项目架构

```
polymarket-agent/
├── apps/                       # 业务应用模块
│   ├── server.py               # FastAPI 主应用入口
│   ├── ingestor/               # 事件接入（OpenNews webhook / 拉取）
│   ├── mapper/                 # 事件 → Polymarket 市场映射
│   ├── rules/                  # 信号规则引擎
│   ├── thesis/                 # 交易论点生成
│   ├── risk_engine/            # 风控引擎（限额/频率/熔断）
│   ├── sizing/                 # 仓位计算（Kelly/固定/比例）
│   ├── execution/              # 订单执行（dry-run / 实盘）
│   ├── monitor/                # 系统监控 & 仪表盘
│   ├── reporting/              # 交易报告 & 绩效分析
│   └── orchestrator/           # 流程编排（预留 Hermes 集成）
├── libs/                       # 公共基础库
│   ├── models/                 # Pydantic DTO + SQLAlchemy ORM
│   │   ├── db_models.py        # ORM 表定义
│   │   ├── schemas.py          # Pydantic 请求/响应模型
│   │   └── settings.py         # 全局配置（pydantic-settings）
│   ├── storage/                # 数据库连接 & 仓储层
│   │   ├── database.py         # 异步/同步引擎管理
│   │   └── repository.py       # 通用 CRUD 仓储基类
│   ├── adapters/               # 外部系统适配器
│   │   ├── polymarket_client.py  # Polymarket SDK 适配器
│   │   ├── opennews_client.py    # 6551 OpenNews 客户端
│   │   └── hermes_client.py      # Hermes 编排引擎客户端
│   └── utils/                  # 工具函数
│       ├── logging.py          # 结构化日志
│       └── yaml_loader.py      # YAML 配置加载
├── configs/                    # 运行时配置文件
│   ├── markets_whitelist.yaml  # 市场白名单
│   ├── risk_limits.yaml        # 风控限制
│   ├── sizing.yaml             # 仓位计算参数
│   └── sources.yaml            # 数据源配置
├── alembic/                    # 数据库迁移
├── tests/                      # 测试
│   ├── unit/                   # 单元测试
│   ├── integration/            # 集成测试
│   └── replay/                 # 事件回放测试
├── .env.example                # 环境变量模板
├── pyproject.toml              # 项目依赖 & 工具链配置
├── docker-compose.yml          # 本地基础设施
└── README.md                   # 本文件
```

## 数据流

```
OpenNews 事件 ──▶ Ingestor ──▶ Mapper ──▶ Rules ──▶ Thesis
                                                      │
         Hermes ◀── Orchestrator ◀── Execution ◀── Sizing ◀── Risk Engine
```

> **架构声明**：
> - `thesis`（投研）模块仅仅提供结构化数据研究支撑（如方向概率和信心等），**不直接进行交易路由或发单**。
> - `sizing`（仓位）模块计算尺寸是严格基于排除了各项损耗摩擦后的**净 edge (Net Edge)** 来推导半凯利分型，而非使用单纯原始概率差。

## 🚀 运维与本地部署指引

### 1. 本地一键启动 (Bootstrap)
对于首次运行，无论是 Windows 还是 Linux 用户，都可以直接使用我们提供的 `bootstrap` 脚本：
- **Windows**: 双击执行或在控制台运行 `scripts\bootstrap.bat`
- **Linux/Mac**: 运行 `bash scripts/bootstrap.sh`
> 注: 系统会自动创建 `.env` 配置表、新建 `venv` 虚拟环境并完成依赖安装。

### 2. 数据库拉起与配置 (Docker)
项目采用 `Postgres+Redis` 双擎。无需本地手动安装数据库，执行以下命令：
```bash
docker-compose up -d postgres redis
```
确认容器处于健康状态后，执行数据表迁移命令生成基础表：
```bash
make db-upgrade
```

### 3. 运行模式切换 (Dry-run / Paper / Live)
控制引擎交易动作的权力核心完全由 `.env` 或运行时环境变量内的 `DRY_RUN` 决定：
- **Paper Mode (Dry Run)**: 设置 `DRY_RUN=true`。这是系统的**默认保护态**，所有流程会在内存中通过 `PolymarketPaperAdapter` 进行模拟撮合，无任何真实损耗和安全隐患。
- **Live Mode (实盘)**: 设置 `DRY_RUN=false`。此时系统启用 `PolymarketLiveAdapter`。你**必定**需要在 `.env` 中提供 `POLYMARKET_PRIVATE_KEY` / `POLYMARKET_API_KEY` / `POLYMARKET_API_SECRET` / `POLYMARKET_PASSPHRASE` 四要素，系统才会将签名单发往主网。请极其谨慎！

### 4. 测试与验证步骤
我们使用 `pytest` 引擎进行底层模块的高覆盖率断言。
执行完整的单元与全链路管线流测试：
```bash
make test
```

### 5. 格式化检阅
推荐在 Git Commit 前进行风格一致性卡控：
```bash
make lint
```

## ⚠️ 风险提示与免责声明 (Risk Disclaimer)
1. **黑天鹅风险**: 尽管系统中拥有极为严苛的 Sizing 及 RiskEngine（日最大亏损熔断、流动枯竭检测），但去中心化预测市场天然具备合约风险及结算争议可能。
2. **凭据安全**: 任何情况下，不得在未经过隔离的沙箱内将携带主网私钥的实盘版本置于公网。
3. **资金安全**: 净边际半凯利是一种高度防守型的仓位公式，不保证盈利，系统属于实验性，请妥善控制资金边界。

## API 端点概览

| 模块          | 路由前缀                                | 说明          |
|---------------|----------------------------------------|---------------|
| 健康检查      | `GET /health`                          | 系统状态      |
| Ingestor      | `/api/v1/ingestor`                     | 事件接入（旧） |
| Ingest        | `POST /api/v1/ingestor/ingest/opennews/webhook` | OpenNews webhook |
| Ingest        | `POST /api/v1/ingestor/ingest/opennews/pull`    | OpenNews 拉取 |
| Mapper        | `POST /api/v1/mapper/signals/map/{id}` | 映射事件至市场 |
| Rules         | `GET /api/v1/rules/{candidate_id}`     | 获取&分析规则 |
| Rules         | `POST /api/v1/rules/evaluate/{id}`     | 评估信号判定 |
| Thesis        | `POST /api/v1/thesis/build/{id}`       | 结构化交易论点 |
| Risk Engine   | `POST /api/v1/risk/check/{id}`         | 确定性风控审查 |
| Sizing        | `POST /api/v1/sizing/calculate/{id}`   | 净边际仓位计算 |
| Execution     | `/api/v1/execution`                    | 订单执行      |
| Monitor       | `/api/v1/monitor`                      | 系统监控      |
| Reporting     | `/api/v1/reporting`                    | 交易报告      |
| Orchestrator  | `/api/v1/orchestrator`                 | 流程编排      |

## 预留集成

### Hermes Orchestration
系统预留了 `HermesClient` 适配器 (`libs/adapters/hermes_client.py`)，可通过配置 `HERMES_ENDPOINT` 和 `HERMES_API_KEY` 接入 Hermes 编排引擎。

### 6551 OpenNews

通过三层架构接入 OpenNews 事件源：

| 层级 | 文件 | 职责 |
|------|------|------|
| HTTP 适配器 | `libs/adapters/opennews_client.py` | 封装 REST API 调用，返回原始 dict |
| 业务客户端 | `apps/ingestor/opennews_client.py` | 调用适配器 + webhook 校验 |
| 标准化 | `apps/ingestor/normalizer.py` | 原始 dict → 统一 IngestEvent DTO |
| 编排服务 | `apps/ingestor/service.py` | validate → normalize → dedupe → save |

#### 环境变量配置

在 `.env` 中配置以下变量（参见 `.env.example`）：

```bash
# OpenNews API 认证令牌（必填）
OPENNEWS_TOKEN=your_opennews_api_token_here

# API 基础 URL（选填，有默认值）
OPENNEWS_BASE_URL=https://api.opennews.6551.io/v1

# WebSocket URL（预留，当前版本未启用）
OPENNEWS_WS_URL=wss://ws.opennews.6551.io/v1/stream
```

> ⚠️ `OPENNEWS_TOKEN` 为必填项。未配置时，API 调用将返回 401 错误。请从 OpenNews 管理后台获取令牌。

#### 使用方式

**Webhook 推送**（由 OpenNews 主动调用）：
```bash
curl -X POST http://localhost:8000/api/v1/ingestor/ingest/opennews/webhook \
  -H 'Content-Type: application/json' \
  -d '{"id": "evt_001", "title": "Bitcoin ATH", "body": "...", "category": "crypto"}'
```

**手动拉取**：
```bash
curl -X POST 'http://localhost:8000/api/v1/ingestor/ingest/opennews/pull?limit=20'
```

#### 去重机制

系统基于 `dedupe_hash`（SHA-256 of `source|source_event_id|headline`）进行全局去重：
- Webhook 推送重复事件返回 `409 Conflict`
- 批量拉取自动跳过重复事件并在响应中统计

### Polymarket 市场数据与规则解析 (Mapper & Rules)
利用提取的各类事件(News/Events)调用 **PolymarketMarketClient**，使用内部启发式的 **mapping_score** (综合实体标签/词汇交集度) 定位最佳市场匹配。映射记录会保存至 `candidate_markets` 表。
针对每个 `CandidateMarket`：
* **RulesParser**: 拉取事件描述(rule_text)，提取判定源 `resolution_source`、结束时间 `end_date`、和边缘处理条件 `edge_cases`，并计算规则明确度。
* 获取当前的盘口数据及价差 (spread)。

### Polymarket SDK
通过 `PolymarketClient` 适配器 (`libs/adapters/polymarket_client.py`) 预留官方 SDK 集成接口。待 `py-clob-client` 集成后可实现真实交易。

## 配置说明

### 风控限制 (`configs/risk_limits.yaml`)
- 包含严格白名单市场限制、单市场/分类主题最大风险隔离
- 单日新增风险上限控制与单日最大亏损熔断
- 强制校验最小盘口深度、最大盘口价差 (spread)、及预估滑点预置
- 最大持仓时长约束及临近到期 (near-expiry) 避免交易策略

### 仓位计算 (`configs/sizing.yaml`)
- 使用**净边际半凯利 (Net Edge Half Kelly)**计算策略
- 基于 `alpha` 折扣收缩主观概率避免过度自信 (`q_adj = p_market + alpha * (q_raw - p_market)`)
- 自动核算执行摩擦包含：预测 Taker_fee、合理滑点估损、退出仓位储备以及不确定性折本
- 支持绝对上限 `$USD` 仓位斩波控制

### 市场白名单 (`configs/markets_whitelist.yaml`)
- 按类别过滤
- 按条件 ID 白名单/黑名单
- 最低流动性和交易量要求

## 开发指南

- 所有代码使用 Python 3.11+ 类型注解
- 使用 `ruff` 进行代码风格检查
- 使用 `mypy` 进行静态类型检查
- 新模块需在 `apps/server.py` 中注册路由
- 数据库变更通过 Alembic 迁移管理
- 所有交易相关操作必须支持 dry-run 模式

## Replay 回放与 Paper Backtest

`apps.replay` 用于按历史事件窗口重放候选单，并基于历史快照做 paper backtest。该模块不会复用实时 execution/position 表，而是把每次回放的汇总、逐候选单、逐成交和资金曲线单独落到 replay 结果表中。

### 前置历史数据

运行 replay 前，需要数据库中已经存在以下历史输入：

- `ingest_events`：历史事件，回放窗口按 `published_at` 过滤
- `candidate_orders`：历史候选单，使用其中的 `size` / `target_price`
- `thesis_history` / `risk_history` / `sizing_history`：历史 thesis / risk / sizing 结果
- `market_snapshot_history`：历史盘口快照，至少包含 `condition_id / outcome / snapshot_at / best_bid / best_ask / executable_size`
- `market_resolutions`：最终决议与 payout

如果候选单缺少任一关键历史输入，系统会把它计入候选单数量，但标记为不可交易；不会补算 thesis/risk/sizing，也不会用最近快照插值。

### CLI 用法

```bash
python -m apps.replay.main --start 2026-01-01 --end 2026-01-31
```

默认行为：

- 使用 `published_at` 作为窗口锚点
- 自动创建一条 `replay_runs` 记录
- 默认导出到 `artifacts/replay/<run_id>/`
- 终端输出 run id、候选数、可交易数、成交数、累计 pnl 和导出目录

### 指标口径

- 候选单数量：窗口内关联事件的历史 `CandidateOrder` 数量
- 可交易数量：同时具备历史 thesis/risk/sizing、有效 entry snapshot、最终 resolution，且 `risk.allow=true`、`size>0`
- 平均净 edge：可交易候选单的 `sizing_history.edge_net` 平均值
- 模拟成交数：满足可交易且通过目标价格与 `executable_size` 校验的成交数
- 胜率：已结算成交中 `pnl > 0` 的占比
- 平均持仓时长：`resolved_at - fill_at`
- 最大回撤：基于 `replay_equity_points` 的资金曲线峰谷回撤
- 累计 pnl：所有已结算成交 pnl 之和

### 撮合与结算规则

- `BUY` 按对应 outcome 的 `best_ask` 成交
- `SELL` 按对应 outcome 的 `best_bid` 成交
- 仅使用 `snapshot_at >= candidate_order.created_at` 的第一条快照作为 entry snapshot
- 如果价格没有穿过 `target_price` 或快照可成交数量不足，则标记为未成交
- 已成交仓位持有到最终 `market_resolutions` 结算，不做超时强平

### 导出目录

每次 replay 默认导出以下文件：

- `summary.csv`
- `summary.json`
- `candidate_results.csv`
- `candidate_results.json`
- `trade_results.csv`
- `trade_results.json`
- `equity_curve.csv`
- `manifest.json`

### 常见不可交易原因

- `missing_thesis_history`
- `missing_risk_history`
- `missing_sizing_history`
- `missing_condition_id`
- `non_positive_order_size`
- `risk_blocked`
- `missing_entry_snapshot`
- `missing_market_resolution`

## 许可证

MIT

## 系统全流程解

从事件发起到自动执行离场，系统构建了一条高度确定性的坚固单向传输链路：
1. **Event Ingest**: 外部引擎抛出消息，安全录入 IngestEvent。
2. **Mapper & Rules**: 生成实体对齐的候选集 CandidateMarket。
3. **Thesis Generation**: 组合并构建纯领域研究输出 ThesisResult。
4. **Risk & Sizing**: 前置拦网网与极值削波保护分配单子为 CandidateOrder。
5. **Orchestrator 审批悬停**: 管线统一评估合规后，状态挂起为 AWAIT_APPROVAL 等待人工裁决。
6. **Execution 落地执行**: 收到 True 的批准后底层 OrderManager 全权接管状态流转并创建 ExecutionRecord 审计台账。
7. **Monitor 后期防线**: MonitorService 侦测 Thesis翻转等 5 类退出警戒触发平仓并汇入 Reporting 每日自动化结账。
