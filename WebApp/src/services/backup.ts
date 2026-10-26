import axios from 'axios';

export async function getBackupStatus(options?: { [key: string]: any }) {
  return axios.get('/api/prime_backup/status', options).then((res) => res.data);
}

export async function listBackups(options?: { [key: string]: any }) {
  return axios.get('/api/prime_backup/list', options).then((res) => res.data);
}

export async function createBackup(
  body: { comment: string },
  options?: { [key: string]: any }
) {
  return axios
    .post('/api/prime_backup/make', body, options)
    .then((res) => res.data);
}

export async function deleteBackup(
  body: { id: number },
  options?: { [key: string]: any }
) {
  return axios
    .post('/api/prime_backup/delete', body, options)
    .then((res) => res.data);
}

export async function restoreBackup(
  body: { id: number; path: string },
  options?: { [key: string]: any }
) {
  return axios
    .post('/api/prime_backup/restore', body, options)
    .then((res) => res.data);
}
