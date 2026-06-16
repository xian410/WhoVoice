import axios from "axios";

const api = axios.create({
  baseURL: "/api",
  timeout: 60000,
  // 不设默认 Content-Type，让 axios 根据请求体自动判断
});

// 请求拦截器 - 添加认证 token
api.interceptors.request.use((config) => {
  // 如果是 FormData，让 axios 自动设置 multipart/form-data + boundary
  if (config.data instanceof FormData) {
    delete config.headers["Content-Type"];
  }
  const token = localStorage.getItem("token");
  if (token) {
    config.headers.Authorization = `Token ${token}`;
  }
  return config;
});

// 响应拦截器 - 统一错误处理
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem("token");
      window.location.reload();
    }
    console.error("API 错误:", error.response?.status, error.response?.data);
    return Promise.reject(error);
  },
);

export default api;
