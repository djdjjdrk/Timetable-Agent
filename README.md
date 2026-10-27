# Timetable-Agent · 校园课程智能助手

基于 Vue 3 和 FastAPI 的校园课程智能助手，支持账号、用户、课程、课表、学习计划和课程资料管理。课程助手通过 LangChain Agent 调用 MCP 工具查询当前用户课表，支持普通对话和 SSE 流式回答。

## 当前功能

| 模块 | 当前状态 |
| --- | --- |
| 管理布局 | 顶部导航、侧边菜单、当前用户展示、个人信息与修改密码入口 |
| 系统首页 | 展示当前登录账号的欢迎信息 |
| 注册与登录 | 前端调用后端接口；注册成功后跳转登录；登录返回 JWT 和用户信息 |
| 身份认证 | bcrypt 密码哈希、JWT 校验、用户存在性和禁用状态检查 |
| 权限控制 | 前端登录与管理员路由守卫；后端登录用户与管理员依赖校验 |
| 用户管理 | 管理员分页查询、按账号或姓名模糊搜索、新增、修改、禁用及删除用户 |
| 课程管理 | 管理员查询、新增、编辑、停用及删除课程，支持名称、代码和简介模糊搜索 |
| 个人信息 | 查询和修改当前用户资料，支持头像上传 |
| 修改密码 | 校验原密码及新旧密码不同；前端成功后清除本地登录信息并跳转登录 |
| 文件上传 | 校验文件后缀和文件大小，保存至本地并返回访问地址 |
| 我的课表 | 学生分页查询本人课表，支持按日期筛选，后端强制隔离用户数据 |
| 课表管理 | 管理员新增、编辑、删除课表，按学生和日期筛选；已排课课程禁止删除 |
| 学习计划 | 保存、本人分页列表、Markdown 详情及删除，JWT 隔离用户数据 |
| 课程助手 | 登录后聊天，支持 SSE 流式回答、工具调用过程和本人课表查询；需要配置模型密钥并启动 MCP 服务 |
| 课程资料 | 管理员批量上传、列表查询、删除及文本预览，支持 TXT、Markdown、PDF、DOCX |

## 技术栈

- 前端：Vue 3、Vue Router、Element Plus、Axios、Vite、Prettier。
- 后端：FastAPI、Uvicorn、SQLAlchemy 2、Pydantic、Pydantic Settings。
- 数据库：通过 SQLAlchemy 配置连接，安装了 PostgreSQL 驱动 Psycopg 3。
- 认证：bcrypt、PyJWT。
- Agent / MCP：LangChain、LangGraph、LangChain OpenAI、LangChain MCP Adapters、FastMCP。
- 文档解析：python-docx、pypdf；目前提供文本提取，尚未接入向量检索。
- 测试：unittest、FastAPI TestClient、HTTPX、SQLite 内存数据库。

## 项目结构

```text
Timetable-Agent/
├── backend/
│   ├── app/
│   │   ├── api/                # 认证、用户、课程、课表、学习计划、资料、聊天及 MCP 接口
│   │   ├── common/             # 统一响应、分页响应和异常处理
│   │   ├── dependencies/       # 当前用户及管理员权限校验
│   │   ├── models/             # 用户、课程、课表、学习计划和课程资料表模型
│   │   ├── schemas/            # 请求参数校验和响应数据模型
│   │   ├── services/           # 业务服务、文档解析、Agent 和 MCP 客户端
│   │   ├── utils/              # 密码哈希与 JWT 工具
│   │   ├── config.py           # 环境变量及上传配置
│   │   ├── database.py         # 数据库引擎、会话和模型基类
│   │   └── main.py             # 应用入口、建表、CORS、异常及静态文件配置
│   ├── migrations/            # 用户名唯一约束 SQL 脚本
│   ├── tests/                 # 用户、课程、课表、学习计划和课程资料接口测试
│   ├── mcp_server.py          # 独立运行的课表 MCP 服务
│   ├── data/kb/               # 本地课程资料，不提交
│   ├── uploads/               # 自动创建的本地上传目录，不提交
│   ├── environment.yml        # Conda 环境定义
│   ├── .env.example           # 可提交的配置模板
│   ├── .env                   # 本地配置，自行创建，不提交版本库
│   ├── requirements.txt
│   └── requirements-dev.txt
├── frontend/
│   ├── src/
│   │   ├── api/                # 认证、用户、课程、课表和文件请求封装
│   │   ├── assets/css/         # 全局样式
│   │   ├── layouts/Layout.vue  # 管理布局与菜单
│   │   ├── router/index.js     # 页面路由及权限守卫
│   │   ├── utils/              # Axios 拦截器、登录存储和用户状态
│   │   ├── views/              # 登录、用户、课程、课表、学习计划、资料和聊天页面
│   │   ├── App.vue
│   │   └── main.js
│   ├── package.json
│   └── vite.config.js          # /api 和 /uploads 开发代理
├── docs/Apifox接口测试指南.md
└── README.md
```

