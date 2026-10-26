import React from 'react';

interface PluginWrapperProps {
  url: string;
}

const PluginWrapper: React.FC<PluginWrapperProps> = ({ url }) => {
  return (
    <div
      style={{
        width: '100%',
        height: 'calc(100vh - 120px)',
        overflow: 'hidden',
      }}
    >
      <iframe
        src={url}
        style={{ width: '100%', height: '100%', border: 'none' }}
        title="Plugin Content"
      />
    </div>
  );
};

export default PluginWrapper;
