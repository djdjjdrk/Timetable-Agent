<template>
  <div>
    <el-card>
      <template #header>
        <div style="font-size: 16px; font-weight: bold">文档管理</div>
      </template>
      <el-alert v-if="!isAdmin" title="仅管理员可以管理课程资料" type="warning" :closable="false" />
      <template v-else>
        <div style="margin-bottom: 12px">
          <el-upload
            ref="uploadRef"
            v-model:file-list="fileList"
            :auto-upload="false"
            :disabled="uploadLoading"
            accept=".txt,.md,.pdf,.docx"
            multiple
          >
            <el-button :disabled="uploadLoading">选择文件</el-button>
          </el-upload>
          <el-button
            type="primary"
            style="margin-top: 12px"
            :loading="uploadLoading"
            :disabled="fileList.length === 0"
            @click="handleUpload"
          >上传并入库</el-button>
          <div style="margin-top: 6px; color: #909399; font-size: 12px">
            支持 .txt / .md / .pdf / .docx，单个文件不超过 100 MiB。同名不可重复；扫描版 PDF 可能抽不出文字。
            同一批中任一文件上传或入库失败，整批撤销。
          </div>
        </div>
        <el-table
          v-loading="loading"
          :data="pageData"
          :header-cell-style="{ backgroundColor: '#f5f7fa', color: '#333' }"
          style="width: 100%"
        >
          <el-table-column prop="original_name" label="文件名称" min-width="220" show-overflow-tooltip />
          <el-table-column label="类型" width="100">
            <template #default="{ row }">{{ row.ext?.slice(1).toUpperCase() }}</template>
          </el-table-column>
          <el-table-column prop="ingested" label="已入库" width="90">
            <template #default="{ row }">
              <el-tag :type="row.ingested ? 'success' : 'info'" size="small">
                {{ row.ingested ? '是' : '否' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="大小" width="120">
            <template #default="{ row }">{{ formatSize(row.size) }}</template>
          </el-table-column>
          <el-table-column label="创建时间" min-width="180">
            <template #default="{ row }">{{ formatTime(row.create_time) }}</template>
          </el-table-column>
          <el-table-column label="操作" width="290" fixed="right">
            <template #default="{ row }">
              <el-button type="primary" text bg @click="handlePreview(row)">预览</el-button>
              <el-button
                type="primary"
                text
                bg
                size="small"
                :loading="reingestLoadingId === row.id"
                @click="handleReingest(row)"
              >重新入库</el-button>
              <el-button type="danger" text bg :loading="deletingId === row.id" @click="handleDelete(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
        <el-pagination
          v-model:current-page="currentPage"
          v-model:page-size="pageSize"
          :page-sizes="[10, 20, 50]"
          :total="allData.length"
          layout="total, sizes, prev, pager, next"
          style="margin-top: 16px; justify-content: flex-end; flex-wrap: wrap"
          @size-change="currentPage = 1"
        />
      </template>
    </el-card>
    <el-dialog
      v-model="previewVisible"
      :title="previewTitle"
      width="min(800px, 92vw)"
      @update:model-value="invalidatePreview"
    >
      <div v-loading="previewLoading" style="min-height: 120px">
        <el-alert v-if="previewError" :title="previewError" type="error" :closable="false" />
        <template v-else-if="!previewLoading">
          <div style="color: #909399; margin-bottom: 12px">共 {{ previewCharCount }} 个字符</div>
          <pre class="preview-text">{{ previewText }}</pre>
        </template>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useUser } from '@/utils/user'
import { deleteDocumentApi, listDocumentsApi, previewDocumentApi, reingestDocumentApi, uploadDocumentsApi } from '@/api/document'

defineOptions({ name: 'Documents' })
const { userInfo } = useUser()
const isAdmin = computed(() => userInfo.value?.role === 'admin')
const uploadRef = ref()
const fileList = ref([])
const uploadLoading = ref(false)
const loading = ref(false)
const allData = ref([])
const currentPage = ref(1)
const pageSize = ref(10)
const deletingId = ref(null)
const reingestLoadingId = ref(null) // 正在重新入库的文档 ID，控制对应按钮的加载状态
const pageData = computed(() => allData.value.slice((currentPage.value - 1) * pageSize.value, currentPage.value * pageSize.value))
const previewVisible = ref(false)
const previewTitle = ref('资料预览')
const previewText = ref('')
const previewCharCount = ref(0)
const previewError = ref('')
const previewLoading = ref(false)
let previewRequestId = 0
let listRequestId = 0

const formatSize = (size) => {
  if (size < 1024) return `${size} B`
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KiB`
  return `${(size / (1024 * 1024)).toFixed(1)} MiB`
}
const formatTime = (value) => value ? value.replace('T', ' ').split('.')[0] : '-'

const load = async () => {
  if (!isAdmin.value) return
  const requestId = ++listRequestId
  loading.value = true
  try {
    const res = await listDocumentsApi()
    if (requestId !== listRequestId) return
    if (res.code === 200) {
      allData.value = res.data || []
      currentPage.value = Math.min(currentPage.value, Math.max(1, Math.ceil(allData.value.length / pageSize.value)))
    }
  } catch {
    // 请求拦截器统一展示错误。
  } finally {
    if (requestId === listRequestId) loading.value = false
  }
}

const handleUpload = async () => {
  if (!isAdmin.value || uploadLoading.value) return
  const files = fileList.value.map((item) => item.raw)
  if (!files.length || files.some((file) => !file)) {
    ElMessage.warning('请先选择要上传的文件')
    return
  }
  uploadLoading.value = true
  try {
    const res = await uploadDocumentsApi(files)
    if (res.code === 200) {
      uploadRef.value?.clearFiles()
      fileList.value = []
      ElMessage.success('上传并入库成功')
      currentPage.value = 1
      await load()
    }
  } catch {
    // 上传失败保留选择列表，便于调整后重试。
  } finally {
    uploadLoading.value = false
  }
}

const invalidatePreview = (visible) => {
  if (!visible) {
    ++previewRequestId
    previewLoading.value = false
  }
}
const handlePreview = async (row) => {
  if (!isAdmin.value) return
  const requestId = ++previewRequestId
  previewTitle.value = row.original_name
  previewText.value = ''
  previewCharCount.value = 0
  previewError.value = ''
  previewLoading.value = true
  previewVisible.value = true
  try {
    const res = await previewDocumentApi(row.id)
    if (requestId !== previewRequestId) return
    if (res.code === 200) {
      previewText.value = res.data.text
      previewCharCount.value = res.data.char_count
    } else {
      previewError.value = res.message || '无法读取文档'
    }
  } catch (err) {
    if (requestId !== previewRequestId) return
    previewError.value = err.response?.data?.message || err.message || '无法读取文档，请稍后重试'
  } finally {
    if (requestId === previewRequestId) previewLoading.value = false
  }
}

const handleReingest = async (row) => {
  // 已有一份资料在入库时，不重复发起新的入库请求。
  if (!isAdmin.value || reingestLoadingId.value !== null) return
  reingestLoadingId.value = row.id
  try {
    const res = await reingestDocumentApi(row.id)
    if (res.code === 200) {
      ElMessage.success(`「${row.original_name}」已重新入库`)
    }
  } catch {
    // 请求拦截器已提示网络或 HTTP 错误。
  } finally {
    reingestLoadingId.value = null
    // 失败时原文件仍在，但状态可能由“是”变成“否”，因此也刷新列表。
    await load()
  }
}

const handleDelete = async (row) => {
  if (!isAdmin.value || deletingId.value !== null) return
  try {
    await ElMessageBox.confirm(`确认删除文档「${row.original_name}」及其原文件和向量片段？`, '确认删除', { type: 'warning' })
  } catch {
    return
  }
  deletingId.value = row.id
  try {
    const res = await deleteDocumentApi(row.id)
    if (res.code === 200) {
      ElMessage.success('已删除')
    }
  } catch {
    // 请求拦截器统一展示错误。
  } finally {
    deletingId.value = null
    await load() // 删除失败也可能已清理向量，需要同步最新入库状态。
  }
}

onMounted(load)
onBeforeUnmount(() => {
  ++previewRequestId
  ++listRequestId
})
</script>

<style scoped>
.preview-text {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  max-height: 60vh;
  overflow-y: auto;
  font-family: inherit;
  line-height: 1.7;
  margin: 0;
}
</style>