后端请求主要经过 `api → services → models / database`；`schemas` 负责参数校验和返回数据结构，`dependencies` 负责身份与权限检查，`common` 负责统一响应和异常处理。

## 本地运行

### 环境准备

- Node.js：`^22.18.0 || >=24.12.0`，与 `frontend/package.json` 一致。
- Python：使用 Conda 管理；当前验证环境为 `timetable-backed`、Python 3.13。
- PostgreSQL：提前创建数据库，准备可连接且有建表权限的账号。

下面使用 Windows PowerShell。后端、MCP 服务和前端分别在三个终端运行；两个 Python 终端均需激活 Conda 环境。

### 启动后端

从项目根目录执行：

```powershell
cd backend
# 新电脑首次创建；已有同名环境时跳过 create。
conda env create -f environment.yml
conda activate timetable-backed
python -m pip install -r requirements.txt
```

从模板复制 `backend/.env`，按本地环境填写配置；已有 `.env` 时保留原文件，不要覆盖：

```powershell
if (!(Test-Path .env)) { Copy-Item .env.example .env }
```

```dotenv
DATABASE_URL=postgresql+psycopg://db_user:db_password@localhost:5432/timetable_agent
JWT_SECRET_KEY=replace_with_your_own_random_secret_at_least_32_bytes
JWT_ALGORITHM=HS256
JWT_EXPIRE_HOURS=24
LLM_BASE_URL=https://api.deepseek.com
LLM_API_KEY=
LLM_MODEL_NAME=deepseek-flash
MCP_HOST=127.0.0.1
MCP_PORT=8001
MCP_PATH=/mcp
```

`DATABASE_URL` 和 `JWT_SECRET_KEY` 为必填项；`JWT_ALGORITHM`、`JWT_EXPIRE_HOURS` 默认分别为 `HS256`、`24`。`LLM_API_KEY` 留空不影响普通管理接口，调用课程助手时会提示缺少配置。使用课程助手前需填写模型密钥，并确认 `LLM_BASE_URL` 与 `LLM_MODEL_NAME` 是供应商支持的地址和模型。JWT 密钥应自行随机生成，例如：

```powershell
python -c "import secrets; print(secrets.token_hex(32))"
```

启动服务：

```powershell
python -m uvicorn app.main:app --reload
```

- 服务地址：<http://127.0.0.1:8000>
- Swagger 接口文档：<http://127.0.0.1:8000/docs>
- ReDoc 接口文档：<http://127.0.0.1:8000/redoc>

应用加载时通过 `Base.metadata.create_all()` 创建缺失的表，不会创建数据库或迁移已有表结构。旧数据库若缺少用户名唯一约束，可检查并处理重复账号后，按需执行 `backend/migrations/001_unique_username.sql`；已有唯一约束时无需重复添加。

### 启动 MCP 服务

在另一个终端中进入项目根目录，再执行：

```powershell
conda activate timetable-backed
cd backend
python mcp_server.py
```

默认 MCP 地址为 `http://127.0.0.1:8001/mcp`。服务使用与后端相同的 `.env` 和数据库配置，通过请求中的 JWT 查询当前用户课表。普通管理功能不依赖 MCP；课程助手和 `/api/mcp/my-schedules` 需要此服务可用。

