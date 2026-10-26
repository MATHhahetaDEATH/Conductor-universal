import React, { useContext, useMemo } from 'react';
import {
  Tooltip,
  Input,
  Avatar,
  Select,
  Dropdown,
  Menu,
  Divider,
  Message,
  Button,
} from '@arco-design/web-react';
import {
  IconLanguage,
  IconNotification,
  IconSunFill,
  IconMoonFill,
  IconUser,
  IconSettings,
  IconPoweroff,
  IconLoading,
} from '@arco-design/web-react/icon';
import { useHistory } from 'react-router-dom';
import { useSelector } from 'react-redux';
import { GlobalState } from '@/store';
import { GlobalContext } from '@/context';
import useLocale from '@/utils/useLocale';
import Logo from '@/assets/logo.svg';
import MessageBox from '@/components/MessageBox';
import IconButton from './IconButton';
import Settings from '../Settings';
import styles from './style/index.module.less';
import defaultLocale from '@/locale';
import useStorage from '@/utils/useStorage';
import { routes, IRoute } from '@/routes';
import { authorizedFetch } from '@/utils/request';

function Navbar({ show }: { show: boolean }) {
  const t = useLocale();
  const { userInfo, userLoading } = useSelector((state: GlobalState) => state);
  const history = useHistory();

  const [, setUserStatus] = useStorage('userStatus');

  const { setLang, lang, theme, setTheme } = useContext(GlobalContext);

  const searchableRoutes = useMemo(() => {
    const result: Array<{ path: string; label: string }> = [];
    const visit = (items: IRoute[]) => {
      items.forEach((route) => {
        if (route.ignore) return;
        const path = route.path || `/${route.key}`;
        if (route.component && path) {
          result.push({ path, label: t[route.name] || route.name });
        }
        if (route.children) visit(route.children);
      });
    };
    visit(routes);
    return result;
  }, [t]);

  function handleSearch(value: string) {
    const query = value.trim().toLocaleLowerCase();
    if (!query) return;
    const match = searchableRoutes.find((route) =>
      `${route.label} ${route.path}`.toLocaleLowerCase().includes(query)
    );
    if (match) {
      history.push(match.path);
    } else {
      Message.info(t['navbar.search.noResults'] || 'No matching page');
    }
  }

  async function logout() {
    try {
      await authorizedFetch('/api/user/logout', { method: 'POST' });
    } catch (_error) {
      // Local logout still proceeds when the server is unreachable.
    } finally {
      setUserStatus('logout');
      localStorage.removeItem('conductorToken');
      window.location.href = '/login';
    }
  }

  function onMenuItemClick(key) {
    if (key === 'logout') {
      logout();
    } else if (key === 'management') {
      history.push('/user/management');
    } else {
      Message.info(`You clicked ${key}`);
    }
  }

  if (!show) {
    return (
      <div className={styles['fixed-settings']}>
        <Settings
          trigger={
            <Button icon={<IconSettings />} type="primary" size="large" />
          }
        />
      </div>
    );
  }

  const droplist = (
    <Menu onClickMenuItem={onMenuItemClick}>
      <Menu.Item key="role" disabled>
        <IconUser className={styles['dropdown-icon']} />
        <span className={styles['user-role']}>
          {userInfo?.permission_name || t['menu.user.role.user']}
        </span>
      </Menu.Item>
      {userInfo?.permissions?.['system.users']?.includes('manage') && (
        <Menu.Item key="management">
          <IconUser className={styles['dropdown-icon']} />
          {t['menu.user.management']}
        </Menu.Item>
      )}
      <Divider style={{ margin: '4px 0' }} />
      <Menu.Item key="logout">
        <IconPoweroff className={styles['dropdown-icon']} />
        {t['navbar.logout']}
      </Menu.Item>
    </Menu>
  );

  return (
    <div className={styles.navbar}>
      <div className={styles.left}>
        <div className={styles.logo}>
          <Logo />
          <div className={styles['logo-name']}>Arco Pro</div>
        </div>
      </div>
      <ul className={styles.right}>
        <li>
          <Input.Search
            className={styles.round}
            placeholder={t['navbar.search.placeholder']}
            onSearch={handleSearch}
          />
        </li>
        <li>
          <Select
            triggerElement={<IconButton icon={<IconLanguage />} />}
            options={[
              { label: '中文', value: 'zh-CN' },
              { label: 'English', value: 'en-US' },
            ]}
            value={lang}
            triggerProps={{
              autoAlignPopupWidth: false,
              autoAlignPopupMinWidth: true,
              position: 'br',
            }}
            trigger="hover"
            onChange={(value) => {
              setLang(value);
              const nextLang = defaultLocale[value];
              Message.info(`${nextLang['message.lang.tips']}${value}`);
            }}
          />
        </li>
        <li>
          <MessageBox>
            <IconButton icon={<IconNotification />} />
          </MessageBox>
        </li>
        <li>
          <Tooltip
            content={
              theme === 'light'
                ? t['settings.navbar.theme.toDark']
                : t['settings.navbar.theme.toLight']
            }
          >
            <IconButton
              icon={theme !== 'dark' ? <IconMoonFill /> : <IconSunFill />}
              onClick={() => setTheme(theme === 'light' ? 'dark' : 'light')}
            />
          </Tooltip>
        </li>
        <Settings />
        {userInfo && (
          <li>
            <Dropdown droplist={droplist} position="br" disabled={userLoading}>
              <Avatar size={32} style={{ cursor: 'pointer' }}>
                {userLoading ? (
                  <IconLoading />
                ) : userInfo.avatar ? (
                  <img alt="avatar" src={userInfo.avatar} />
                ) : (
                  <IconUser />
                )}
              </Avatar>
            </Dropdown>
          </li>
        )}
      </ul>
    </div>
  );
}

export default Navbar;
