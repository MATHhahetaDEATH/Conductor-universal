import React, { useEffect, useState } from 'react';
import { Button, Card, Grid, Input, Message, Modal, Select, Space, Table, Tabs, Tag, Typography } from '@arco-design/web-react';
import { getPluginDependencies, getPluginFileContent, getPluginFiles, getPluginLogs, getPluginsDetail, installPluginDependencies, pluginAction, savePluginFileContent, syncPluginDependencies } from '@/services/conductor';
import axios from 'axios';

const { Row, Col } = Grid;
const { TextArea } = Input;
type Plugin = { id: string; name: string; version: string; status: string; is_core?: boolean; has_web_portal?: boolean; web_portal_url?: string };
const errorText = (error: any) => error?.response?.data?.errorMessage || error?.message || 'Request failed';

const PluginManagement: React.FC = () => {
  const [plugins, setPlugins] = useState<Plugin[]>([]);
  const [selected, setSelected] = useState<Plugin | null>(null);
  const [files, setFiles] = useState<any[]>([]);
  const [file, setFile] = useState<any>(null);
  const [logs, setLogs] = useState<string[]>([]);
  const [dependencies, setDependencies] = useState<any>(null);
  const [topology, setTopology] = useState<any>(null);
  const [ecosystem, setEcosystem] = useState<'all' | 'python' | 'web'>('all');
  const [loading, setLoading] = useState(false);

  const loadPlugins = async () => {
    setLoading(true);
    try { const payload = await getPluginsDetail(); setPlugins(payload?.data?.plugins || []); }
    catch (error) { Message.error(errorText(error)); }
    finally { setLoading(false); }
  };
  useEffect(() => {
    loadPlugins();
    getPluginDependencies().then(setDependencies).catch((error) => Message.error(errorText(error)));
    axios.get('/api/core/topology').then((response) => setTopology(response.data)).catch((error) => Message.error(errorText(error)));
  }, []);
  const selectPlugin = async (plugin: Plugin) => {
    setSelected(plugin); setFile(null);
    try { const [filePayload, logPayload] = await Promise.all([getPluginFiles(plugin.id), getPluginLogs(plugin.id)]); setFiles(filePayload?.data?.files || []); setLogs(logPayload?.data?.logs || []); }
    catch (error) { Message.error(errorText(error)); }
  };
  const action = async (operation: 'reload' | 'unload') => {
    if (!selected) return;
    try { const payload = await pluginAction({ plugin_id: selected.id, action: operation }); if (!payload.success) throw new Error(payload.errorMessage || 'Plugin action failed'); Message.success(`${operation} completed`); await loadPlugins(); }
    catch (error) { Message.error(errorText(error)); }
  };
  const openFile = async (item: any) => {
    if (!selected) return;
    try { const payload = await getPluginFileContent(selected.id, item.name, item.category); setFile({ ...item, content: payload?.data?.content || '' }); }
    catch (error) { Message.error(errorText(error)); }
  };
  const saveFile = async () => {
    if (!selected || !file) return;
    try { const payload = await savePluginFileContent({ id: selected.id, name: file.name, category: file.category, content: file.content }); if (!payload.success) throw new Error(payload.errorMessage || 'Save failed'); Message.success('File saved'); }
    catch (error) { Message.error(errorText(error)); }
  };
  const dependencyAction = async (kind: 'sync' | 'install', ecosystem: 'all' | 'python' | 'web') => {
    try { const payload = kind === 'sync' ? await syncPluginDependencies({ ecosystem }) : await installPluginDependencies({ ecosystem }); if (!payload.success) throw new Error(payload.errorMessage || `${kind} failed`); Message.success(`${kind} completed`); setDependencies(payload); }
    catch (error) { Message.error(errorText(error)); }
  };
  return <div style={{ padding: 24 }}>
    <Card title="Core Plugin Management" extra={<Button loading={loading} onClick={loadPlugins}>Refresh</Button>}>
      <Table rowKey="id" data={plugins} onRow={(record) => ({ onClick: () => selectPlugin(record) })} columns={[
        { title: 'ID', dataIndex: 'id' }, { title: 'Name', dataIndex: 'name' }, { title: 'Version', dataIndex: 'version' },
        { title: 'Status', dataIndex: 'status', render: (value) => <Tag color={value === 'loaded' ? 'green' : 'orange'}>{value}</Tag> },
        { title: 'Type', render: (_, row) => row.is_core ? 'Core' : 'Plugin' },
        { title: 'Portal', render: (_, row) => row.has_web_portal ? <Button size="small" onClick={() => window.open(row.web_portal_url, '_blank')}>Open</Button> : '-' },
      ]} />
    </Card>
    <Card style={{ marginTop: 16 }} title={selected ? `Plugin: ${selected.id}` : 'Plugin details'}>
      {!selected ? <Typography.Text type="secondary">Select a plugin to inspect its files and logs.</Typography.Text> : <Tabs defaultActiveTab="actions">
        <Tabs.TabPane key="actions" title="Lifecycle"><Space><Button status="warning" onClick={() => action('reload')}>Reload</Button><Button status="danger" onClick={() => Modal.confirm({ title: 'Unload plugin?', onOk: () => action('unload') })}>Unload</Button></Space></Tabs.TabPane>
        <Tabs.TabPane key="files" title="Files"><Row gutter={16}><Col span={8}><Table size="small" rowKey={(row) => `${row.category}/${row.name}`} data={files} pagination={false} columns={[{ title: 'File', render: (_, row) => <Button type="text" onClick={() => openFile(row)}>{row.category}/{row.name}</Button> }]} /></Col><Col span={16}>{file ? <><Typography.Text>{file.category}/{file.name}</Typography.Text><TextArea value={file.content} onChange={(content) => setFile({ ...file, content })} autoSize={{ minRows: 10, maxRows: 24 }} /><Button type="primary" style={{ marginTop: 8 }} onClick={saveFile}>Save (Owner)</Button></> : <Typography.Text type="secondary">Choose a file.</Typography.Text>}</Col></Row></Tabs.TabPane>
        <Tabs.TabPane key="logs" title="Logs"><pre style={{ maxHeight: 360, overflow: 'auto' }}>{logs.join('')}</pre></Tabs.TabPane>
      </Tabs>}
    </Card>
    <Card style={{ marginTop: 16 }} title="Dependencies"><Space><Select value={ecosystem} style={{ width: 120 }} options={[{ label: 'All', value: 'all' }, { label: 'Python', value: 'python' }, { label: 'Web', value: 'web' }]} onChange={setEcosystem} /><Button onClick={() => dependencyAction('sync', ecosystem)}>Sync manifests</Button><Button onClick={() => dependencyAction('install', ecosystem)}>Install missing</Button></Space><pre style={{ maxHeight: 260, overflow: 'auto' }}>{JSON.stringify(dependencies?.data || dependencies || {}, null, 2)}</pre></Card>
    <Card style={{ marginTop: 16 }} title="Topology"><pre style={{ maxHeight: 260, overflow: 'auto' }}>{JSON.stringify(topology?.data || topology || {}, null, 2)}</pre></Card>
  </div>;
};
export default PluginManagement;