### 启动前端

在第三个终端中，从项目根目录执行：

```powershell
cd frontend
npm ci
npm run dev
```

默认访问 <http://localhost:5173>，实际地址以终端输出为准。开发服务器将 `/api` 和 `/uploads` 代理到 `http://127.0.0.1:8000`。后端也允许 `http://localhost:5173` 与 `http://127.0.0.1:5173` 的跨域请求。

Axios 的 `baseURL` 默认为空，可通过前端环境变量 `VITE_API_BASE_URL` 指定 API 地址。Vite 的代理仅用于开发服务器，部署构建产物时需要另外配置 API 和上传文件的访问路径。

### 首次使用

1. 打开 `/register` 注册账号，再到 `/login` 登录。注册用户固定为 `student`，状态为正常；名称未提供时使用账号。
2. 项目没有默认账号或管理员初始化脚本。需要管理员时，可先注册账号，再在数据库中将该账号的 `role` 改为 `admin`，重新登录。
3. 管理员登录后可以访问用户管理页面，并创建其他用户。

例如，先注册账号 `admin_demo`，再在数据库客户端执行：

```sql
UPDATE users SET role = 'admin' WHERE username = 'admin_demo';
```

### 前端页面

| 路径 | 页面 | 访问要求 |
| --- | --- | --- |
| `/login` | 登录 | 公开 |
| `/register` | 注册 | 公开 |
| `/manager/home` | 系统首页 | 登录 |
| `/manager/chat` | 课程助手 | 登录 |
| `/manager/documents` | 课程资料管理 | 管理员；后端接口强制校验 |
| `/manager/schedule` | 我的课表，支持日期筛选和分页 | 登录，查询本人课表 |
| `/manager/timetable` | 兼容旧地址，跳转 `/manager/schedule` | 登录 |
| `/manager/schedule-manage` | 课表管理 | 管理员 |
| `/manager/study-plan` | 学习计划，保存、分页、查看和删除 | 登录，菜单仅学生可见 |
| `/manager/profile` | 个人信息 | 登录 |
| `/manager/password` | 修改密码 | 登录 |
| `/manager/user` | 用户管理 | 管理员 |
| `/manager/course` | 课程管理 | 管理员 |

访问 `/` 会跳转到 `/manager/home`，未登录时由路由守卫跳转到 `/login`。前端在 `localStorage` 中保存 Token 和用户信息，退出登录时清除两者。

### 前端常用命令

在 `frontend` 目录执行：

```powershell
npm run build    # 构建到 dist 目录
npm run preview  # 预览已构建的前端
npm run format   # 格式化 src 目录
```

## 后端接口

| 方法 | 路径 | 用途 | 权限 |
| --- | --- | --- | --- |
| GET | `/` | 服务检查 | 公开 |
| POST | `/api/auth/register` | 注册学生账号 | 公开 |
| POST | `/api/auth/login` | 登录，返回 Token 和用户信息 | 公开 |
| GET | `/api/user/me` | 获取当前用户资料 | 登录 |
| PUT | `/api/user/me` | 修改个人资料 | 登录 |
| PUT | `/api/user/password` | 修改自己的密码 | 登录 |
| GET | `/api/user/list` | 分页查询和搜索用户 | 管理员 |
| POST | `/api/user` | 新增用户 | 管理员 |
| PUT | `/api/user/{user_id}` | 修改指定用户 | 管理员 |
| DELETE | `/api/user/{user_id}` | 删除其他用户 | 管理员 |
| GET | `/api/courses` | 查询课程列表，支持 keywords 参数 | 管理员 |
| GET | `/api/courses/{course_id}` | 查询课程详情 | 管理员 |
| POST | `/api/courses` | 新增课程 | 管理员 |
| PUT | `/api/courses/{course_id}` | 修改课程 | 管理员 |
| DELETE | `/api/courses/{course_id}` | 删除课程 | 管理员 |
| GET | `/api/schedules` | 分页查询课表，支持 user_id、date、page、page_size | 登录，学生只能查询本人 |
| POST | `/api/schedules` | 给学生新增课表 | 管理员 |
| PUT | `/api/schedules/{schedule_id}` | 修改课表 | 管理员 |
| DELETE | `/api/schedules/{schedule_id}` | 删除课表 | 管理员 |
| GET | `/api/study-plans` | 分页查询本人的学习计划 | 登录 |
| POST | `/api/study-plans` | 保存本人的学习计划 | 登录 |
| DELETE | `/api/study-plans/{plan_id}` | 删除本人的学习计划 | 登录 |
| GET | `/api/documents` | 课程资料列表 | 管理员 |
| POST | `/api/documents` | 批量上传课程资料 | 管理员 |
| DELETE | `/api/documents/{doc_id}` | 删除资料记录及文件 | 管理员 |
| GET | `/api/documents/{doc_id}/preview` | 提取资料文本 | 管理员 |
| POST | `/api/chat/ask` | 普通 Agent 对话 | 登录 |
| POST | `/api/chat/stream` | SSE 流式 Agent 对话 | 登录 |
| GET | `/api/mcp/my-schedules` | 通过 MCP 查询本人课表 | 登录 |
| POST | `/api/files/upload` | 上传文件 | 当前未要求登录 |
| GET | `/uploads/{文件名}` | 访问已上传文件 | 公开 |

