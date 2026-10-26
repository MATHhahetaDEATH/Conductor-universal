import React, { useEffect, useState } from 'react';
import { Card, Table, Typography, Message } from '@arco-design/web-react';

const PluginManagement: React.FC = () => {
  const [plugins, setPlugins] = useState<any[]>([]);
  useEffect(() => {
    fetch('/api/core/plugins').then((response) => response.json()).then((payload) => setPlugins(payload?.data?.plugins || [])).catch(() => Message.error('Failed to load plugins'));
  }, []);
  return <Card style={{ margin: 24 }}><Typography.Title heading={5}>Core Plugin Management</Typography.Title><Table rowKey="id" data={plugins} columns={[{ title: 'ID', dataIndex: 'id' }, { title: 'Name', dataIndex: 'name' }, { title: 'Version', dataIndex: 'version' }, { title: 'Status', dataIndex: 'status' }, { title: 'Type', render: (_, row) => row.is_core ? 'Core' : 'Plugin' }]} /></Card>;
};

export default PluginManagement;
