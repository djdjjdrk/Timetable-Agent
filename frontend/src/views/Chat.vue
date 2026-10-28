<template>
  <div>
    <el-card>
      <template #header>
        <div style="font-size: 16px; font-weight: bold">
          课程助手
        </div>
      </template>
      <div
        ref="messageBox"
        class="messages"
        aria-live="polite"
        style="
          height: 480px;
          overflow-y: auto;
          padding: 8px 4px;
          background-color: #fafafa;
          border-radius: 6px;
        "
      >
        <div
          v-for="(item, index) in messages"
          :key="index"
          :style="{
            display: 'flex',
            justifyContent: item.role === 'user' ? 'flex-end' : 'flex-start',
            marginBottom: '12px'
          }"
        >
          <div
            :style="{
              maxWidth: '70%',
              padding: '10px 12px',
              borderRadius: '8px',
              backgroundColor: item.role === 'user' ? '#409eff' : '#fff',
              color: item.role === 'user' ? '#fff' : '#333',
              lineHeight: '1.6',
              boxShadow: '0 1px 2px rgba(0, 0, 0, 0.06)'
            }"
          >
            <!-- 当前进行中的一句话，如「正在查询我的课表…」 -->
            <div
              v-if="item.role === 'assistant' && item.status"
              style="margin-bottom: 6px; font-size: 12px; color: #909399"
            >
              {{ item.status }}
            </div>
            <!-- 本轮已发生的过程列表，只展示不回传给后端 -->
            <div
              v-if="item.role === 'assistant' && item.steps?.length"
              style="margin-bottom: 8px; font-size: 12px; color: #909399; line-height: 1.5"
            >
              <div v-for="(step, i) in item.steps" :key="i">· {{ step }}</div>
            </div>
            <div
              v-if="item.role === 'user' && item.content"
              style="white-space: pre-wrap; word-break: break-word"
            >
              {{ item.content }}
            </div>
            <div
              v-else-if="item.content"
              class="chat-md"
              v-html="parseMarkdown(item.content)"
            ></div>
          </div>
        </div>
      </div>
      <!-- 输入框 -->
      <div style="margin-top: 12px; display: flex; gap: 8px; align-items: flex-end">
        <el-input
          v-model="question"
          type="textarea"
          :rows="2"
          aria-label="输入问题"
          placeholder="例如：我明天有什么课？"
          @keydown.enter.exact.prevent="send"
          @keydown.enter.shift.stop
        ></el-input>
        <el-button type="primary" :loading="sending" @click="send">发送</el-button>
      </div>
    </el-card>
  </div>
</template>
<script setup>
import { nextTick, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import { streamChat } from '@/api/chat'
marked.setOptions({ gfm: true, breaks: true })
const question = ref('')
const messages = ref([
  {
    role: 'assistant',
    content: '您好，我是校园课程智能助手。你可以查询自己的课表、检索课程资料或制定学习计划；明确说“保存计划”后，我才会为你保存。',
    status: '',
    steps: []
  }
])
const history = ref([])
const sending = ref(false)
const messageBox = ref(null)
const toolLabels = {
  get_my_schedules: '查询我的课表',
  search_course_docs: '检索课程资料',
  save_study_plan: '保存学习计划'
}
function parseMarkdown(text) {
  return DOMPurify.sanitize(marked.parse(text || ''), { USE_PROFILES: { html: true } })
}
async function scrollToBottom() {
  await nextTick()
  messageBox.value?.scrollTo({ top: messageBox.value.scrollHeight })
}
async function send() {
  const text = question.value.trim()
  // 同一页面一次只发送一个问题，空白输入不发请求。
  if (sending.value || !text) return
  const previousHistory = history.value.map((item) => ({ ...item }))
  messages.value.push({ role: 'user', content: text })
  messages.value.push({ role: 'assistant', content: '', status: '正在连接', steps: [] })
  const reply = messages.value[messages.value.length - 1]
  question.value = ''
  sending.value = true
  scrollToBottom()
  try {
    await streamChat({ question: text, history: previousHistory }, (event) => {
      const label = toolLabels[event.name] || event.name
      // 状态与正文分开显示，文字片段逐段追加。
      if (event.type === 'status') {
        reply.status = event.message
      } else if (event.type === 'token') {
        reply.content += event.content
        reply.status = ''
      // 过程区只追加可读文案，不参与下一轮历史。
      } else if (event.type === 'tool_start') {
        reply.status = `正在${label}`
        reply.steps.push(`开始：${label}`)
      } else if (event.type === 'tool_end') {
        reply.status = `${label}已返回`
        reply.steps.push(`已返回：${label}`)
      // done 校准最终答案，只有成功问答进入历史。
      } else if (event.type === 'done') {
        reply.content = event.answer
        reply.status = ''
        history.value.push(
          { role: 'user', content: text },
          { role: 'assistant', content: event.answer }
        )
      } else if (event.type === 'error') {
        throw new Error(event.message)
      }
      scrollToBottom()
    })
  } catch (error) {
    reply.status = `未完成：${error.message}`
    question.value = text
    ElMessage.error(error.message)
  } finally {
    sending.value = false
    scrollToBottom()
  }
}
</script>
<style scoped>
.chat-md :deep(table) {
  border-collapse: collapse;
  width: 100%;
  margin: 8px 0;
  font-size: 13px;
  display: table;
}
.chat-md :deep(thead),
.chat-md :deep(tbody) {
  display: table-row-group;
}
.chat-md :deep(tr) {
  display: table-row;
}
.chat-md :deep(th),
.chat-md :deep(td) {
  display: table-cell;
  border: 1px solid #dcdfe6;
  padding: 6px 10px;
  text-align: left;
  vertical-align: top;
  word-break: break-word;
}
.chat-md :deep(th) {
  background: #f5f7fa;
  font-weight: 600;
}
.chat-md :deep(p) {
  margin: 0.4em 0;
}
.chat-md :deep(p:first-child) {
  margin-top: 0;
}
.chat-md :deep(p:last-child) {
  margin-bottom: 0;
}
.chat-md :deep(ul),
.chat-md :deep(ol) {
  margin: 0.4em 0;
  padding-left: 1.4em;
}
</style>
