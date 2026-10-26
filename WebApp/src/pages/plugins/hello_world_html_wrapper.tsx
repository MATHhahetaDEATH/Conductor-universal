import React from 'react';
import PluginWrapper from '@/components/PluginWrapper';

const Hello_worldHtmlPlugin: React.FC = () => {
  return <PluginWrapper url="/api/static/plugins/hello_world/index.html?v=1792991000305" />;
};

export default Hello_worldHtmlPlugin;
