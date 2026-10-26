export function authHeaders(headers?: HeadersInit): Record<string, string> {
  const result: Record<string, string> = {};
  if (headers instanceof Headers) {
    headers.forEach((value, key) => { result[key] = value; });
  } else if (Array.isArray(headers)) {
    headers.forEach(([key, value]) => { result[key] = value; });
  } else if (headers) {
    Object.assign(result, headers);
  }
  const token = localStorage.getItem('conductorToken');
  if (token && !Object.keys(result).some((key) => key.toLowerCase() === 'authorization')) {
    result.Authorization = `Bearer ${token}`;
  }
  return result;
}

export async function authorizedFetch(input: RequestInfo | URL, init: RequestInit = {}) {
  const headers = authHeaders(init.headers);
  if (typeof init.body === 'string' && !Object.keys(headers).some((key) => key.toLowerCase() === 'content-type')) {
    headers['Content-Type'] = 'application/json';
  }
  const response = await fetch(input, { ...init, headers });
  if (response.status === 401 && window.location.pathname !== '/login') {
    localStorage.removeItem('conductorToken');
    localStorage.setItem('userStatus', 'logout');
    window.location.assign('/login');
  }
  return response;
}

export async function requestJson<T = any>(input: RequestInfo | URL, init: RequestInit = {}): Promise<T> {
  const response = await authorizedFetch(input, init);
  const payload = await response.json().catch(() => ({}));
  if (!response.ok || payload?.success === false) {
    const error = new Error(payload?.errorMessage || payload?.msg || `Request failed (${response.status})`) as Error & { status?: number };
    error.status = response.status;
    throw error;
  }
  return payload?.data as T;
}
