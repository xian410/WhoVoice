import { createRouter, createWebHistory } from 'vue-router'
import HomePage from './views/HomePage.vue'
import SingerDetail from './views/SingerDetail.vue'

const routes = [
  {
    path: '/',
    name: 'Home',
    component: HomePage,
  },
  {
    path: '/celebrities/:name',
    name: 'SingerDetail',
    component: SingerDetail,
    props: true,
  },
  {
    path: '/leaderboard/:name?',
    name: 'Leaderboard',
    component: () => import('./views/LeaderboardPage.vue'),
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

export default router
