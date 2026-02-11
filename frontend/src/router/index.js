import { createRouter, createWebHistory } from 'vue-router'
import TraceView from '../views/TraceView.vue'

const routes = [
  {
    path: '/',
    name: 'Trace',
    component: TraceView
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router
