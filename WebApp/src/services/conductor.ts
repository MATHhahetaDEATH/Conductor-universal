import axios from 'axios';

/** 获取系统状态 GET /api/status */
export async function getSystemStatus(options?: { [key: string]: any }) {
  return axios.get('/api/status', options).then((res) => res.data);
}

/** 执行命令 POST /api/command */
export async function executeCommand(
  body: { command: string },
  options?: { [key: string]: any }
) {
  return axios.post('/api/command', body, options).then((res) => res.data);
}

/** 接收内容结构 POST /api/content */
export async function receiveContent(
  body: { id: string; source: string; payload: any; tags?: string[] },
  options?: { [key: string]: any }
) {
  return axios.post('/api/content', body, options).then((res) => res.data);
}

/** 获取系统插件详情 GET /api/core/plugins */
export async function getPluginsDetail(options?: { [key: string]: any }) {
  return axios.get('/api/core/plugins', options).then((res) => res.data);
}

/** 插件生命周期操作 POST /api/core/plugin/action */
export async function pluginAction(
  body: { plugin_id: string; action: 'reload' | 'unload' | 'load' },
  options?: { [key: string]: any }
) {
  return axios
    .post('/api/core/plugin/action', body, options)
    .then((res) => res.data);
}

/** 列表插件文件 GET /api/core/plugin/files */
export async function getPluginFiles(
  id: string,
  options?: { [key: string]: any }
) {
  return axios
    .get('/api/core/plugin/files', { params: { id }, ...options })
    .then((res) => res.data);
}

/** 读取文件内容 GET /api/core/plugin/file */
export async function getPluginFileContent(
  id: string,
  name: string,
  category: string,
  options?: { [key: string]: any }
) {
  return axios
    .get('/api/core/plugin/file', {
      params: { id, name, category },
      ...options,
    })
    .then((res) => res.data);
}

/** 保存文件内容 POST /api/core/plugin/file */
export async function savePluginFileContent(
  body: { id: string; name: string; category: string; content: string },
  options?: { [key: string]: any }
) {
  return axios
    .post('/api/core/plugin/file', body, options)
    .then((res) => res.data);
}

/** 获取插件日志 GET /api/core/plugin/logs */
export async function getPluginLogs(
  id: string,
  options?: { [key: string]: any }
) {
  return axios
    .get('/api/core/plugin/logs', { params: { id }, ...options })
    .then((res) => res.data);
}

/** 获取插件依赖状态 GET /api/core/dependencies */
export async function getPluginDependencies(options?: { [key: string]: any }) {
  return axios
    .get('/api/core/dependencies', options)
    .then((res) => res.data);
}

/** 安装缺失插件依赖 POST /api/core/dependencies/install */
export async function installPluginDependencies(
  body: { ecosystem: 'all' | 'python' | 'web' },
  options?: { [key: string]: any }
) {
  return axios
    .post('/api/core/dependencies/install', body, options)
    .then((res) => res.data);
}

/** 同步插件依赖到项目清单 POST /api/core/dependencies/sync */
export async function syncPluginDependencies(
  body: { ecosystem: 'all' | 'python' | 'web' },
  options?: { [key: string]: any }
) {
  return axios
    .post('/api/core/dependencies/sync', body, options)
    .then((res) => res.data);
}
