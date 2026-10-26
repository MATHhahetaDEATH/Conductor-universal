import axios from 'axios';

export async function sendWebLog(
  body: { level: string; message: string },
  options?: { [key: string]: any }
) {
  return axios.post('/api/logs/web', body, options).then((res) => res.data);
}
