import axios from 'axios'

const api = axios.create({
  baseURL: '/api/fortune'
})

export const analyzeFate = (data) => api.post('/analyze', data).then(res => res.data)
export const getStatus = (sessionId) => api.get(`/status/${sessionId}`).then(res => res.data)
export const getReport = (sessionId) => api.get(`/report/${sessionId}`).then(res => res.data)
export const listMasters = () => api.get('/masters').then(res => res.data)
