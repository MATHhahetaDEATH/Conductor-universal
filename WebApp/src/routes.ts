import auth, { AuthParams } from '@/utils/authentication';
import { useEffect, useMemo, useState } from 'react';
import pluginRoutes from './plugin_routes';

export type IRoute = AuthParams & {
  name: string;
  key: string;
  path?: string;
  // 当前页是否展示面包屑
  breadcrumb?: boolean;
  children?: IRoute[];
  // 当前路由是否渲染菜单项，为 true 的话不会在菜单中显示，但可通过路由地址访问。
  ignore?: boolean;
  icon?: string;
  is_core?: boolean;
  component?: any;
};

const normalizedPluginRoutes = (pluginRoutes as any[]).map((route) => ({
  ...route,
  is_core:
    route.is_core ??
    !(typeof route.path === 'string' && route.path.startsWith('/plugins/')),
}));

const corePluginRoutes = normalizedPluginRoutes
  .filter((r) => r.is_core)
  .map((r) => ({ ...r, ignore: r.hideInMenu }))
  .sort((a, b) => Number(a.ignore) - Number(b.ignore));
const customPluginRoutes = normalizedPluginRoutes
  .filter((r) => !r.is_core)
  .map((r) => ({ ...r, ignore: r.hideInMenu }));

export const routes: IRoute[] = [
  ...(corePluginRoutes as IRoute[]),
  {
    name: 'menu.conductor',
    key: 'plugin-extensions',
    icon: 'apps',
    children: customPluginRoutes as IRoute[],
  },
  {
    name: 'menu.exception',
    key: 'exception',
    children: [
      {
        name: 'menu.exception.403',
        key: 'exception/403',
        ignore: true,
      },
    ],
  },
  {
    name: 'menu.user.management',
    key: 'user/management',
    icon: 'user-management',
    requiredPermissions: [{ resource: 'system.users', actions: ['manage'] }],
  },
];

export const getName = (path: string, routes) => {
  return routes.find((item) => {
    const itemPath = `/${item.key}`;
    if (path === itemPath) {
      return item.name;
    } else if (item.children) {
      return getName(path, item.children);
    }
  });
};

export const generatePermission = (role: string) => {
  const actions = role === 'admin' ? ['*'] : ['read'];
  const result = {};
  routes.forEach((item) => {
    if (item.children) {
      item.children.forEach((child) => {
        result[child.name] = actions;
      });
    }
  });
  return result;
};

const useRoute = (userPermission): [IRoute[], string] => {
  const filterRoute = (routes: IRoute[], arr = []): IRoute[] => {
    if (!routes.length) {
      return [];
    }
    for (const route of routes) {
      const { requiredPermissions, oneOfPerm } = route;
      let visible = true;
      if (requiredPermissions) {
        visible = auth({ requiredPermissions, oneOfPerm }, userPermission);
      }

      if (!visible) {
        continue;
      }
      if (route.children && route.children.length) {
        const newRoute = { ...route, children: [] };
        filterRoute(route.children, newRoute.children);
        if (newRoute.children.length) {
          arr.push(newRoute);
        }
      } else {
        arr.push({ ...route });
      }
    }

    return arr;
  };

  const [permissionRoute, setPermissionRoute] = useState(routes);

  useEffect(() => {
    const newRoutes = filterRoute(routes);
    setPermissionRoute(newRoutes);
  }, [JSON.stringify(userPermission)]);

  const defaultRoute = useMemo(() => {
    const first = permissionRoute.find((route) => !route.ignore);
    if (first) {
      const firstRoute =
        first?.children?.find((route) => !route.ignore)?.key || first.key;
      return firstRoute;
    }
    return '';
  }, [permissionRoute]);

  return [permissionRoute, defaultRoute];
};

export default useRoute;
