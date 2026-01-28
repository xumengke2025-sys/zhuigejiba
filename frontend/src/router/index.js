import { createRouter, createWebHistory } from 'vue-router'
import Home from '../views/Home.vue'
import FortuneView from '../views/FortuneView.vue'

const routes = [
  {
    path: '/',
    name: 'Home',
    component: Home
  },
  {
    path: '/fortune',
    name: 'Fortune',
    component: FortuneView
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router
