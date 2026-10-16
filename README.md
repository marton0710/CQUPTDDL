# 重邮聚合截止线 · CQUPTDDL

[![CI](https://github.com/marton0710/CQUPTDDL/actions/workflows/ci.yml/badge.svg)](https://github.com/marton0710/CQUPTDDL/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.14%2B-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.136%2B-009688.svg)](https://fastapi.tiangolo.com/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

把「学在重邮」「学习通」「雨课堂」三个平台的作业聚合成一份截止线：自动定时刷新、同步到 Meet 课程表、订阅到系统日历，并通过 QQ 机器人推送临期提醒。

- 在线体验：<https://ddl.cqu.pt>
- 前端仓库：[marton0710/DDL-Web](https://github.com/marton0710/DDL-Web)（Vue）
- 接口文档：部署实例的 `/docs`（OpenAPI / Swagger UI）

## 目录

- [功能特性](#功能特性)
- [架构](#架构)
- [技术栈](#技术栈)
- [快速开始](#快速开始)
- [配置项](#配置项)
- [API 概览](#api-概览)
- [项目结构](#项目结构)
- [开发与质量保障](#开发与质量保障)
- [部署](#部署)
- [已知局限与后续计划](#已知局限与后续计划)
- [许可证](#许可证)

## 功能特性

- **多平台作业聚合**：一次绑定三个平台，统一查询、手动/自动刷新、标记完成，按平台过滤与分页。
- **两种登录方式**：学在重邮 / 雨课堂复用学校统一认证（支持扫码登录），学习通使用账号密码；平台凭据 AES 加密后落库，Cookie 失效自动重新登录并重试。
- **定时自动刷新**：APScheduler 按 `用户 × 平台` 调度，间隔 = 基础 TTL + 随机抖动；手动刷新有独立冷却（冷却中返回 `429`）。
- **ICS 日历订阅**：一个用户可建多条订阅（可指定平台），支持 `ETag` / `304`；针对不发送条件请求的客户端，服务端可按数据源版本**强制返回空 304**，把无效正文流量降到 0。
- **Meet 课程表同步**：四阶段状态机（`PUSH → UPDATE → DELETE → PULL`）把作业镜像成日历事件，并回写远端真实完成状态；api-key 失效 / 权限不足 / 课程表被删时自动解绑，不产生无限重试。
- **QQ 机器人推送**：新作业提醒 + 临期提醒，定时（cron 推 scope 内截止）与实时（`deadline - scope` 触发）两种策略，实时消息进缓冲后合并发送；推送通道可切换（见下文）。
- **可选静态前端托管**：配置 `FRONTEND_DIR` 后，后端以同源方式托管前端构建产物，无需额外 Web 服务器。

## 架构

```
        前端 (Vue / QQ 机器人)
                 │  HTTP + Cookie / X-API-Key
                 ▼
        ┌──────────────────────────────┐
        │  router/     FastAPI 路由层   │  参数校验、依赖注入、异常映射
        ├──────────────────────────────┤
        │  service/    业务层           │  auth / platform / homework
        │                               │  qqpush / meetschedule / ics
        ├──────────────────────────────┤
        │  core/       基础设施         │  config · db · factory · symbol
        │                               │  hook · event_bus · task
        └──────────────────────────────┘
                 │                    │
                 ▼                    ▼
        MySQL / MariaDB (SQLModel)  第三方平台 / Meet / qqchan
```

设计上刻意拆出了五个机制，避免业务模块互相 import 形成网状依赖：

| 机制 | 位置 | 作用 |
| --- | --- | --- |
| 依赖注入 | `core/factory.py` | 路由用 `SessionDep` / `UserDep`；非路由代码用 `get_session()` / `get_client()` 上下文管理器。session 在 `yield` 之后统一 commit |
| 符号表 | `core/symbol.py` | 跨 service 调用的**声明与实现分离**：泛型 `Symbol[**P, R]` 预先声明签名，实现处 `@core.symbol.xxx.register` 注册。跨模块调用一律走符号表，不直接 import 别的 service |
| 钩子 | `core/hook.py` | 进程内扩展点，`@core.hook.on("auth.after_register")` 注册，支持 `background=True`（不阻塞）与 `fatal=True`（失败阻断） |
| 事件总线 | `core/event_bus.py` | 仅保留两个跨模块广播事件：登录过期、自动刷新失败（新逻辑优先用钩子） |
| 后台任务 | `core/task.py` | `core.task.background()` 立即执行 + `register()` 在事件循环启动前登记，由 `core.init()` 统一启动 |

同步逻辑的核心是**把「远端结局」与「本地动作」解耦**：远端调用点只汇报 `OK / MISSING / PERMANENT / TRANSIENT` 四种结局，本地状态迁移收敛到唯一真值表 `_transition`（[`refresh_task.py`](src/cquptddl/service/meetschedule/refresh_task.py)）。要改同步规则只改这一处，并且有表驱动测试逐格钉死（[`test_meetschedule_transition.py`](tests/test_meetschedule_transition.py)）。

### 推送通道可切换

QQ 官方机器人暂未对个人开放，因此当前使用野生机器人通道；官方机器人实现作为备用保留，两者接口一致。`service/qqpush/push.py` 是指向现役实现的**符号链接**，切换通道 = 改链接目标，业务代码零改动。

## 技术栈

| 类别 | 选型 |
| --- | --- |
| 语言 / 运行时 | Python 3.14+（实际生产环境 3.15），`uv` 管理依赖与发版 |
| Web 框架 | FastAPI + Uvicorn |
| 数据层 | SQLModel / SQLAlchemy 2.x（异步）+ MySQL / MariaDB（`aiomysql`），本地可用 SQLite |
| 认证 | PyJWT 双令牌（access + refresh）+ Cookie，uid 加密进 payload，配 `token_version` 实现批量失效 |
| 加密 | PyCryptoDome（AES-CBC）加密平台密码与凭据 |
| 调度 | APScheduler（按用户 × 平台的刷新任务、推送策略、Meet 同步） |
| HTTP 客户端 | httpx（异步，统一 `User-Agent`） |
| 日历 | icalendar（ICS 渲染） |
| 限流 | throttled-py（Meet API 60 次/分钟） |
| 外部依赖 | `fuckids`（学校统一认证）、`meetschedule-sdk`（Meet 课程表）、`abxbus`（事件总线） |
| 质量工具 | ruff（lint + format）、ty（类型检查）、pytest |

## 快速开始

### 前置条件

- Python 3.14+（仓库内 `.python-version` 指定 3.15）
- [uv](https://docs.astral.sh/uv/)
- 一个 MySQL / MariaDB 库（本地开发也可直接用 SQLite）
- 可选：一个 [qqchan](https://github.com/) 机器人实例（不配置则跳过推送相关功能）

### 安装与运行

```bash
git clone git@github.com:marton0710/CQUPTDDL.git
cd CQUPTDDL

cp .env.example .env      # 然后按「配置项」一节填写
uv sync --dev             # 安装依赖（含开发依赖）
uv run cquptddl           # 启动服务，默认监听 8000
```

`DEBUG=true` 时会开启 uvicorn 热重载，并且只监听 `127.0.0.1`。

首次启动由 `core.init()` 调用 `SQLModel.metadata.create_all` 自动建表（只会创建缺失的表，不会修改已有表结构，见[已知局限](#已知局限与后续计划)）。

启动后：

- 接口文档：<http://127.0.0.1:8000/docs>
- 当前版本：<http://127.0.0.1:8000/api/version>

### 配置前端（可选）

```bash
# 将 DDL-Web 的构建产物放到任意目录后：
FRONTEND_DIR=/path/to/dist uv run cquptddl
```

后端会以同源方式托管该目录，并对未匹配的路径回退到 `index.html`。

## 配置项

配置来自 `.env`（`pydantic-settings`，大小写不敏感，未知字段忽略），完整示例见 [`.env.example`](.env.example)。

**必填：**

| 变量 | 说明 |
| --- | --- |
| `DATABASE_URL` | 数据库连接串，如 `mysql+aiomysql://user:pass@host:3306/cquptddl`；本地可用 `sqlite+aiosqlite:///./test.db` |
| `SECRET_KEY` | JWT 签名密钥，同时派生 AES 密钥 `md5(SECRET_KEY)[:16]`。**上线后更换会导致已存凭据无法解密** |
| `QQBOT_URL` | qqchan 机器人地址 |
| `QQBOT_RECV_API_KEY` | 后端 → 机器人方向鉴权 |
| `QQBOT_SEND_API_KEY` | 机器人 → 后端方向鉴权（请求头 `X-API-Key`） |

**常用可选：**

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `DEBUG` | `false` | 开启热重载、只监听回环地址、放宽部分日志 |
| `homework_cache_base_ttl` | `43200` | 自动刷新间隔基数（秒） |
| `homework_cache_jitter` | `1800` | 刷新间隔随机抖动上限（秒） |
| `homework_cooldown_ttl` | `1800` | 手动刷新冷却（秒） |
| `homework_refresh_attempts` | `3` | 单次刷新的尝试次数（仅对超时重试） |
| `meetschedule_sync_interval` | `300` | Meet 同步轮询间隔（秒） |
| `ACCESS_TOKEN_EXPIRE_SECONDS` | `900` | access token 有效期 |
| `REFRESH_TOKEN_EXPIRE_SECONDS` | `604800` | refresh token 有效期 |
| `qr_login_session_ttl` | `180` | 扫码登录会话有效期（秒） |
| `ics_timezone` | `Asia/Shanghai` | 日历时区 |
| `ics_event_duration_minutes` | `30` | 日历事件时长（结束时间 = 截止时间） |
| `ics_past_days` | `30` | 订阅中保留最近多少天内已截止的作业 |
| `FRONTEND_DIR` | 空 | 前端构建产物目录，设置后由后端托管 |

## API 概览

所有接口以 `/api` 为前缀，完整定义见 `/docs`。除登录与日历订阅外均需登录态（Cookie）。

| 分组 | 方法 | 路径 | 说明 |
| --- | --- | --- | --- |
| auth | `POST` | `/api/auth/login` | 账号密码登录 |
| | `GET` | `/api/auth/qrcode_login` | 获取统一认证二维码（返回会话 id 与二维码） |
| | `POST` | `/api/auth/qrcode_login` | 轮询扫码结果（未扫描返回 `202`） |
| | `POST` | `/api/auth/refresh` | 刷新令牌 |
| | `GET` `DELETE` | `/api/auth/me` | 当前用户信息 / 注销账号 |
| | `POST` | `/api/auth/logout` | 登出并失效令牌 |
| platform | `GET` | `/api/platform/{platform}/auth_method` | 查询该平台登录方式 |
| | `POST` | `/api/platform/{platform}/bind` | 绑定平台 |
| | `POST` | `/api/platform/{platform}/unbind` | 解绑平台并清理本地作业 |
| | `GET` | `/api/platform/{platform}/valid_cookie` | 检查平台 Cookie 是否有效 |
| homework | `GET` | `/api/homework` | 查询作业（支持平台过滤、分页） |
| | `POST` | `/api/homework/refresh` | 手动刷新（带冷却） |
| | `POST` | `/api/homework/{id}/complete` | 标记完成 |
| qqpush | `POST` | `/api/qqpush/configure` | 推送配置（提醒范围、时间窗等） |
| | `POST` | `/api/qqpush/_/dying_homeworks` | 供机器人反向调用 |
| meetschedule | `POST` | `/api/meetschedule/bind` | 绑定 Meet 课程表并回填全部作业 |
| | `DELETE` | `/api/meetschedule/bind` | 解绑（`202` 表示异步清理） |
| ics | `GET` `POST` | `/api/ics/subscription` | 列出 / 新建订阅（明文 token 仅创建时返回一次） |
| | `DELETE` | `/api/ics/subscription/{id}` | 撤销订阅 |
| | `GET` | `/api/ics/feed/{token}.ics` | 日历正文（供日历客户端拉取，无需登录） |
| 其他 | `GET` | `/api/version` | 当前版本号 |

## 项目结构

```
src/cquptddl/
├── __init__.py          # FastAPI app、lifespan 生命周期、main 入口
├── exc.py               # 业务异常（类属性声明 status/detail，统一转 HTTPException）
├── core/                # 基础设施：config db factory symbol hook event_bus task
├── model/
│   ├── db/              # SQLModel 表：User Homework PlatformInfo QQPushConfig
│   │                    #   MeetscheduleConfig MeetscheduleEntry IcsSubscription
│   ├── schema/          # 请求 / 响应模型与枚举（PlatformEnum、AuthMethod）
│   └── event/           # 全局广播事件定义
├── middleware/          # 登录态(UserDep)、会话(SessionDep)、机器人鉴权(X-API-Key)
├── router/api/          # auth homework platform qqpush meetscheule ics
└── service/
    ├── auth/            # 统一认证、扫码登录、JWT、AES
    ├── platform/        # Platform 抽象基类 + 学在重邮 / 学习通 / 雨课堂实现
    ├── homework/        # 查询、刷新、完成、定时刷新任务
    ├── qqpush/          # 推送策略、缓冲发送、通道实现
    ├── meetschedule/    # 四阶段同步状态机、限流
    └── ics/             # 日历渲染（纯函数）与订阅管理
tests/                   # pytest：ICS 渲染/订阅/强制缓存、平台冷却、符号 mock、状态机真值表
```

新增平台只需实现 `Platform` 子类（声明 `name` 与 `auth_method`，`__init_subclass__` 自动注册）并在 `service/platform/__init__.py` 中 import。

## 开发与质量保障

```bash
uv run pytest -q      # 单元测试
ruff check .          # lint
ruff format --check . # 格式检查
ty check              # 类型检查
```

以上四项在 [CI](.github/workflows/ci.yml) 中对每次 push 与 PR 全量执行。测试全部使用内存 SQLite，不依赖外部服务；`core.symbol.mock()` 支持在 `DEBUG` 下临时替换符号实现，用于构造注入。

开发约定（详见 [`AGENTS.md`](AGENTS.md)）：注释、日志与异常信息统一中文；提交信息遵循 Conventional Commits；跨 service 调用走符号表；每个模块显式设置 logger 级别。

## 部署

仓库提供 [`Dockerfile`](Dockerfile)：基于 `python:3.15-alpine`，从自建源安装已发布的 `cquptddl` 包，并将前端产物复制到 `/fe` 由 `FRONTEND_DIR` 指向，容器暴露 `8000`。

```bash
docker build -t cquptddl .
docker run -d --name cquptddl \
  --env-file .env \
  -e FRONTEND_DIR=/fe \
  -p 8000:8000 \
  cquptddl
```

发版：`uv build` 产出 `dist/` 下的 wheel 与 sdist，发布到自建 PyPI 源后由 Docker 构建拉取。

> 当前为**单实例部署**：扫码登录会话、刷新冷却锁、推送缓冲与 Meet 限流都在进程内，如需水平扩展需要先引入共享存储（Redis 等）。

## 已知局限与后续计划

- **建表不迁移**：只使用 `SQLModel.metadata.create_all`，不做 `ALTER`。字段或主键变更需要一次性迁移脚本（例如修改作业主键会让增量刷新产生全量重复）<!--，后续计划引入 Alembic-->。
- **单实例假设**：见上文「部署」一节的说明。
- **测试覆盖不均衡**：ICS 渲染/订阅/缓存与平台冷却、Meet 状态机有测试，认证与平台抓取解析仍以人工验证为主。
- **凭据加密**：当前为 AES-CBC，无完整性校验与密钥轮换，计划升级到 AES-GCM 并拆分密钥。
- **推送通道**：受 QQ 官方机器人个人开发者政策限制，暂用野生通道，官方通道代码已保留待切换。

## 贡献

欢迎提交 Issue 与 Pull Request。请确保本地 `ruff` / `ty` / `pytest` 全绿，并遵循 Conventional Commits 提交规范。

## 许可证

本项目采用 [MIT 许可证](LICENSE)。