受保护的接口需要请求头：

```http
Authorization: Bearer <登录返回的token>
```

后端会验证 Token，并查询数据库确认用户存在且未禁用；管理员接口还会检查角色。用户被禁用或删除后，其已有 Token 也无法通过这些检查。

### 响应格式

接口使用统一结构：

```json
{
  "code": 200,
  "message": "请求成功",
  "data": null
}
```

`GET /` 返回 `{"code":200,"message":"Hello FastAPI","data":null}`。

HTTP 状态码与响应体中的业务 `code` 分别处理：

| 情况 | HTTP 状态码 | 业务 code |
| --- | --- | --- |
| 成功 | 200 | 200 |
| 账号重复、密码错误等业务异常 | 200 | 默认 500 |
| 非管理员访问管理员接口 | 200 | 403 |
| 未登录、Token 无效或用户被禁用等认证错误 | 401 | 401 |
| 请求参数校验失败 | 422 | 422 |
| 未捕获的服务器异常 | 500 | 500 |

### 注册和登录

注册请求：

```http
POST /api/auth/register
Content-Type: application/json
```

```json
{
  "username": "demo_user",
  "password": "Demo12345",
  "name": "测试用户"
}
```

注册账号要求 3～20 位英文字母、数字或下划线；密码要求 8～20 位，至少包含英文字母和数字，只允许可见 ASCII 字符，不允许空格。`name` 可省略。注册成功返回 `code: 200`、`message: "注册成功"`、`data: null`。

登录使用 JSON 请求体：

```http
POST /api/auth/login
Content-Type: application/json
```

```json
{
  "username": "demo_user",
  "password": "Demo12345"
}
```

成功响应示例：

```json
{
  "code": 200,
  "message": "登录成功",
  "data": {
    "token": "<JWT>",
    "user": {
      "id": 1,
      "username": "demo_user",
      "name": "测试用户",
      "role": "student",
      "email": null,
      "phone": null,
      "avatar": null,
      "status": 1
    }
  }
}
```

账号或密码错误返回 `{"code":500,"message":"账号或密码错误","data":null}`，HTTP 状态码为 200。密码以 bcrypt 哈希保存，用户响应不包含密码字段。

### 用户管理和个人资料

