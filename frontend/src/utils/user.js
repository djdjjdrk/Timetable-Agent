// 仅供页面 setup 函数使用
import { ref } from 'vue'
import { getUserInfo, setToken, setUserInfo } from './auth'

const userInfo = ref(getUserInfo())

export function useUser() {
  function saveLoginData(data) {
    setToken(data.token)
    setUserInfo(data.user)
    userInfo.value = data.user
  }

  function updateUser(user) {
    setUserInfo(user)
    userInfo.value = user
  }

  function reloadUser() {
    userInfo.value = getUserInfo()
  }

  return { userInfo, saveLoginData, updateUser, reloadUser }
}
