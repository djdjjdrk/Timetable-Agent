import request from '@/utils/request'
export function listCoursesApi(params) {
  return request({
    url: '/api/courses',
    method: 'get',
    params
  })
}
export function getCourseApi(id) {
  return request({
    url: `/api/courses/${id}`,
    method: 'get'
  })
}
export function createCourseApi(data) {
  return request({
    url: '/api/courses',
    method: 'post',
    data
  })
}
export function updateCourseApi(id, data) {
  return request({
    url: `/api/courses/${id}`,
    method: 'put',
    data
  })
}
export function deleteCourseApi(id) {
  return request({
    url: `/api/courses/${id}`,
    method: 'delete'
  })
}
