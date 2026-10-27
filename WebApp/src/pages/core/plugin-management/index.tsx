import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
  Alert,
  Button,
  Card,
  Grid,
  Input,
  Message,
  Modal,
  Select,
  Space,
  Table,
  Tabs,
  Tag,
  Typography,
} from '@arco-design/web-react';
import ForceGraph2D, {
  GraphData,
  NodeObject,
  ForceGraphMethods,
} from 'react-force-graph-2d';
import {
  getPluginFileContent,
  getPluginFiles,
  getPluginLogs,
  getPluginsDetail,
  installPluginDependencies,
  pluginAction,
  savePluginFileContent,
  syncPluginDependencies,
} from '@/services/conductor';
import { requestJson } from '@/utils/request';

const { Row, Col } = Grid;
const { TextArea } = Input;

type Plugin = {
  id: string;
  name: string;
  version: string;
  status: string;
  is_core?: boolean;
  has_web_portal?: boolean;
  web_portal_url?: string;
};

type DependencyRow = {
  ecosystem: string;
  name: string;
  specs?: string[];
  installed?: string | null;
  status: 'ok' | 'missing' | 'version_mismatch' | string;
  plugins?: string[];
  source_files?: string[];
};

type DependencyPayload = {
  dependencies?: DependencyRow[];
  next_actions?: string[];
  manifest_sync?: Record<string, unknown>;
};

type TopologyNode = {
  id: string;
  name: string;
  is_core?: boolean;
  priority?: number;
};

type TopologyLink = { source: string; target: string };
type TopologyPayload = { nodes?: TopologyNode[]; links?: TopologyLink[] };
type GraphNode = TopologyNode & { x?: number; y?: number };
type GraphLink = TopologyLink;

const errorText = (error: any) =>
  error?.response?.data?.errorMessage || error?.message || 'Request failed';

const statusColor: Record<string, string> = {
  ok: 'green',
  missing: 'red',
  version_mismatch: 'orange',
};

