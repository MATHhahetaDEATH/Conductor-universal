import './style/global.less';
import React, { useEffect } from 'react';
import ReactDOM from 'react-dom';
import { createStore } from 'redux';
import { Provider } from 'react-redux';
import { ConfigProvider } from '@arco-design/web-react';
import zhCN from '@arco-design/web-react/es/locale/zh-CN';
import enUS from '@arco-design/web-react/es/locale/en-US';
import { BrowserRouter, Switch, Route } from 'react-router-dom';
import axios from 'axios';
import rootReducer from './store';
import PageLayout from './layout';
import { GlobalContext } from './context';
import Login from './pages/login';
import checkLogin from './utils/checkLogin';
import changeTheme from './utils/changeTheme';
import useStorage from './utils/useStorage';
import { sendWebLog } from './services/logs';
import './mock';

const store = createStore(rootReducer);

// Mobile login hands the authenticated session to the web app through the URL hash.
// Consume it before React's login check runs so the app cannot redirect to /login first.
const mobileTokenPrefix = '#conductor-token=';
if (window.location.hash.startsWith(mobileTokenPrefix)) {
  const token = decodeURIComponent(window.location.hash.slice(mobileTokenPrefix.length));
  if (token) {
    localStorage.setItem('conductorToken', token);
    localStorage.setItem('userStatus', 'login');
    window.history.replaceState(
      null,
      document.title,
      `${window.location.pathname}${window.location.search}`
    );
  }
}

axios.interceptors.request.use((config) => {
  const token = localStorage.getItem('conductorToken');
  if (token) {
    config.headers = {
      ...(config.headers || {}),
      Authorization: `Bearer ${token}`,
    };
  }
  return config;
});

axios.interceptors.response.use(
  (response) => response,
  (error) => {
    if (
      error?.response?.status === 401 &&
      window.location.pathname.replace(/\//g, '') !== 'login'
    ) {
      localStorage.setItem('userStatus', 'logout');
      localStorage.removeItem('conductorToken');
      window.location.pathname = '/login';
    }
    return Promise.reject(error);
  }
);

window.addEventListener('error', (event) => {
  sendWebLog({
    level: 'ERROR',
    message: `${event.message} (${event.filename}:${event.lineno}:${event.colno})`,
  }).catch(() => undefined);
});

window.addEventListener('unhandledrejection', (event) => {
  sendWebLog({
    level: 'ERROR',
    message: `Unhandled promise rejection: ${String(event.reason)}`,
  }).catch(() => undefined);
});

function Index() {
  const [lang, setLang] = useStorage('arco-lang', 'en-US');
  const [theme, setTheme] = useStorage('arco-theme', 'light');

  function getArcoLocale() {
    switch (lang) {
      case 'zh-CN':
        return zhCN;
      case 'en-US':
        return enUS;
      default:
        return zhCN;
    }
  }

  function fetchUserInfo() {
    store.dispatch({
      type: 'update-userInfo',
      payload: { userLoading: true },
    });
    axios
      .get('/api/user/userInfo')
      .then((res) => {
        store.dispatch({
          type: 'update-userInfo',
          payload: { userInfo: res.data, userLoading: false },
        });
      })
      .catch(() => {
        store.dispatch({
          type: 'update-userInfo',
          payload: { userLoading: false },
        });
      });
  }

  useEffect(() => {
    if (checkLogin()) {
      fetchUserInfo();
    } else if (window.location.pathname.replace(/\//g, '') !== 'login') {
      window.location.pathname = '/login';
    }
  }, []);

  useEffect(() => {
    changeTheme(theme);
  }, [theme]);

  const contextValue = {
    lang,
    setLang,
    theme,
    setTheme,
  };

  return (
    <BrowserRouter>
      <ConfigProvider
        locale={getArcoLocale()}
        componentConfig={{
          Card: {
            bordered: false,
          },
          List: {
            bordered: false,
          },
          Table: {
            border: false,
          },
        }}
      >
        <Provider store={store}>
          <GlobalContext.Provider value={contextValue}>
            <Switch>
              <Route path="/login" component={Login} />
              <Route path="/" component={PageLayout} />
            </Switch>
          </GlobalContext.Provider>
        </Provider>
      </ConfigProvider>
    </BrowserRouter>
  );
}

ReactDOM.render(<Index />, document.getElementById('root'));
