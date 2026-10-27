<template>
  <div>
    <el-card>
      <template #header>
        <div style="font-size: 16px; font-weight: bold">
          课程管理
        </div>
      </template>
      <div style="margin-bottom: 10px">
        <el-input
          v-model="keywords"
          placeholder="按名称 / 代码 / 简介查询"
          style="width: 260px; margin-right: 8px"
          clearable
          @keyup.enter="handleSearch"
          @clear="handleSearch"
        />
        <el-button type="primary" :icon="Search" @click="handleSearch">查询</el-button>
        <el-button type="success" :icon="Plus" @click="handleCreate">新增课程</el-button>
      </div>
      <el-table
        v-loading="loading"
        :header-cell-style="{ backgroundColor: '#f5f7fa', color: '#333' }"
        :data="allData"
        style="width: 100%"
      >
        <el-table-column prop="name" label="课程名称" min-width="140" />
        <el-table-column prop="code" label="课程代码" width="120" />
        <el-table-column prop="description" label="简介" min-width="200" show-overflow-tooltip />
        <el-table-column prop="status" label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="row.status === 1 ? 'success' : 'info'">
              {{ row.status === 1 ? '正常' : '停用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" text bg @click="handleEdit(row)">编辑</el-button>
            <el-button type="danger" text bg @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
    <el-dialog v-model="dialogVisible" :title="form.id ? '编辑课程' : '新增课程'" width="480">
      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        label-width="90px"
        style="padding-right: 20px; padding-top: 8px"
      >
        <el-form-item label="课程名称" prop="name">
          <el-input v-model="form.name" placeholder="例如：数据结构" maxlength="100" />
        </el-form-item>
        <el-form-item label="课程代码" prop="code">
          <el-input v-model="form.code" placeholder="可选，唯一" maxlength="50" />
        </el-form-item>
        <el-form-item label="简介" prop="description">
          <el-input v-model="form.description" type="textarea" :rows="3" />
        </el-form-item>
        <el-form-item label="状态">
          <el-radio-group v-model="form.status">
            <el-radio :value="1">正常</el-radio>
            <el-radio :value="0">停用</el-radio>
          </el-radio-group>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="formLoading" @click="handleSave">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>
<script setup>
defineOptions({ name: 'Course' })
import { Search, Plus } from '@element-plus/icons-vue'
import { nextTick, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { createCourseApi, deleteCourseApi, listCoursesApi, updateCourseApi } from '@/api/course'
const keywords = ref('')
const loading = ref(false)
const allData = ref([])
const dialogVisible = ref(false)
const formRef = ref()
const formLoading = ref(false)
const form = reactive({
  id: null,
  name: '',
  code: '',
  description: '',
  status: 1
})
const rules = {
  name: [{ required: true, whitespace: true, message: '请输入课程名称', trigger: 'blur' }]
}
const resetForm = () => {
  Object.assign(form, {
    id: null,
    name: '',
    code: '',
    description: '',
    status: 1
  })
}
let latestRequest = 0
const load = async () => {
  const requestId = ++latestRequest
  loading.value = true
  try {
    const res = await listCoursesApi({ keywords: keywords.value || undefined })
    if (requestId !== latestRequest) return
    if (res.code === 200) {
      allData.value = res.data || []
    } else {
      allData.value = []
    }
  } catch {
    // 请求拦截器统一展示错误。
    if (requestId === latestRequest) allData.value = []
  } finally {
    if (requestId === latestRequest) loading.value = false
  }
}
const handleSearch = () => {
  load()
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
    name: row.name,
    code: row.code || '',
    description: row.description || '',
    status: row.status
  })
  dialogVisible.value = true
  await nextTick()
  formRef.value?.clearValidate()
}
const handleSave = async () => {
  if (formLoading.value) return
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return
  formLoading.value = true
  try {
    const payload = {
      name: form.name.trim(),
      code: form.code.trim() || null,
      description: form.description.trim() || null,
      status: form.status
    }
    const res = form.id ? await updateCourseApi(form.id, payload) : await createCourseApi(payload)
    if (res.code === 200) {
      dialogVisible.value = false
      ElMessage.success('操作成功')
      await load()
    }
  } catch {
    // 请求拦截器统一展示错误，保留表单以便重试。
  } finally {
    formLoading.value = false
  }
}
const handleDelete = (row) => {
  ElMessageBox.confirm(`确认删除课程「${row.name}」？`, '确认删除', {
    type: 'warning'
  }).then(async () => {
    const res = await deleteCourseApi(row.id)
    if (res.code === 200) {
      ElMessage.success('已删除')
      load()
    }
  }).catch(() => {
    // 取消删除无需提示，请求错误由拦截器统一展示。
  })
}
onMounted(() => {
  load()
})
</script>
