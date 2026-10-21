# Apifox 接口测试

服务地址：`http://127.0.0.1:8000`

## 1. 服务检查

`GET http://127.0.0.1:8000/`

不传参数。

## 2. 登录

`POST http://127.0.0.1:8000/api/auth/login`

Body 选择 JSON，填写数据库中已有账号的用户名和密码：

```json
{
  "username": "你的用户名",
  "password": "你的密码"
}
```

复制成功响应中的 `data.token`，用于下一个接口。

## 3. 获取当前用户信息

`GET http://127.0.0.1:8000/api/user/me`

Header：

```text
Authorization: Bearer 登录返回的token
```

不传 Body。

## 4. 管理员查询用户列表

`GET http://127.0.0.1:8000/api/user/list?page=1&page_size=10`

Header 使用管理员登录返回的 Token：

```text
Authorization: Bearer 管理员登录返回的token
```

查询参数：

| 参数 | 默认值 | 说明 |
| --- | --- | --- |
| `page` | `1` | 页码，至少为 1 |
| `page_size` | `10` | 每页条数，范围 1～100 |
| `keywords` | 不传 | 按账号或名称模糊查询，不区分英文大小写 |

例如查询账号或名称包含 `admin` 的用户：

`GET http://127.0.0.1:8000/api/user/list?page=1&page_size=10&keywords=admin`

成功响应的 `data.list` 为用户数组，按 ID 倒序排列；`data.total` 为符合搜索条件的总数。用户信息不包含密码。

- 无搜索结果或超出最后一页时，`data.list` 为 `[]`。
- 学生 Token 请求时，返回业务码 `403`、消息 `无权限访问`（按现有业务异常约定，HTTP 状态为 `200`）。
- 未登录、Token 无效或账号被禁用时，返回 HTTP `401`。
- 页码或每页条数无效时，返回 HTTP `422`。

前端使用管理员账号登录后，点击“用户管理”进入 `/manager/user`。可使用查询按钮、回车或清空输入框查询，查询时会回到第一页；学生不显示该菜单，直接访问该路由会返回首页。

## 5. 管理员新增用户

`POST http://127.0.0.1:8000/api/user`

Header 使用管理员 Token，Body 选择 JSON：

```json
{
  "username": "apifox_student_001",
  "password": "Test123456",
  "name": "联调学生",
  "role": "student",
  "status": 1,
  "email": "student001@example.com",
  "phone": "13800000001",
  "avatar": "https://example.com/avatar.png"
}
```

字段说明：

| 字段 | 说明 |
| --- | --- |
| `username` | 必填，账号唯一；新增后不可通过编辑接口修改 |
| `password` | 3～10 位；接口可省略，默认密码为 `123`；密码在服务端加密保存，响应不包含密码 |
| `name` | 可省略，缺省时使用 `username` |
| `role` | `student`（学生）或 `admin`（管理员） |
| `status` | `1`（启用）或 `0`（禁用） |
| `email`、`phone`、`avatar` | 可选的邮箱、手机号和头像地址 |

成功后记录返回用户的 `id`，供编辑、删除使用。最小请求可用以下内容验证默认名称和密码：

```json
{
  "username": "apifox_default_001"
}
```

使用新账号和密码调用登录接口；最小请求创建的账号使用密码 `123` 登录。重复提交同一 `username` 应提示账号已存在，不能产生重复用户。请使用专门的联调账号，避免覆盖已有账号。

## 6. 管理员编辑用户

`PUT http://127.0.0.1:8000/api/user/{user_id}`

将 `{user_id}` 替换为新增用户的 `id`，Header 使用管理员 Token，Body 选择 JSON：

```json
{
  "name": "联调学生（已修改）",
  "email": "student001-updated@example.com",
  "phone": "13800000002",
  "avatar": "https://example.com/avatar-updated.png",
  "role": "student",
  "status": 1
}
```

可编辑 `name`、`email`、`phone`、`avatar`、`role`、`status`，以及可选的 `password`；账号 `username` 不可编辑。角色仅支持 `student`、`admin`，状态仅支持 `0`、`1`，非法值应返回参数校验错误。

编辑时省略 `password`、传 `null` 或传空字符串 `""`，均保留原密码。要重置密码，在编辑请求中增加非空密码，例如：

```json
{
  "password": "Changed456"
}
```

验证更新后，原密码无法登录，新密码可以登录。将 `status` 改为 `0` 后，该用户不能登录，已有 Token 请求受保护接口也应返回 HTTP `401`；管理员可将状态改回 `1` 恢复账号。

`PUT /api/user/me` 仅用于当前用户修改自己的 `name`、`email`、`phone`、`avatar`，不支持修改 `username`、`role`、`status` 或 `password`。用户自行修改密码使用 `PUT /api/user/password`，提交 `old_password` 和 `new_password`；管理员重置其他用户密码使用本节的管理员编辑接口。

## 7. 管理员删除用户

`DELETE http://127.0.0.1:8000/api/user/{user_id}`

将 `{user_id}` 替换为待删除用户的 `id`，Header 使用管理员 Token，不传 Body。删除成功后，用户应从列表中消失，该账号无法登录，已有 Token 请求受保护接口返回 HTTP `401`。

禁止删除当前登录的管理员账号。编辑或删除不存在的用户应返回用户不存在的业务错误。学生 Token 请求新增、编辑、删除接口时，均返回业务码 `403`、消息 `无权限访问`（HTTP 状态为 `200`）；未登录、Token 无效或账号被禁用时返回 HTTP `401`。

## 8. 页面与接口联调顺序

1. 使用管理员账号登录，进入“用户管理”，点击“新增用户”，填写账号、名称、密码、角色、状态及可选联系方式，保存后确认列表出现新用户。
2. 使用新账号登录，确认其密码和角色生效；另通过接口省略密码、名称创建账号，验证默认密码 `123` 和默认名称与账号一致（页面新增时要求填写密码和名称）。
3. 回到管理员页面，点击该用户行的“编辑”，确认账号不可编辑；修改名称、邮箱、手机号、头像并保存，确认列表与用户信息更新。
4. 编辑时不填密码，并分别通过接口验证 `password: null`、`password: ""`；原密码应始终有效。再填写新密码保存，确认旧密码失效、新密码有效。
5. 将角色切换为 `admin`，重新登录确认用户管理入口和接口权限生效；恢复为 `student` 后，确认学生没有用户管理权限。避免修改当前操作管理员的角色，以便继续联调。
6. 将测试账号禁用，验证登录失败和已有 Token 失效；重新启用后验证恢复正常。
7. 点击测试用户行的“删除”，先取消确认以验证无变化，再确认删除，检查列表刷新、账号无法登录及原 Token 失效。若删除当前页最后一条记录，确认页面仍能显示有效分页。
8. 使用重复账号新增、非法角色或状态编辑、不存在的用户 ID 编辑/删除、当前管理员 ID 删除及学生 Token 调用增删改，确认均被拒绝，且数据未被意外修改。

联调仅操作本次创建的测试用户；结束后删除剩余测试账号。

## 自动化回归测试

在 `backend` 目录执行（沿用本地 `.env` 配置）：

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

测试使用独立的 SQLite 内存数据库和测试密钥，不读取或修改业务数据库中的用户数据。覆盖用户分页与搜索、管理员增删改鉴权、账号重复、用户不存在、禁止删除当前账号、字段与角色/状态校验、默认名称及密码、密码保留与重置、禁用和删除后的认证失效，以及响应不泄漏密码。个人资料更新的字段限制也纳入回归，防止通过 `/me` 修改角色、状态或密码。
