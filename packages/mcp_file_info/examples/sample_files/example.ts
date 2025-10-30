/**
 * @PURPOSE: 实现前端路由管理和导航守卫功能
 * @OUTLINE:
 *   - class Router: 核心路由管理器
 *   - function setupGuards(): 配置导航守卫
 *   - function handleNavigation(to, from): 处理路由跳转
 *   - function checkPermission(route): 检查路由权限
 * @GOTCHAS:
 *   - 路由守卫必须返回boolean或Promise<boolean>
 *   - 避免在守卫中进行重定向循环
 *   - 异步守卫必须正确处理错误，否则会导致导航卡住
 *   - 全局守卫在组件守卫之前执行
 * @TECH_DEBT:
 *   - TODO: 实现路由懒加载优化
 *   - TODO: 添加路由过渡动画
 *   - TODO: 实现更细粒度的权限控制
 * @DEPENDENCIES:
 *   - 外部: vue-router, pinia
 *   - 内部: @/stores/userStore, @/utils/auth
 * @RELATED: guards/authGuard.ts, guards/permissionGuard.ts
 */

import { createRouter, createWebHistory, RouteRecordRaw } from 'vue-router';
import { useUserStore } from '@/stores/userStore';

/**
 * 路由配置
 */
const routes: RouteRecordRaw[] = [
  {
    path: '/',
    name: 'Home',
    component: () => import('@/views/Home.vue'),
  },
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/Login.vue'),
  },
  {
    path: '/dashboard',
    name: 'Dashboard',
    component: () => import('@/views/Dashboard.vue'),
    meta: { requiresAuth: true },
  },
];

/**
 * 创建路由实例
 */
const router = createRouter({
  history: createWebHistory(),
  routes,
});

/**
 * 设置导航守卫
 */
function setupGuards() {
  router.beforeEach(async (to, from, next) => {
    const userStore = useUserStore();

    // 检查是否需要认证
    if (to.meta.requiresAuth && !userStore.isAuthenticated) {
      next({ name: 'Login', query: { redirect: to.fullPath } });
      return;
    }

    next();
  });
}

// 初始化守卫
setupGuards();

export default router;

