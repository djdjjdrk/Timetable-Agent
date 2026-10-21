<template>
  <div>
    <el-card>
      <template #header>
        <div style="font-size: 16px; font-weight: bold">用户管理</div>
      </template>
      <div style="margin-bottom: 10px">
        <el-input
          v-model="params.keywords"
          placeholder="请输入账号或名称查询"
          style="width: 240px; margin-right: 8px"
          clearable
          @keyup.enter="handleSearch"
          @clear="handleSearch"
        />
        <el-button type="primary" :icon="Search" @click="handleSearch">查询</el-button>
        <el-button type="success" :icon="Plus" @click="handleCreate">新增</el-button>
      </div>

      <el-table
        v-loading="loading"
        :header-cell-style="{ backgroundColor: '#f5f7fa', color: '#333' }"
        :data="tableData"
        style="width: 100%"
        empty-text="暂无用户数据"
      >
        <el-table-column prop="username" label="账号" />
        <el-table-column prop="name" label="名称" />
        <el-table-column prop="avatar" label="头像">
          <template #default="{ row }">
            <div style="min-height: 50px">
              <img
                v-if="row.avatar"
                :src="row.avatar"
                alt="用户头像"
                style="
                  display: block;
                  width: 50px;
                  height: 50px;
                  border-radius: 50%;
                  object-fit: cover;
                "
              />
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="email" label="邮箱" />
        <el-table-column prop="phone" label="手机号" />
        <el-table-column prop="role" label="角色" width="100">
          <template #default="{ row }">
            {{ row.role === 'admin' ? '管理员' : '学生' }}
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.status === 1 ? 'success' : 'danger'">
              {{ row.status === 1 ? '正常' : '禁用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" text bg @click="handleEdit(row)">编辑</el-button>
            <el-button
              type="danger"
              text
              bg
              :disabled="row.id === userInfo?.id || deletingId !== null"
              :loading="deletingId === row.id"
              :title="row.id === userInfo?.id ? '不能删除当前登录的账号' : '删除用户'"
              @click="handleDelete(row)"
              >删除</el-button
            >
          </template>
        </el-table-column>
      </el-table>

      <div style="margin-top: 10px; display: flex; justify-content: flex-end">
        <el-pagination
          v-model:current-page="params.page"
          v-model:page-size="params.pageSize"
          :total="total"
          background
          layout="total, prev, pager, next"
          @current-change="load"
        />
      </div>
    </el-card>

    <el-dialog
      v-model="dialogVisible"
      :title="form.id === null ? '新增用户' : '编辑用户'"
      width="450px"
      style="max-width: calc(100vw - 32px)"
      :close-on-click-modal="!formLoading"
      :close-on-press-escape="!formLoading"
      :show-close="!formLoading"
      :before-close="handleBeforeClose"
      @closed="resetForm"
    >
      <el-form
        ref="formRef"
        :rules="rules"
        :model="form"
        :disabled="formLoading"
        label-width="80px"
        style="padding-right: 20px"
        @submit.prevent="handleSave"
      >
        <el-form-item label="账号" prop="username">
          <el-input
            v-model.trim="form.username"
            :disabled="form.id !== null"
            placeholder="请输入账号"
            autocomplete="off"
          />
        </el-form-item>
        <el-form-item label="密码" prop="password" :required="form.id === null">
          <el-input
            v-model="form.password"
            type="password"
            show-password
            :placeholder="form.id === null ? '请输入3-10位密码' : '留空保留原密码'"
            autocomplete="new-password"
          />
        </el-form-item>
        <el-form-item label="名称" prop="name">
          <el-input v-model.trim="form.name" placeholder="请输入名称" />
        </el-form-item>
        <el-form-item label="角色" prop="role">
          <el-select v-model="form.role" style="width: 100%">
            <el-option label="学生" value="student" />
            <el-option label="管理员" value="admin" />
          </el-select>
        </el-form-item>
        <el-form-item label="邮箱" prop="email">
          <el-input v-model.trim="form.email" placeholder="请输入邮箱（可选）" />
        </el-form-item>
        <el-form-item label="手机号" prop="phone">
          <el-input v-model.trim="form.phone" placeholder="请输入手机号（可选）" />
        </el-form-item>
        <el-form-item label="头像地址" prop="avatar">
          <el-input v-model.trim="form.avatar" placeholder="请输入头像图片地址（可选）" />
        </el-form-item>
        <el-form-item label="状态" prop="status">
          <el-radio-group v-model="form.status">
            <el-radio :value="1">正常</el-radio>
            <el-radio :value="0">禁用</el-radio>
          </el-radio-group>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button :disabled="formLoading" @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="formLoading" @click="handleSave">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { createUserApi, deleteUserApi, getUserPageList, updateUserApi } from '@/api/user'
import { ref, reactive, nextTick, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search, Plus } from '@element-plus/icons-vue'
import { useUser } from '@/utils/user'
import { logout } from '@/utils/auth'
import router from '@/router'

const { userInfo, updateUser, reloadUser } = useUser()
const params = reactive({ page: 1, pageSize: 10, keywords: '' })
const loading = ref(false)
const tableData = ref([])
const total = ref(0)
const dialogVisible = ref(false)
const formRef = ref()
const formLoading = ref(false)
const deletingId = ref(null)
const emptyForm = () => ({
  id: null,
  username: '',
  password: '',
  name: '',
  role: 'student',
  email: '',
  phone: '',
  avatar: '',
  status: 1
})
const form = reactive(emptyForm())
const validatePassword = (_rule, value, callback) => {
  if (!value && form.id !== null) return callback()
  if (!value) return callback(new Error('请输入密码'))
  const length = [...value].length
  if (length < 3 || length > 10) return callback(new Error('密码是3-10位'))
  callback()
}
const rules = {
  username: [{ required: true, whitespace: true, message: '请输入账号', trigger: 'blur' }],
  password: [{ validator: validatePassword, trigger: 'blur' }],
  name: [{ required: true, whitespace: true, message: '请输入名称', trigger: 'blur' }],
  role: [{ required: true, message: '请选择角色', trigger: 'change' }],
  email: [{ type: 'email', message: '邮箱格式错误', trigger: 'blur' }],
  phone: [{ pattern: /^1[3-9]\d{9}$/, message: '手机号格式错误', trigger: 'blur' }]
}
let latestRequest = 0

const load = async () => {
  const requestId = ++latestRequest
  loading.value = true
  try {
    const res = await getUserPageList({
      page: params.page,
      page_size: params.pageSize,
      keywords: params.keywords.trim()
    })
    if (requestId !== latestRequest) return
    tableData.value = res.code === 200 ? (res.data?.list ?? []) : []
    total.value = res.code === 200 ? (res.data?.total ?? 0) : 0
    const lastPage = Math.max(1, Math.ceil(total.value / params.pageSize))
    if (res.code === 200 && params.page > lastPage) {
      params.page = lastPage
      await load()
    }
  } catch {
    // 请求拦截器统一展示错误，清空数据以免误显示上次查询的结果。
    if (requestId === latestRequest) {
      tableData.value = []
      total.value = 0
    }
  } finally {
    if (requestId === latestRequest) loading.value = false
  }
}

const resetForm = () => {
  Object.assign(form, emptyForm())
  formRef.value?.clearValidate()
}

const handleCreate = async () => {
  resetForm()
  dialogVisible.value = true
  await nextTick()
  formRef.value?.clearValidate()
}

const handleEdit = async (row) => {
  resetForm()
  Object.assign(form, {
    id: row.id,
    username: row.username,
    name: row.name ?? '',
    role: row.role,
    email: row.email ?? '',
    phone: row.phone ?? '',
    avatar: row.avatar ?? '',
    status: row.status
  })
  dialogVisible.value = true
  await nextTick()
  formRef.value?.clearValidate()
}

const handleBeforeClose = (done) => {
  if (!formLoading.value) done()
}

const handleDelete = async (row) => {
  if (row.id === userInfo.value?.id || deletingId.value !== null) return
  deletingId.value = row.id
  try {
    await ElMessageBox.confirm(`确认删除用户 [${row.username}] ？`, '确认删除', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消'
    })
    const res = await deleteUserApi(row.id)
    if (res.code === 200) {
      ElMessage.success('删除用户成功')
      await load()
    }
  } catch {
    // 关闭确认框无需提示，请求错误由 request.js 统一展示。
  } finally {
    deletingId.value = null
  }
}

const handleSave = async () => {
  if (formLoading.value) return
  formLoading.value = true
  try {
    const valid = await formRef.value?.validate().catch(() => false)
    if (!valid) return
    const payload = {
      name: form.name,
      role: form.role,
      email: form.email,
      phone: form.phone,
      avatar: form.avatar,
      status: form.status
    }
    if (form.password) payload.password = form.password
    const isEdit = form.id !== null
    const res = isEdit
      ? await updateUserApi(form.id, payload)
      : await createUserApi({ ...payload, username: form.username })
    if (res.code !== 200) return
    dialogVisible.value = false
    ElMessage.success(isEdit ? '修改用户成功' : '新增用户成功')
    if (isEdit && form.id === userInfo.value?.id) {
      updateUser(res.data)
      if (res.data.status !== 1) {
        logout()
        reloadUser()
        await router.replace('/login')
        return
      }
      if (res.data.role !== 'admin') {
        await router.replace('/manager/home')
        return
      }
    }
    await load()
  } catch {
    // 请求错误由 request.js 统一展示，保留表单以便修改后重试。
  } finally {
    formLoading.value = false
  }
}

const handleSearch = () => {
  params.page = 1
  load()
}

onMounted(load)
</script>