- 用户列表参数：`page` 默认 1 且至少为 1；`page_size` 默认 10，范围为 1～100；`keywords` 可选，按账号或姓名进行忽略大小写的模糊查询。结果按 ID 倒序，返回 `data.list` 和匹配总数 `data.total`。
- 管理员创建用户时，账号去除两端空白后要求 1～50 位；密码为 3～10 位，省略时默认 `123`；名称省略或为空时使用账号；角色默认 `student`，状态默认 `1`。
- 角色可选 `student`、`admin`；状态可选 `0`（禁用）、`1`（正常）。管理员修改用户时可修改名称、邮箱、手机号、头像、角色、状态和密码，不支持修改账号；密码省略、为空字符串或为 `null` 时保留原密码，非空密码要求 3～10 位。
- 个人资料接口仅更新名称、邮箱、手机号和头像，忽略角色、状态和密码字段。资料更新会忽略值为 `null` 的字段。
- 管理员不能删除当前登录的账号；删除其他用户会直接删除数据库记录。
- 自助修改密码的请求字段为 `old_password` 和 `new_password`，后端检查原密码正确及新旧密码不同，目前没有与注册一致的密码复杂度校验。

### 课程管理

重启后端时，`app.main` 在 `create_all` 前导入课程模型，自动创建不存在的 `courses` 表；已有表的结构不会自动修改。管理员登录后可通过侧栏「课程管理」进入 `/manager/course`。

使用教程提供的 Model、Schema、Service、API 分层及 Vue 页面代码，并补齐教程遗漏的详情接口。教程中课程代码必填的代码与表设计说明冲突，此处按表设计实现可选代码：省略、空字符串及全空格保存为 `null`，非空代码必须唯一。名称去除首尾空格后须为 1～100 位，代码最多 50 位，状态为 `0`（停用）或 `1`（正常）。

课程列表一次返回全部匹配记录，按 ID 倒序排列。更新时省略字段保持原值；代码和简介传 `null` 或空字符串可以清空。课程已关联课表时禁止删除，提示「该课程已关联课表，无法删除」。全部五个接口均校验管理员权限，学生不能通过直接调用接口访问。

### 课表管理和学生端查询

沿用第 4 节提供的 Model、Schema、Service、API 和 Vue 页面代码。`models/__init__.py` 导出全部模型，后端启动时会创建缺失的 `schedules` 表。课表通过 `user_id` 关联学生、`course_id` 关联课程；教程中的 `coruses.id` 已修正为 `courses.id`。

管理员侧栏显示「课表管理」，学生侧栏显示「我的课表」。新增或编辑的字段为 `user_id`、`course_id`、`class_date`（如 `2026-10-21`）、`period`（如 `1-2节`）、`location`（如 `教学楼 A201`）。只能给学生安排课表；日期必须有效，节次和地点去除首尾空格后不能为空，最多分别为 50 和 100 字符。修改时省略或传 `null` 的字段保持原值。

`GET /api/schedules` 统一返回 `data: { list, total }`，按 ID 倒序排列。`page` 默认 1，`page_size` 默认 10、最大 100；`date` 可选。管理员可传 `user_id` 筛选学生，不传则查询全部；学生传入其他 `user_id` 也只能查询自己。每条记录包含账号、姓名和课程名称。MCP 工具 `get_my_schedules` 通过课表服务查询当前用户的全部课表或指定日期课表。

学生下拉框按每页 100 条遍历用户列表，修正教程中 `page_size=200` 超过接口限制的问题；课程下拉框只显示正常课程。删除当前页最后一条课表后自动回到有效页。

联调可先准备管理员、学生 `aaa` 和 `bbb`，以及课程 ENG101 / DS101 / MATH101。在管理员页面为 `aaa` 分别创建 2026-10-21 的英语、2026-10-22 的数据结构、2026-10-23 的高等数学课表，`bbb` 暂不排课。确认 `aaa` 可查看三条、按日期筛选只剩一条、`bbb` 列表为空，已排课课程不可删除。自动化测试使用隔离内存数据库中的相同场景，不向业务数据库写入演示数据。

### 学习计划

使用第 5 节提供的 Model、Schema、Service、API 和 Vue 页面代码。重启后端自动创建缺失的 `study_plans` 表；学生侧栏显示「学习计划」，管理员侧栏隐藏该入口。接口要求登录，全部查询和删除均按 JWT 当前用户过滤，忽略客户端指定的 `user_id`。

