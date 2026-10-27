import React from 'react';
import PluginWrapper from '@/components/PluginWrapper';

const Hello_worldHtmlPlugin: React.FC = () => {
  return <PluginWrapper url="/api/static/plugins/hello_world/index.html?v=1793076170124" />;
};

export default Hello_worldHtmlPlugin;