const PluginManagement: React.FC = () => {
  const [plugins, setPlugins] = useState<Plugin[]>([]);
  const [selected, setSelected] = useState<Plugin | null>(null);
  const [files, setFiles] = useState<any[]>([]);
  const [file, setFile] = useState<any>(null);
  const [logs, setLogs] = useState<string[]>([]);
  const [dependencies, setDependencies] = useState<DependencyPayload>({});
  const [topology, setTopology] = useState<TopologyPayload>({});
  const [ecosystem, setEcosystem] = useState<'all' | 'python' | 'web'>('all');
  const [dependencyFilter, setDependencyFilter] = useState('');
  const [loading, setLoading] = useState(false);
  const [dependencyLoading, setDependencyLoading] = useState(false);
  const [topologyLoading, setTopologyLoading] = useState(false);
  const [topologyError, setTopologyError] = useState('');
  const [dependencyError, setDependencyError] = useState('');
  const graphRef = useRef<ForceGraphMethods<GraphNode, GraphLink>>();

  const loadPlugins = async () => {
    setLoading(true);
    try {
      const payload = await getPluginsDetail();
      setPlugins(payload?.data?.plugins || []);
    } catch (error) {
      Message.error(errorText(error));
    } finally {
      setLoading(false);
    }
  };

  const loadDependencies = async () => {
    setDependencyLoading(true);
    setDependencyError('');
    try {
      setDependencies(await requestJson<DependencyPayload>('/api/core/dependencies'));
    } catch (error) {
      setDependencyError(errorText(error));
      Message.error(errorText(error));
    } finally {
      setDependencyLoading(false);
    }
  };

  const loadTopology = async () => {
    setTopologyLoading(true);
    setTopologyError('');
    try {
      setTopology(await requestJson<TopologyPayload>('/api/core/topology'));
    } catch (error) {
      setTopologyError(errorText(error));
      Message.error(errorText(error));
    } finally {
      setTopologyLoading(false);
    }
  };

  useEffect(() => {
    loadPlugins();
    loadDependencies();
    loadTopology();
  }, []);

  const selectPlugin = async (plugin: Plugin) => {
    setSelected(plugin);
    setFile(null);
    try {
      const [filePayload, logPayload] = await Promise.all([
        getPluginFiles(plugin.id),
        getPluginLogs(plugin.id),
      ]);
      setFiles(filePayload?.data?.files || []);
      setLogs(logPayload?.data?.logs || []);
    } catch (error) {
      Message.error(errorText(error));
    }
  };

  const action = async (operation: 'reload' | 'unload') => {
    if (!selected) return;
    try {
      const payload = await pluginAction({ plugin_id: selected.id, action: operation });
      if (!payload.success) throw new Error(payload.errorMessage || 'Plugin action failed');
      Message.success(`${operation} completed`);
      await loadPlugins();
      await loadTopology();
    } catch (error) {
      Message.error(errorText(error));
    }
  };

  const openFile = async (item: any) => {
    if (!selected) return;
    try {
      const payload = await getPluginFileContent(selected.id, item.name, item.category);
      setFile({ ...item, content: payload?.data?.content || '' });
    } catch (error) {
      Message.error(errorText(error));
    }
  };

  const saveFile = async () => {
    if (!selected || !file) return;
    try {
      const payload = await savePluginFileContent({
        id: selected.id,
        name: file.name,
        category: file.category,
        content: file.content,
      });
      if (!payload.success) throw new Error(payload.errorMessage || 'Save failed');
      Message.success('File saved');
    } catch (error) {
      Message.error(errorText(error));
    }
  };

  const dependencyAction = async (
    kind: 'sync' | 'install',
    selectedEcosystem: 'all' | 'python' | 'web'
  ) => {
    try {
      const payload =
        kind === 'sync'
          ? await syncPluginDependencies({ ecosystem: selectedEcosystem })
          : await installPluginDependencies({ ecosystem: selectedEcosystem });
      if (!payload.success) throw new Error(payload.errorMessage || `${kind} failed`);
      Message.success(`${kind} completed`);
      await loadDependencies();
    } catch (error) {
      Message.error(errorText(error));
    }
  };

  const dependencyRows = useMemo(() => {
    const query = dependencyFilter.trim().toLowerCase();
    return (dependencies.dependencies || []).filter((row) => {
      if (ecosystem !== 'all' && row.ecosystem !== ecosystem) return false;
      if (!query) return true;
      return [row.name, row.ecosystem, ...(row.plugins || []), ...(row.source_files || [])]
        .join(' ')
        .toLowerCase()
        .includes(query);
    });
  }, [dependencies.dependencies, dependencyFilter, ecosystem]);

  const graphData = useMemo<GraphData<GraphNode, GraphLink>>(
    () => ({
      nodes: (topology.nodes || []) as GraphNode[],
      links: (topology.links || []) as GraphLink[],
    }),
    [topology]
  );

  const graphNodeClick = (node: NodeObject<GraphNode>) => {
    const plugin = plugins.find((item) => item.id === node.id);
    if (plugin) selectPlugin(plugin);
  };

  return (
    <div style={{ padding: 24 }}>
      <Card title="Core Plugin Management" extra={<Button loading={loading} onClick={loadPlugins}>Refresh</Button>}>
        <Table
          rowKey="id"
          data={plugins}
          onRow={(record) => ({ onClick: () => selectPlugin(record) })}
          columns={[
            { title: 'ID', dataIndex: 'id' },
            { title: 'Name', dataIndex: 'name' },
            { title: 'Version', dataIndex: 'version' },
            { title: 'Status', dataIndex: 'status', render: (value) => <Tag color={value === 'loaded' ? 'green' : 'orange'}>{value}</Tag> },
            { title: 'Type', render: (_, row) => row.is_core ? 'Core' : 'Plugin' },
            { title: 'Portal', render: (_, row) => row.has_web_portal ? <Button size="small" onClick={(event) => { event.stopPropagation(); window.open(row.web_portal_url, '_blank'); }}>Open</Button> : '-' },
          ]}
        />
      </Card>

      <Card style={{ marginTop: 16 }} title={selected ? `Plugin: ${selected.id}` : 'Plugin details'}>
        {!selected ? <Typography.Text type="secondary">Select a plugin to inspect its files and logs.</Typography.Text> : <Tabs defaultActiveTab="actions">
          <Tabs.TabPane key="actions" title="Lifecycle"><Space><Button status="warning" onClick={() => action('reload')}>Reload</Button><Button status="danger" onClick={() => Modal.confirm({ title: 'Unload plugin?', onOk: () => action('unload') })}>Unload</Button></Space></Tabs.TabPane>
          <Tabs.TabPane key="files" title="Files"><Row gutter={16}><Col span={8}><Table size="small" rowKey={(row) => `${row.category}/${row.name}`} data={files} pagination={false} columns={[{ title: 'File', render: (_, row) => <Button type="text" onClick={() => openFile(row)}>{row.category}/{row.name}</Button> }]} /></Col><Col span={16}>{file ? <><Typography.Text>{file.category}/{file.name}</Typography.Text><TextArea value={file.content} onChange={(content) => setFile({ ...file, content })} autoSize={{ minRows: 10, maxRows: 24 }} /><Button type="primary" style={{ marginTop: 8 }} onClick={saveFile}>Save (Owner)</Button></> : <Typography.Text type="secondary">Choose a file.</Typography.Text>}</Col></Row></Tabs.TabPane>
          <Tabs.TabPane key="logs" title="Logs"><pre style={{ maxHeight: 360, overflow: 'auto' }}>{logs.length ? logs.join('') : 'No logs available.'}</pre></Tabs.TabPane>
        </Tabs>}
      </Card>

      <Card style={{ marginTop: 16 }} title="Dependencies" extra={<Space><Select value={ecosystem} style={{ width: 120 }} options={[{ label: 'All', value: 'all' }, { label: 'Python', value: 'python' }, { label: 'Web', value: 'web' }]} onChange={setEcosystem} /><Button loading={dependencyLoading} onClick={loadDependencies}>Refresh</Button><Button onClick={() => dependencyAction('sync', ecosystem)}>Sync manifests</Button><Button onClick={() => dependencyAction('install', ecosystem)}>Install missing</Button></Space>}>
        <Input.Search allowClear placeholder="Filter dependencies or plugins" value={dependencyFilter} onChange={setDependencyFilter} style={{ maxWidth: 360, marginBottom: 12 }} />
        {dependencyError ? <Alert type="error" content={dependencyError} /> : <Table
          rowKey={(row) => `${row.ecosystem}:${row.name}`}
          loading={dependencyLoading}
          data={dependencyRows}
          pagination={{ pageSize: 8 }}
          columns={[
            { title: 'Dependency', dataIndex: 'name' },
            { title: 'Ecosystem', dataIndex: 'ecosystem', render: (value) => <Tag>{value}</Tag> },
            { title: 'Declared', dataIndex: 'specs', render: (value) => (value || []).join(', ') || '*' },
            { title: 'Installed', dataIndex: 'installed', render: (value) => value || '-' },
            { title: 'Status', dataIndex: 'status', render: (value) => <Tag color={statusColor[value] || 'arcoblue'}>{value}</Tag> },
            { title: 'Plugins', dataIndex: 'plugins', render: (value) => (value || []).join(', ') || '-' },
            { title: 'Sources', dataIndex: 'source_files', render: (value) => (value || []).map((item) => item.split('/').pop()).join(', ') || '-' },
          ]}
        />}
      </Card>

      <Card style={{ marginTop: 16 }} title="Topology" extra={<Button loading={topologyLoading} onClick={loadTopology}>Refresh</Button>}>
        {topologyError ? <Alert type="error" content={topologyError} /> : graphData.nodes.length ? <>
          <Space style={{ marginBottom: 12 }}><Tag color="arcoblue">Core</Tag><Tag color="green">Plugin</Tag><Typography.Text type="secondary">Click a node to open plugin details. Drag and zoom are enabled.</Typography.Text></Space>
          <div style={{ height: 460, border: '1px solid var(--color-neutral-3)', borderRadius: 4, overflow: 'hidden' }}>
            <ForceGraph2D
              ref={graphRef}
              graphData={graphData}
              nodeLabel={(node) => `${node.name} (${node.id})`}
              nodeColor={(node) => node.is_core ? '#165DFF' : '#00B42A'}
              nodeRelSize={6}
              linkDirectionalArrowLength={5}
              linkDirectionalArrowRelPos={1}
              linkColor={() => '#86909C'}
              linkWidth={1.5}
              dagMode="td"
              dagLevelDistance={70}
              onNodeClick={graphNodeClick}
              cooldownTicks={80}
              onEngineStop={() => graphRef.current?.zoomToFit(400, 30)}
            />
          </div>
        </> : <Typography.Text type="secondary">No topology data available.</Typography.Text>}
      </Card>
    </div>
  );
};

export default PluginManagement;
