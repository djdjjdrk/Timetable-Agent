import request from '@/utils/request'

export function listDocumentsApi() {
  return request({ url: '/api/documents', method: 'get' })
}

export function uploadDocumentsApi(files) {
  const data = new FormData()
  for (const file of files) {
    data.append('files', file)
  }
  return request({ url: '/api/documents', method: 'post', data, timeout: 0 })
}

export function previewDocumentApi(id) {
  // 预览错误由当前弹窗处理，避免过期请求弹出错误提示。
  return request({ url: `/api/documents/${id}/preview`, method: 'get', silentError: true })
}

export function deleteDocumentApi(id) {
  return request({ url: `/api/documents/${id}`, method: 'delete' })
}

export function reingestDocumentApi(id) {
  return request({ url: `/api/documents/${id}/reingest`, method: 'post', timeout: 0 })
}
