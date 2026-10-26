/* eslint-disable @typescript-eslint/no-var-requires */
const path = require('path');
const {
  override,
  addWebpackModuleRule,
  addWebpackPlugin,
  addWebpackAlias,
  overrideDevServer,
} = require('customize-cra');
const ArcoWebpackPlugin = require('@arco-plugins/webpack-react');
const addLessLoader = require('customize-cra-less-loader');
const setting = require('./src/settings.json');

const devServerConfig = () => (config) => {
  return {
    ...config,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:5678',
        changeOrigin: true,
        pathRewrite: { '^': '' },
      },
    },
    // Ensure history API fallback is enabled for SPA routing
    historyApiFallback: true,
    port: 8678,
  };
};

module.exports = {
  webpack: override(
    (config) => {
      config.resolve.symlinks = false;
      return config;
    },
    addLessLoader({
      lessLoaderOptions: {
        lessOptions: {},
      },
    }),
    addWebpackModuleRule({
      test: /\.svg$/,
      loader: '@svgr/webpack',
    }),
    addWebpackPlugin(
      new ArcoWebpackPlugin({
        theme: '@arco-themes/react-arco-pro',
        modifyVars: {
          'arcoblue-6': setting.themeColor,
        },
      })
    ),
    addWebpackAlias({
      '@': path.resolve(__dirname, 'src'),
    })
  ),
  devServer: overrideDevServer(devServerConfig()),
};
