import axios from 'axios'

const api = axios.create({
  baseURL: '/api/trace'
})

export const analyzeTrace = (data) => api.post('/analyze', data).then(res => res.data)
export const getTraceStatus = (sessionId) => api.get(`/status/${sessionId}`).then(res => res.data)
export const getSampleData = () => api.get('/sample').then(res => res.data)

