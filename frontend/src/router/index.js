import { createRouter, createWebHistory } from 'vue-router'
import { getToken, getUserInfo } from '@/utils/auth'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    { path: '/', redirect: '/manager/home' },
    {
      path: '/manager',
      name: 'Layout',
      component: () => import('@/layouts/Layout.vue'),
      children: [
        { path: 'profile', name: 'Profile', component: () => import('@/views/Profile.vue') },
        { path: 'password', name: 'Password', component: () => import('@/views/Password.vue') },
        { path: 'home', name: 'Home', component: () => import('@/views/Home.vue') },
        { path: 'chat', name: 'Chat', component: () => import('@/views/Chat.vue') },
        { path: 'timetable', redirect: '/manager/schedule' },
        { path: 'schedule', name: 'Schedule', component: () => import('@/views/Schedule.vue') },
        {
          path: 'schedule-manage',
          name: 'ScheduleManage',
          component: () => import('@/views/ScheduleManage.vue'),
          meta: { requiresAdmin: true }
        },
        { path: 'study-plan', name: 'StudyPlan', component: () => import('@/views/StudyPlan.vue') },
        {
          path: 'course',
          name: 'Course',
          component: () => import('@/views/Course.vue'),
          meta: { requiresAdmin: true }
        },
        { path: 'documents', name: 'Documents', component: () => import('@/views/Documents.vue') },
        {
          path: 'user',
          name: 'User',
          component: () => import('@/views/User.vue'),
          meta: { requiresAdmin: true }
        }
      ]
    },
    { path: '/login', name: 'Login', component: () => import('@/views/Login.vue') },
    { path: '/register', name: 'Register', component: () => import('@/views/Register.vue') }
  ]
})

router.beforeEach((to) => {
  const token = getToken()
  if (to.path === '/login' || to.path === '/register') {
    return true
  }
  if (!token) return '/login'
  if (to.meta.requiresAdmin && getUserInfo()?.role !== 'admin') {
    return '/manager/home'
  }
  return true
})

export default router
