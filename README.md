# Timetable-Agent · 智能实验室预约系统

基于 Vue 3 和 FastAPI 的实验室预约系统项目，目前处于基础框架开发阶段，已搭建前端管理布局、登录与注册页面，以及后端用户模型和登录接口。实验室预约、排课和 Agent 智能预约功能尚未实现。

## 当前功能

| 模块 | 当前状态 |
| --- | --- |
| 管理界面 | 已实现顶部导航、侧边菜单、首页和退出登录跳转 |
| 前端登录 | 已实现表单和加载效果；通过定时器模拟成功，未调用后端 |
| 前端注册 | 已实现表单，尚未实现提交逻辑 |
| 实验室管理 | 已接入路由，页面为待实现占位内容 |
| 设备、用户管理 | 已创建占位页面及菜单入口，尚未配置对应路由 |
| 后端登录 | 已实现数据库账号查询与密码比对，返回用户信息 |
| 数据库 | 已定义 `users` 表，启动后端时自动创建缺失的表 |
| 预约与 Agent | 尚未实现 |

## 技术栈

- 前端：Vue 3、Vue Router、Element Plus、Vite、Prettier。
- 后端：FastAPI、Uvicorn、SQLAlchemy 2、Pydantic Settings。
- 数据库驱动：Psycopg 3；以下启动示例使用 PostgreSQL。

## 项目结构

```text
Timetable-Agent/
├── backend/
│   ├── app/
│   │   ├── api/auth.py          # 登录接口
│   │   ├── models/user.py       # 用户表模型
│   │   ├── schemas/             # 请求和响应模型
│   │   ├── config.py           # 环境变量配置
│   │   ├── database.py         # 数据库连接、会话和基础模型
│   │   └── main.py             # FastAPI 入口与建表
│   ├── .env                   # 本地数据库配置
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── assets/css/         # 全局样式
│   │   ├── layouts/Layout.vue # 管理界面布局
│   │   ├── router/index.js     # 路由配置
│   │   ├── views/              # 登录、注册及管理页面
│   │   ├── App.vue
│   │   └── main.js             # Vue 入口
│   ├── package.json
│   └── vite.config.js
└── README.md
```

## 本地运行

### 环境准备

- Node.js：`^22.18.0 || >=24.12.0`，与前端 `package.json` 要求一致。
- Python：建议使用 3.10 或更高版本，代码使用了 `str | None` 类型语法。
- PostgreSQL：准备可访问的数据库及具有建表权限的账号。

以下命令在项目根目录执行，使用 Windows PowerShell。前后端分别在两个终端启动。

### 启动后端

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

在 `backend/.env` 中配置数据库连接。下面的账号、密码和数据库名均为示例，请替换为本地配置；已有配置时无需覆盖：

```dotenv
DATABASE_URL=postgresql+psycopg://db_user:db_password@localhost:5432/timetable_agent
```

数据库需要提前创建。应用启动时会创建缺失的表，但不会创建数据库，也不会迁移已有表结构。

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

- 服务地址：<http://127.0.0.1:8000>
- Swagger 接口文档：<http://127.0.0.1:8000/docs>
- ReDoc 接口文档：<http://127.0.0.1:8000/redoc>

### 启动前端

在另一个终端中，从项目根目录执行：

```powershell
cd frontend
npm ci
npm run dev
```

默认访问 <http://localhost:5173>，实际地址以 Vite 终端输出为准。访问根路径会跳转到 `/manager/home`；登录和注册页面分别位于 `/login` 和 `/register`。

### 前端常用命令

在 `frontend` 目录执行：

```powershell
npm run build    # 构建，输出到 dist 目录
npm run preview  # 本地预览构建产物，需先构建
npm run format   # 使用 Prettier 格式化 src 目录
```

## 后端接口

### 服务检查

`GET /`

```json
{"message": "Hello FastAPI"}
```

### 用户登录

`POST /api/auth/login`

请求体：

```json
{
  "username": "demo",
  "password": "demo_password"
}
```

成功响应示例：

```json
{
  "code": 200,
  "message": "操作成功",
  "data": {
    "id": 1,
    "username": "demo",
    "name": "测试用户",
    "role": "student",
    "phone": null,
    "email": null,
    "status": 1
  }
}
```

账号或密码错误时返回：

```json
{"code": 400, "message": "账号或密码错误"}
```

这里的 `code` 是响应体中的业务状态码；目前账号或密码错误时 HTTP 状态码仍为 `200`。请求参数不符合模型要求时由 FastAPI 返回校验错误。

项目未提供默认账号、用户初始化脚本或注册接口。测试后端登录前，需要自行向 `users` 表插入用户，必填业务字段为 `username`、`password`、`name` 和 `role`；角色约定为 `student`（学生）或 `admin`（管理员）。

## 当前开发限制

- 前后端尚未联调；Vite 未配置 API 代理，后端未配置 CORS。接入接口时需要配置代理或跨域访问。
- 后端当前直接比较明文密码，未实现密码哈希、Token、会话或权限校验，也未检查用户是否被禁用。
- 前端没有登录路由守卫，管理页面可以直接访问；退出登录仅执行页面跳转。
- `Base.metadata.create_all()` 仅用于创建缺失的表，后续修改数据库结构需要引入迁移方案。

## 后续开发方向

- 实现注册接口、密码哈希和登录认证，并完成前后端联调。
- 补齐设备与用户管理路由，实现实验室、设备及用户的管理接口。
- 实现预约记录、时间冲突检测和角色权限控制。
- 接入 Agent 智能预约与排课逻辑。
