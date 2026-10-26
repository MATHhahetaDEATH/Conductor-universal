import axios from 'axios';

export async function getPluginInfo(
  pluginId: string,
  options?: { [key: string]: any }
) {
  return axios
    .get('/api/web_cli/info', { params: { plugin_id: pluginId }, ...options })
    .then((res) => res.data);
}

export async function suggestCommand(
  body: { input: string },
  options?: { [key: string]: any }
) {
  return axios
    .post('/api/web_cli/suggest', body, options)
    .then((res) => res.data);
}

export async function executeCommand(
  body: { plugin_id: string; input: string },
  options?: { [key: string]: any }
) {
  return axios
    .post('/api/web_cli/execute', body, options)
    .then((res) => res.data);
}
