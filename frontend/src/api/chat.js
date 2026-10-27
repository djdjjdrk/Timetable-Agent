import { getToken, logout } from '@/utils/auth'
import router from '@/router'
export async function streamChat(body, onEvent) {
  const baseURL = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '')
  const response = await fetch(`${baseURL}/api/chat/stream`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'text/event-stream',
      Authorization: `Bearer ${getToken() || ''}`
    },
    body: JSON.stringify(body)
  })
  // fetch 不经过 Axios 拦截器，需要自行处理登录失效和 HTTP 错误。
  if (response.status === 401) {
    logout()
    router.push('/login')
    throw new Error('登录状态已失效，请重新登录')
  }
  if (!response.ok) {
    const data = await response.json().catch(() => ({}))
    throw new Error(data.message || `请求失败：HTTP ${response.status}`)
  }
  // 普通 JSON 响应不能按 SSE 解析，即使 HTTP 状态是 200。
  if (!response.headers.get('content-type')?.includes('text/event-stream') || !response.body) {
    throw new Error('服务未返回 SSE 事件流，请检查接口地址和后端日志')
  }
  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  try {
    while (true) {
      const { value, done } = await reader.read()
      // 没有收到 done/error 就断开，不能把半截回答当作已完成。
      if (done) throw new Error('连接已结束，但未收到完成事件，请重新提问')
      buffer += decoder.decode(value, { stream: true })
      const blocks = buffer.split('\n\n')
      buffer = blocks.pop()
      for (const block of blocks) {
        // 本节后端固定输出单行 data: JSON，前六个字符是 "data: "。
        const event = JSON.parse(block.slice(6))
        onEvent(event)
        if (event.type === 'done' || event.type === 'error') return
      }
    }
  } finally {
    await reader.cancel().catch(() => {})
    reader.releaseLock()
  }
}
