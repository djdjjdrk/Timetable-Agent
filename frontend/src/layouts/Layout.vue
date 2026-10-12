<template>
  <div>
    <el-container style="min-height: 100vh">
      <el-header
        style="
          display: flex;
          align-items: center;
          border-bottom: 1px solid #ddd;
          background-color: #fff;
        "
      >
        <div
          style="flex: 1; display: flex; align-items: center; font-size: 24px; font-weight: bold"
        >
          <el-icon :size="40"><House /></el-icon>
          <div style="margin-left: 5px">智能实验室预约系统</div>
        </div>
        <el-dropdown trigger="hover" @command="handleAccountCommand">
          <button class="account-trigger" type="button" aria-label="管理员菜单">
            <el-icon :size="30"><User /></el-icon>
            <span>管理员</span>
            <el-icon><ArrowDown /></el-icon>
          </button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="logout" :icon="SwitchButton">
                退出登录
              </el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </el-header>
      <el-container>
        <el-aside width="220px">
          <el-menu router style="height: 100%" :default-active="route.path">
            <el-menu-item index="/manager/home">
              <el-icon><icon-menu /></el-icon>
              系统首页
            </el-menu-item>
            <el-menu-item index="/manager/lab">
              <el-icon><House /></el-icon>
              实验室管理
            </el-menu-item>
            <el-menu-item index="/manager/equ">
              <el-icon><Setting /></el-icon>
              设备列表管理
            </el-menu-item>
            <el-menu-item index="/manager/user">
              <el-icon><User /></el-icon>
              用户管理
            </el-menu-item>
          </el-menu>
        </el-aside>
        <el-main>
          <router-view />
        </el-main>
      </el-container>
    </el-container>
  </div>
</template>

<script setup>
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Menu as IconMenu, House, Setting, User, ArrowDown, SwitchButton } from '@element-plus/icons-vue'

const route = useRoute()
const router = useRouter()

const handleAccountCommand = async (command) => {
  if (command !== 'logout') return

  await router.replace('/login')
  ElMessage.success('已退出登录')
}
</script>

<style scoped>
.account-trigger {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 0 8px 8px;
  border: none;
  background: transparent;
  color: inherit;
  font: inherit;
  cursor: pointer;
}

.account-trigger:hover,
.account-trigger:focus-visible {
  color: var(--el-color-primary);
}
</style>