`POST /api/study-plans` 请求体为 `{ "content": "..." }`，Schema 去除首尾空白，Service 校验内容非空且不超过 2000 字。`GET /api/study-plans` 使用 `page`（默认 1）及 `page_size`（默认 10，范围 1～100），返回 `data: { list, total }`，列表按 ID 倒序。每项包含 `id`、`content` 和 `create_time`。删除他人的或不存在的记录统一提示「学习计划不存在」。本节不提供编辑接口。

前端沿用教程页面，详情通过 `marked` 渲染并经 `dompurify` 清理 HTML，列表显示纯文本摘要。保存后返回第一页，删除当前页最后一条后回到有效页，取消删除不会发送请求。`STUDY_PLAN_MAX_LENGTH` 在 `backend/app/config.py` 中定义，无需修改 `.env`。

`backend/tests/test_study_plan_crud.py` 使用隔离 SQLite 数据库验证教程中的纯文本和 Markdown 示例、倒序与分页、删除、空白及长度边界、JWT 数据隔离和未登录访问，不写入业务库演示数据。

### 文件上传

使用 `multipart/form-data`，文件字段名为 `file`。配置的大小上限为 100 MB，允许的后缀为：

```text
.jpg .jpeg .png .gif .webp .pdf .doc .docx .xls .xlsx .zip
```

文件保存至 `backend/uploads/`，使用时间戳和随机标识生成文件名。返回的 `data` 包含 `original_name`、`disk_name`、`size` 和相对访问地址 `url`（例如 `/uploads/xxx.png`）。当前按后缀校验类型，按可用的 `UploadFile.size` 校验大小。

## 后端测试

在 `backend` 目录执行：

```powershell
python -m pip install -r requirements-dev.txt
python -m unittest discover -s tests -v
```

测试终端同样先执行 `conda activate timetable-backed`。测试仍需满足配置项要求，可使用前述 `backend/.env`。现有测试自行创建 SQLite 内存数据库，并替换数据库依赖和 JWT 测试密钥，不导入会触发业务库建表的 `app.main`，不读写本地业务数据。

覆盖用户列表分页搜索、返回字段、身份权限校验，以及用户创建、编辑、密码哈希、禁用、删除和个人资料字段保护等场景；课程测试覆盖增删改查、详情、三字段搜索、代码可空和唯一、字段清空、参数校验及全部课程接口的身份权限。课表测试覆盖增删改查、联表字段、学生数据隔离、日期和学生筛选、分页、参数校验、身份权限、关联课程删除保护和全量查询服务。当前没有前端自动化测试脚本，也没有覆盖全部接口的测试。

## 当前限制与后续方向

- 已接入 Agent 和 MCP 课表工具；课程资料目前支持文本提取，尚未接入向量化、检索与聊天知识库问答。
- 数据库尚未接入自动迁移工具，现有 SQL 脚本需要手动执行。
- 注册、管理员用户管理和自助修改密码的校验规则目前不同。
- 退出登录清除前端存储；后端尚无 Token 撤销机制，修改密码也不会主动撤销已经签发的 Token。
- 文件上传尚无登录校验，上传文件通过静态路径公开访问。
- 课程助手目前仅提供课表查询工具，尚不能通过工具直接保存学习计划。


## Git 提交与配置管理

- 提交源代码、测试、`requirements*.txt`、`environment.yml`、前端 `package-lock.json` 和 `.env.example`。
- `.env`、真实模型密钥、数据库凭证、上传资料、知识库文件、日志、数据库备份、`tmp/` 和 `output/` 不提交；对应目录已配置忽略规则。
- 前端 `VITE_` 环境变量会暴露给浏览器，只放公开配置；模型密钥仅放后端 `.env`。
- 现有演示资料若需分享，请脱敏后挑选到独立的示例目录，不要直接提交整个上传目录。
- 提交前执行 `git status --short`，逐项暂存并检查 `git diff --cached`；`.gitignore` 不会自动移除已跟踪文件，也不会清除历史提交中的密钥。
- 后端依赖按当前 Conda 环境中的直接依赖版本记录，未导出包含本机路径和无关包的整个环境。升级后运行 `python -m pip check` 和接口测试，再更新版本记录。
