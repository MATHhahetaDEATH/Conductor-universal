import React, {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import {
  Button,
  Card,
  Descriptions,
  Grid,
  Image,
  Input,
  InputNumber,
  Message,
  Modal,
  Select,
  Space,
  Statistic,
  Switch,
  Table,
  Tabs,
  Tag,
  Typography,
} from '@arco-design/web-react';
import {
  IconCode,
  IconDelete,
  IconEdit,
  IconPlus,
  IconRefresh,
  IconSend,
} from '@arco-design/web-react/icon';
import { useHistory } from 'react-router-dom';

const { Row, Col } = Grid;
const { Title, Text } = Typography;
const TextArea = Input.TextArea;
const tierOptions = [
  { label: 'T1 (1B-8B)', value: 't1' },
  { label: 'T2 (9B+)', value: 't2' },
  { label: 'T3 (Large)', value: 't3' },
  { label: 'VL (Vision)', value: 'vl' },
  { label: 'EB (Embedding)', value: 'eb' },
];
const providerTypeOptions = [
  { label: 'Local llama.cpp', value: 'llama_cpp' },
  { label: 'Online API', value: 'openai_compatible' },
];
const strategyOptions = [
  { label: 'Balanced', value: 'balanced' },
  { label: 'Priority', value: 'priority' },
];
const tierDescriptions: Record<string, string> = {
  t1: '1B-8B text models for lighter tasks.',
  t2: '9B+ text models for stronger general work.',
  t3: 'Large flagship text models for heavier reasoning.',
  vl: 'Vision-language models that can process images with text.',
  eb: 'Embedding models for vectorization and retrieval pipelines.',
};

type LocalFile = {
  id: string;
  name: string;
  path: string;
  size: number;
};

type SelectableModel = {
  selector: string;
  provider: string;
  provider_id?: string;
  display_name: string;
  name: string;
  model?: string;
  transport: 'local' | 'online';
  tier?: string;
  enabled?: boolean;
  max_concurrency?: number;
  base_url?: string;
  type?: string;
  model_path?: string;
  mmproj_path?: string;
  vl_handler?: string;
  tags?: string[];
};

type JobRow = {
  job_id: string;
  provider: string;
  selector?: string;
  tier?: string;
  status: string;
  error?: string;
};

type LLMStatus = {
  queue_size?: number;
  worker_alive?: boolean;
  selectable_models?: SelectableModel[];
  tiers?: Record<string, { count: number }>;
  capacity?: {
    local_active?: number;
    online_active?: Record<string, number>;
  };
  runtime?: {
    llama_cpp_available?: boolean;
    llama_cpp_chat_handlers?: string[];
    python_executable?: string;
  };
  last_llama_cpp_debug?: Record<string, unknown> | null;
  recent_jobs?: JobRow[];
};

type RoutingEntry = {
  default_provider: string;
  strategy: 'balanced' | 'priority';
};

type RoutingConfig = Record<string, RoutingEntry>;

type ProviderEditorState = {
  providerId: string;
  type: 'llama_cpp' | 'openai_compatible';
  displayName: string;
  enabled: boolean;
  tier: string;
  maxConcurrency: number;
  tagsText: string;
  modelName: string;
  baseUrl: string;
  apiKey: string;
  modelPath: string;
  mmprojPath: string;
  vlHandler: string;
  nCtx: number;
  nGpuLayers: number;
  temperature: number;
  maxTokens: number;
  timeout: number;
};

const emptyProviderEditor = (): ProviderEditorState => ({
  providerId: '',
  type: 'openai_compatible',
  displayName: '',
  enabled: true,
  tier: 't2',
  maxConcurrency: 4,
  tagsText: '',
  modelName: '',
  baseUrl: 'https://api.openai.com/v1',
  apiKey: '',
  modelPath: '',
  mmprojPath: '',
  vlHandler: '',
  nCtx: 4096,
  nGpuLayers: 0,
  temperature: 0.7,
  maxTokens: 512,
  timeout: 60,
});

const requestJson = async <T,>(
  url: string,
  options?: RequestInit
): Promise<T> => {
  const res = await fetch(url, {
    headers: {
      'Content-Type': 'application/json',
      ...(options?.headers || {}),
    },
    ...options,
  });
  const data = await res.json();
  if (!data.success) {
    throw new Error(data.errorMessage || 'Request failed');
  }
  return data.data;
};

const parseTags = (text: string) =>
  text
    .split(/[\n,]+/)
    .map((item) => item.trim())
    .filter(Boolean);

const toProviderId = (value: string) =>
  value
    .trim()
    .toLowerCase()
    .replace(/\.[a-z0-9]+$/i, '')
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/^_+|_+$/g, '')
    .slice(0, 64);

const normalizeRouting = (
  value?: Record<string, Partial<RoutingEntry>>
): RoutingConfig => {
  const base: RoutingConfig = {};
  tierOptions.forEach((tier) => {
    const entry = value?.[tier.value] || {};
    base[tier.value] = {
      default_provider: String(entry.default_provider || ''),
      strategy: entry.strategy === 'priority' ? 'priority' : 'balanced',
    };
  });
  return base;
};

const LLMProviderPage: React.FC = () => {
  const history = useHistory();
  const [status, setStatus] = useState<LLMStatus>({});
  const [localFiles, setLocalFiles] = useState<LocalFile[]>([]);
  const [mmprojFiles, setMmprojFiles] = useState<LocalFile[]>([]);
  const [selectedTarget, setSelectedTarget] = useState<string>();
  const [prompt, setPrompt] = useState(
    'Write a one-sentence readiness check for Conductor.'
  );
  const [systemPrompt, setSystemPrompt] = useState('');
  const [vlImageUrl, setVlImageUrl] = useState('');
  const [vlImageDataUrl, setVlImageDataUrl] = useState('');
  const [vlImageName, setVlImageName] = useState('');
  const [vlFileInputKey, setVlFileInputKey] = useState(0);
  const [temperature, setTemperature] = useState(0.7);
  const [maxTokens, setMaxTokens] = useState(256);
  const [timeout, setTimeoutValue] = useState(120);
  const [responseText, setResponseText] = useState('');
  const [rawResponse, setRawResponse] = useState('');
  const [pluginLogText, setPluginLogText] = useState('');
  const [loading, setLoading] = useState(false);
  const [editorVisible, setEditorVisible] = useState(false);
  const [editorMode, setEditorMode] = useState<'create' | 'edit'>('create');
  const [editorState, setEditorState] = useState<ProviderEditorState>(
    emptyProviderEditor()
  );
  const [routingConfig, setRoutingConfig] = useState<RoutingConfig>(() =>
    normalizeRouting()
  );
  const [routingSaving, setRoutingSaving] = useState(false);
  const vlFileInputRef = useRef<HTMLInputElement | null>(null);

  const selectableModels = useMemo(
    () => status.selectable_models || [],
    [status.selectable_models]
  );
  const modelsByTier = useMemo(() => {
    const grouped: Record<string, SelectableModel[]> = {};
    tierOptions.forEach((tier) => {
      grouped[tier.value] = selectableModels.filter(
        (item) => item.enabled !== false && item.tier === tier.value
      );
    });
    return grouped;
  }, [selectableModels]);

  const selectableOptions = useMemo(() => {
    return selectableModels
      .filter((item) => item.enabled !== false)
      .map((item) => ({
        label: `${item.display_name} (${item.provider_id || item.selector})`,
        value: item.selector,
      }));
  }, [selectableModels]);

  const selectableRows = useMemo(() => {
    return selectableModels.map((item) => ({
      ...item,
      key: item.selector,
      active:
        item.transport === 'local'
          ? status.capacity?.local_active || 0
          : status.capacity?.online_active?.[item.selector] || 0,
    }));
  }, [selectableModels, status.capacity]);

  const loadStatus = useCallback(async () => {
    const data = await requestJson<LLMStatus>('/api/llm/status');
    setStatus(data);
    setSelectedTarget(
      (current) =>
        current ||
        data.selectable_models?.find((item) => item.enabled !== false)?.selector
    );
  }, []);

  const loadPluginLogs = useCallback(async () => {
    const data = await requestJson<{ records?: Array<{ formatted?: string }> }>(
      '/api/logs/records?category=plugin&owner=llm_provider&limit=200'
    );
    const records = Array.isArray(data.records) ? data.records : [];
    setPluginLogText(
      records.map((item) => String(item.formatted || '')).join('\n')
    );
  }, []);

  const loadRouting = useCallback(async () => {
    const data = await requestJson<Record<string, Partial<RoutingEntry>>>(
      '/api/llm/routing'
    );
    setRoutingConfig(normalizeRouting(data));
  }, []);

  const loadLocalFiles = useCallback(async () => {
    const data = await requestJson<{
      models: LocalFile[];
      mmprojs: LocalFile[];
    }>('/api/llm/models');
    setLocalFiles(data.models || []);
    setMmprojFiles(data.mmprojs || []);
  }, []);

  const refreshAll = useCallback(async () => {
    try {
      await Promise.all([
        loadStatus(),
        loadLocalFiles(),
        loadRouting(),
        loadPluginLogs(),
      ]);
    } catch (error) {
      Message.error(String(error));
    }
  }, [loadLocalFiles, loadPluginLogs, loadRouting, loadStatus]);

  useEffect(() => {
    refreshAll();
    const timer = window.setInterval(() => {
      loadStatus();
      loadPluginLogs();
    }, 3000);
    return () => window.clearInterval(timer);
  }, [loadPluginLogs, loadStatus, refreshAll]);

  const selectedModel = useMemo(
    () => selectableModels.find((item) => item.selector === selectedTarget),
    [selectableModels, selectedTarget]
  );
  const lastLlamaCppDebugText = useMemo(() => {
    if (!status.last_llama_cpp_debug) {
      return '';
    }
    return JSON.stringify(status.last_llama_cpp_debug, null, 2);
  }, [status.last_llama_cpp_debug]);
  const selectedTier = selectedModel?.tier;
  const isEmbeddingTest = selectedTier === 'eb';
  const isVisionTest = selectedTier === 'vl';
  const vlResolvedImageUrl = vlImageDataUrl || vlImageUrl.trim();

  const onSelectVlImageFile = async (
    event: React.ChangeEvent<HTMLInputElement>
  ) => {
    const file = event.target.files?.[0];
    event.target.value = '';
    if (!file) {
      return;
    }
    if (!file.type.startsWith('image/')) {
      Message.error('Please choose an image file');
      return;
    }
    const reader = new FileReader();
    reader.onload = () => {
      const result = typeof reader.result === 'string' ? reader.result : '';
      if (!result) {
        Message.error('Failed to read image file');
        return;
      }
      setVlImageDataUrl(result);
      setVlImageName(file.name);
      setVlImageUrl('');
      setVlFileInputKey((current) => current + 1);
    };
    reader.onerror = () => {
      Message.error('Failed to read image file');
    };
    reader.readAsDataURL(file);
  };

  const clearVlImage = () => {
    setVlImageUrl('');
    setVlImageDataUrl('');
    setVlImageName('');
    setVlFileInputKey((current) => current + 1);
  };

  const runTest = async () => {
    setLoading(true);
    setResponseText('');
    setRawResponse('');
    try {
      if (!selectedTarget) {
        throw new Error('Select a model first');
      }
      if (isVisionTest && !vlResolvedImageUrl) {
        throw new Error(
          'VL test requires an image URL or a local uploaded image'
        );
      }
      const data = await requestJson<Record<string, unknown>>(
        isEmbeddingTest
          ? '/api/llm/embed'
          : isVisionTest
          ? '/api/llm/chat'
          : '/api/llm/complete',
        {
          method: 'POST',
          body: JSON.stringify(
            isEmbeddingTest
              ? {
                  input: prompt,
                  provider: selectedTarget,
                  options: {
                    timeout,
                  },
                  timeout,
                }
              : isVisionTest
              ? {
                  provider: selectedTarget,
                  messages: [
                    ...(systemPrompt.trim()
                      ? [{ role: 'system', content: systemPrompt.trim() }]
                      : []),
                    {
                      role: 'user',
                      content:
                        selectedModel?.transport === 'local' &&
                        selectedModel?.vl_handler === 'Qwen25VLChatHandler'
                          ? [
                              {
                                type: 'image_url',
                                image_url: {
                                  url: vlResolvedImageUrl,
                                },
                              },
                              { type: 'text', text: prompt },
                            ]
                          : [
                              { type: 'text', text: prompt },
                              {
                                type: 'image_url',
                                image_url: {
                                  url: vlResolvedImageUrl,
                                },
                              },
                            ],
                    },
                  ],
                  options: {
                    temperature,
                    max_tokens: maxTokens,
                  },
                  timeout,
                }
              : {
                  prompt,
                  system_prompt: systemPrompt,
                  provider: selectedTarget,
                  options: {
                    temperature,
                    max_tokens: maxTokens,
                  },
                  timeout,
                }
          ),
        }
      );
      setResponseText(
        isEmbeddingTest
          ? JSON.stringify((data.embeddings as unknown[]) || [], null, 2)
          : String(data.text || '')
      );
      setRawResponse(JSON.stringify(data, null, 2));
      Message.success('LLM request completed');
      await Promise.all([loadStatus(), loadPluginLogs()]);
    } catch (error) {
      Message.error(String(error));
      await Promise.all([loadStatus(), loadPluginLogs()]);
    } finally {
      setLoading(false);
    }
  };

  const openCreateEditor = () => {
    setEditorMode('create');
    setEditorState(emptyProviderEditor());
    setEditorVisible(true);
  };

  const openEditEditor = (row: SelectableModel) => {
    setEditorMode('edit');
    setEditorState({
      providerId: row.provider_id || row.selector,
      type: row.type === 'llama_cpp' ? 'llama_cpp' : 'openai_compatible',
      displayName: row.display_name || row.name,
      enabled: row.enabled !== false,
      tier: row.tier || '',
      maxConcurrency:
        row.max_concurrency || (row.transport === 'local' ? 1 : 4),
      tagsText: (row.tags || []).join(', '),
      modelName: row.transport === 'online' ? String(row.model || '') : '',
      baseUrl: row.base_url || 'https://api.openai.com/v1',
      apiKey: '',
      modelPath: row.model_path || '',
      mmprojPath: String(
        (row as SelectableModel & { mmproj_path?: string }).mmproj_path || ''
      ),
      vlHandler: String(
        (row as SelectableModel & { vl_handler?: string }).vl_handler || ''
      ),
      nCtx: Number((row as SelectableModel & { n_ctx?: number }).n_ctx || 4096),
      nGpuLayers: Number(
        (row as SelectableModel & { n_gpu_layers?: number }).n_gpu_layers || 0
      ),
      temperature: Number(
        (row as SelectableModel & { temperature?: number }).temperature || 0.7
      ),
      maxTokens: Number(
        (row as SelectableModel & { max_tokens?: number }).max_tokens || 512
      ),
      timeout: Number(
        (row as SelectableModel & { timeout?: number }).timeout || 60
      ),
    });
    setEditorVisible(true);
  };

  const saveProvider = async () => {
    try {
      if (!editorState.providerId.trim()) {
        throw new Error('Provider ID is required');
      }
      if (!editorState.displayName.trim()) {
        throw new Error('Display Name is required');
      }
      if (editorState.type === 'llama_cpp' && !editorState.modelPath) {
        throw new Error('Select a local gguf/bin file');
      }
      if (
        editorState.type === 'openai_compatible' &&
        !editorState.baseUrl.trim()
      ) {
        throw new Error('Base URL is required');
      }
      const payload: Record<string, unknown> = {
        type: editorState.type,
        enabled: editorState.enabled,
        display_name: editorState.displayName,
        tier: editorState.tier,
        max_concurrency:
          editorState.type === 'llama_cpp' ? 1 : editorState.maxConcurrency,
        tags: parseTags(editorState.tagsText),
        temperature: editorState.temperature,
        max_tokens: editorState.maxTokens,
      };
      if (editorState.type === 'llama_cpp') {
        payload.model_path = editorState.modelPath;
        payload.mmproj_path = editorState.mmprojPath;
        payload.vl_handler = editorState.vlHandler;
        payload.n_ctx = editorState.nCtx;
        payload.n_gpu_layers = editorState.nGpuLayers;
      } else {
        payload.base_url = editorState.baseUrl;
        payload.model = editorState.modelName;
        payload.timeout = editorState.timeout;
        if (editorState.apiKey) {
          payload.api_key = editorState.apiKey;
        }
      }
      await requestJson(
        `/api/llm/providers/${encodeURIComponent(editorState.providerId)}`,
        {
          method: 'POST',
          body: JSON.stringify(payload),
        }
      );
      Message.success(
        editorMode === 'create' ? 'Model added' : 'Model updated'
      );
      setEditorVisible(false);
      refreshAll();
    } catch (error) {
      Message.error(String(error));
    }
  };

  const deleteProvider = async (providerId: string) => {
    Modal.confirm({
      title: 'Delete model',
      content: `Delete ${providerId}?`,
      onOk: async () => {
        try {
          await requestJson(
            `/api/llm/providers/${encodeURIComponent(providerId)}`,
            {
              method: 'DELETE',
            }
          );
          Message.success('Model deleted');
          refreshAll();
        } catch (error) {
          Message.error(String(error));
        }
      },
    });
  };

  const saveRouting = async () => {
    setRoutingSaving(true);
    try {
      await requestJson('/api/llm/routing', {
        method: 'POST',
        body: JSON.stringify(routingConfig),
      });
      Message.success('Routing updated');
      refreshAll();
    } catch (error) {
      Message.error(String(error));
    } finally {
      setRoutingSaving(false);
    }
  };

  const modelColumns = [
    {
      title: 'Provider ID',
      dataIndex: 'provider_id',
      width: 180,
      ellipsis: true,
    },
    { title: 'Display Name', dataIndex: 'display_name', width: 180 },
    {
      title: 'Tags',
      dataIndex: 'tags',
      render: (value: string[]) =>
        value?.length ? (
          <Space wrap>
            {value.map((tag) => (
              <Tag key={tag}>{tag}</Tag>
            ))}
          </Space>
        ) : (
          '-'
        ),
    },
    {
      title: 'Type',
      dataIndex: 'type',
      width: 130,
      render: (value: string) => (value === 'llama_cpp' ? 'Local' : 'Online'),
    },
    {
      title: 'Tier',
      dataIndex: 'tier',
      width: 90,
      render: (value: string) => value || '-',
    },
    {
      title: 'Status',
      dataIndex: 'enabled',
      width: 100,
      render: (value: boolean) => (
        <Tag color={value === false ? 'red' : 'green'}>
          {value === false ? 'disabled' : 'enabled'}
        </Tag>
      ),
    },
    { title: 'Active', dataIndex: 'active', width: 80 },
    {
      title: 'Max',
      dataIndex: 'max_concurrency',
      width: 80,
      render: (value: number) => value || 1,
    },
    {
      title: 'Manage',
      width: 160,
      render: (_: unknown, row: SelectableModel) => (
        <Space>
          <Button
            size="mini"
            icon={<IconEdit />}
            onClick={() => openEditEditor(row)}
          >
            Edit
          </Button>
          <Button
            size="mini"
            status="danger"
            icon={<IconDelete />}
            onClick={() => deleteProvider(row.provider_id || row.selector)}
          >
            Delete
          </Button>
        </Space>
      ),
    },
  ];

  const jobColumns = [
    { title: 'Job ID', dataIndex: 'job_id', ellipsis: true },
    { title: 'Provider', dataIndex: 'provider', width: 150 },
    {
      title: 'Provider ID',
      dataIndex: 'selector',
      width: 180,
      ellipsis: true,
      render: (value: string) => value || '-',
    },
    {
      title: 'Tier',
      dataIndex: 'tier',
      width: 80,
      render: (value: string) => value || '-',
    },
    {
      title: 'Status',
      dataIndex: 'status',
      width: 120,
      render: (value: string) => {
        const color =
          value === 'succeeded'
            ? 'green'
            : value === 'failed'
            ? 'red'
            : 'arcoblue';
        return <Tag color={color}>{value}</Tag>;
      },
    },
    {
      title: 'Error',
      dataIndex: 'error',
      ellipsis: true,
      render: (value: string) => value || '-',
    },
  ];

  return (
    <div style={{ padding: 24 }}>
      <Title heading={5}>LLM Provider</Title>
      <Text type="secondary" style={{ display: 'block', marginBottom: 24 }}>
        Unified model management for local gguf models and online text APIs.
      </Text>

      <Space style={{ marginBottom: 16 }} wrap>
        <Button
          icon={<IconCode />}
          onClick={() => history.push('/core/terminal')}
        >
          Terminal
        </Button>
        <Button icon={<IconRefresh />} onClick={refreshAll}>
          Refresh
        </Button>
      </Space>

      <Row gutter={[16, 16]}>
        <Col span={6}>
          <Card>
            <Statistic title="Queue Size" value={status.queue_size ?? 0} />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="Worker Alive"
              value={status.worker_alive ? 'yes' : 'no'}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="Configured Models"
              value={selectableModels.length}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="Local Active"
              value={status.capacity?.local_active ?? 0}
            />
          </Card>
        </Col>
      </Row>

      <Tabs defaultActiveTab="test" style={{ marginTop: 16 }}>
        <Tabs.TabPane key="test" title="Test">
          <Row gutter={[16, 16]}>
            <Col span={10}>
              <Card title="Request">
                <Space
                  direction="vertical"
                  size="medium"
                  style={{ width: '100%' }}
                >
                  <Select
                    value={selectedTarget}
                    options={selectableOptions}
                    placeholder="Select configured model"
                    onChange={setSelectedTarget}
                    style={{ width: '100%' }}
                  />
                  <Card size="small">
                    <Space direction="vertical" style={{ width: '100%' }}>
                      {selectedModel?.transport === 'local' ? (
                        <>
                          <Text
                            type={
                              status.runtime?.llama_cpp_available
                                ? 'success'
                                : 'warning'
                            }
                          >
                            llama-cpp-python:{' '}
                            {status.runtime?.llama_cpp_available
                              ? 'available'
                              : 'missing'}
                          </Text>
                          <Text
                            type="secondary"
                            style={{ wordBreak: 'break-all' }}
                          >
                            Python: {status.runtime?.python_executable || '-'}
                          </Text>
                        </>
                      ) : (
                        <Text
                          type="secondary"
                          style={{ wordBreak: 'break-all' }}
                        >
                          Base URL: {selectedModel?.base_url || '-'}
                        </Text>
                      )}
                      <Text type="secondary">
                        Tags: {(selectedModel?.tags || []).join(' ') || '-'}
                      </Text>
                      <Text type="secondary">
                        Tier:{' '}
                        {selectedModel?.tier
                          ? `${selectedModel.tier.toUpperCase()} - ${
                              tierDescriptions[selectedModel.tier] || '-'
                            }`
                          : '-'}
                      </Text>
                    </Space>
                  </Card>
                  {!isEmbeddingTest ? (
                    <TextArea
                      value={systemPrompt}
                      onChange={setSystemPrompt}
                      placeholder="Optional system prompt"
                      autoSize={{ minRows: 3, maxRows: 6 }}
                    />
                  ) : null}
                  {isVisionTest ? (
                    <>
                      <Input
                        value={vlImageUrl}
                        onChange={(value) => {
                          setVlImageUrl(value);
                          if (value.trim()) {
                            setVlImageDataUrl('');
                            setVlImageName('');
                          }
                        }}
                        placeholder="Image URL for VL test, for example https://example.com/demo.png"
                      />
                      <Text type="secondary">
                        VL tests send the image through `image_url`. Local
                        uploaded images are encoded as
                        `data:image/...;base64,...`, which is valid for
                        OpenAI-style multimodal payloads. Local llama.cpp VL
                        normalization now follows the selected
                        `llama_cpp.llama_chat_format` handler class.
                      </Text>
                      <Space wrap>
                        <input
                          ref={vlFileInputRef}
                          key={vlFileInputKey}
                          type="file"
                          accept="image/*"
                          onChange={onSelectVlImageFile}
                          style={{ display: 'none' }}
                        />
                        <Button onClick={() => vlFileInputRef.current?.click()}>
                          Upload Local Image
                        </Button>
                        <Button
                          onClick={clearVlImage}
                          disabled={!vlResolvedImageUrl}
                        >
                          Clear Image
                        </Button>
                      </Space>
                      {vlImageName ? (
                        <Text type="secondary">Local image: {vlImageName}</Text>
                      ) : null}
                      {vlResolvedImageUrl ? (
                        <Card size="small">
                          <Space direction="vertical" style={{ width: '100%' }}>
                            <Text type="secondary">Current image preview</Text>
                            <Image src={vlResolvedImageUrl} width={220} />
                          </Space>
                        </Card>
                      ) : null}
                    </>
                  ) : null}
                  <TextArea
                    value={prompt}
                    onChange={setPrompt}
                    placeholder={
                      isEmbeddingTest
                        ? 'Input text for embedding'
                        : isVisionTest
                        ? 'Question or instruction for the image'
                        : 'Prompt'
                    }
                    autoSize={{ minRows: 8, maxRows: 14 }}
                  />
                  {isEmbeddingTest ? (
                    <Card size="small">
                      <Text type="secondary">
                        EB tests call the embedding API and return vectors
                        rather than generated text. Put one input text in the
                        box above.
                      </Text>
                    </Card>
                  ) : null}
                  {!isEmbeddingTest ? (
                    <Row gutter={12}>
                      <Col span={8}>
                        <Text type="secondary">Temperature</Text>
                        <InputNumber
                          value={temperature}
                          min={0}
                          max={2}
                          step={0.1}
                          onChange={(value) =>
                            setTemperature(Number(value || 0))
                          }
                          style={{ width: '100%' }}
                        />
                      </Col>
                      <Col span={8}>
                        <Text type="secondary">Max Tokens</Text>
                        <InputNumber
                          value={maxTokens}
                          min={1}
                          step={32}
                          onChange={(value) => setMaxTokens(Number(value || 1))}
                          style={{ width: '100%' }}
                        />
                      </Col>
                      <Col span={8}>
                        <Text type="secondary">Timeout</Text>
                        <InputNumber
                          value={timeout}
                          min={1}
                          step={10}
                          onChange={(value) =>
                            setTimeoutValue(Number(value || 1))
                          }
                          style={{ width: '100%' }}
                        />
                      </Col>
                    </Row>
                  ) : (
                    <div>
                      <Text type="secondary">Timeout</Text>
                      <InputNumber
                        value={timeout}
                        min={1}
                        step={10}
                        onChange={(value) =>
                          setTimeoutValue(Number(value || 1))
                        }
                        style={{ width: '100%' }}
                      />
                    </div>
                  )}
                  <Button
                    type="primary"
                    icon={<IconSend />}
                    loading={loading}
                    onClick={runTest}
                  >
                    {isEmbeddingTest
                      ? 'Run Embedding'
                      : isVisionTest
                      ? 'Run Vision Test'
                      : 'Run'}
                  </Button>
                </Space>
              </Card>
            </Col>
            <Col span={14}>
              <Space
                direction="vertical"
                size="medium"
                style={{ width: '100%' }}
              >
                <Card title="Response">
                  <Space direction="vertical" style={{ width: '100%' }}>
                    <TextArea
                      value={responseText}
                      readOnly
                      autoSize={{ minRows: 10, maxRows: 16 }}
                    />
                    <TextArea
                      value={rawResponse}
                      readOnly
                      autoSize={{ minRows: 10, maxRows: 16 }}
                    />
                  </Space>
                </Card>
                <Card
                  title="llama.cpp Debug Terminal"
                  extra={
                    <Button
                      size="small"
                      onClick={() => {
                        loadStatus();
                        loadPluginLogs();
                      }}
                    >
                      Refresh Terminal
                    </Button>
                  }
                >
                  <Space direction="vertical" style={{ width: '100%' }}>
                    <Text type="secondary">
                      Shows the latest local `llama.cpp` runtime snapshot from
                      this plugin plus current-session `llm_provider` logs.
                    </Text>
                    <div
                      style={{
                        background: '#0f172a',
                        color: '#d1fae5',
                        borderRadius: 8,
                        padding: 12,
                        fontFamily:
                          'SFMono-Regular, Consolas, Liberation Mono, Menlo, monospace',
                        fontSize: 12,
                        lineHeight: 1.6,
                        minHeight: 420,
                        maxHeight: 720,
                        overflow: 'auto',
                        whiteSpace: 'pre-wrap',
                        wordBreak: 'break-word',
                      }}
                    >
                      {`$ llm_provider.last_llama_cpp_debug\n${
                        lastLlamaCppDebugText ||
                        '(no local llama.cpp request has been recorded in this session yet)'
                      }\n\n$ tail plugin/llm_provider.log\n${
                        pluginLogText ||
                        '(no llm_provider log records found in the current session)'
                      }`}
                    </div>
                  </Space>
                </Card>
              </Space>
            </Col>
          </Row>
        </Tabs.TabPane>

        <Tabs.TabPane key="models" title="Models">
          <Space direction="vertical" size="medium" style={{ width: '100%' }}>
            <Row gutter={[16, 16]}>
              {tierOptions.map((item) => (
                <Col span={6} key={item.value}>
                  <Card>
                    <Statistic
                      title={item.label}
                      value={status.tiers?.[item.value]?.count ?? 0}
                    />
                  </Card>
                </Col>
              ))}
            </Row>
            <Card
              title="Configured Models"
              extra={
                <Button
                  type="primary"
                  icon={<IconPlus />}
                  onClick={openCreateEditor}
                >
                  Add Model
                </Button>
              }
            >
              <Table
                rowKey="key"
                columns={modelColumns}
                data={selectableRows}
                pagination={false}
              />
            </Card>
          </Space>
        </Tabs.TabPane>

        <Tabs.TabPane key="routing" title="Routing">
          <Space direction="vertical" size="medium" style={{ width: '100%' }}>
            <Card
              title="Tier Routing"
              extra={
                <Space>
                  <Button onClick={loadRouting}>Reload Routing</Button>
                  <Button
                    type="primary"
                    loading={routingSaving}
                    onClick={saveRouting}
                  >
                    Save Routing
                  </Button>
                </Space>
              }
            >
              <Text
                type="secondary"
                style={{ display: 'block', marginBottom: 16 }}
              >
                Each tier can define a preferred default model and a fallback
                scheduling strategy. Plugins only declare a tier such as `t1`,
                `t2`, `t3`, `vl`, or `eb`; this page decides which concrete
                configured model is used at runtime.
              </Text>
              <Row gutter={[16, 16]}>
                {tierOptions.map((tier) => {
                  const providers = modelsByTier[tier.value] || [];
                  const entry = routingConfig[tier.value] || {
                    default_provider: '',
                    strategy: 'balanced' as const,
                  };
                  return (
                    <Col span={12} key={tier.value}>
                      <Card title={tier.label}>
                        <Space
                          direction="vertical"
                          size="medium"
                          style={{ width: '100%' }}
                        >
                          <Text type="secondary">
                            {tierDescriptions[tier.value]}
                          </Text>
                          <Descriptions
                            column={1}
                            data={[
                              {
                                label: 'Available Models',
                                value: providers.length
                                  ? providers
                                      .map((item) => item.display_name)
                                      .join(', ')
                                  : 'None configured',
                              },
                            ]}
                          />
                          <div>
                            <Text
                              type="secondary"
                              style={{ display: 'block', marginBottom: 8 }}
                            >
                              Default Model
                            </Text>
                            <Select
                              value={entry.default_provider}
                              options={[
                                {
                                  label: 'Auto select from available models',
                                  value: '',
                                },
                                ...providers.map((item) => ({
                                  label: `${item.display_name} (${
                                    item.provider_id || item.selector
                                  })`,
                                  value: item.selector,
                                })),
                              ]}
                              placeholder="Choose default provider for this tier"
                              onChange={(value) =>
                                setRoutingConfig((prev) => ({
                                  ...prev,
                                  [tier.value]: {
                                    ...prev[tier.value],
                                    default_provider: String(value || ''),
                                  },
                                }))
                              }
                              style={{ width: '100%' }}
                            />
                            <Text
                              type="secondary"
                              style={{ display: 'block', marginTop: 8 }}
                            >
                              When this model has free capacity, it is preferred
                              first. Leave blank to let the plugin auto-select.
                            </Text>
                          </div>
                          <div>
                            <Text
                              type="secondary"
                              style={{ display: 'block', marginBottom: 8 }}
                            >
                              Load Balancing
                            </Text>
                            <Select
                              value={entry.strategy}
                              options={strategyOptions}
                              onChange={(value) =>
                                setRoutingConfig((prev) => ({
                                  ...prev,
                                  [tier.value]: {
                                    ...prev[tier.value],
                                    strategy:
                                      value === 'priority'
                                        ? 'priority'
                                        : 'balanced',
                                  },
                                }))
                              }
                              style={{ width: '100%' }}
                            />
                            <Text
                              type="secondary"
                              style={{ display: 'block', marginTop: 8 }}
                            >
                              `balanced` rotates among available models.
                              `priority` keeps preferring the lowest-load model
                              in a more stable order.
                            </Text>
                          </div>
                        </Space>
                      </Card>
                    </Col>
                  );
                })}
              </Row>
            </Card>
          </Space>
        </Tabs.TabPane>

        <Tabs.TabPane key="jobs" title="Jobs">
          <Card title="Recent Jobs">
            <Table
              rowKey="job_id"
              columns={jobColumns}
              data={status.recent_jobs || []}
              pagination={{ pageSize: 10 }}
            />
          </Card>
        </Tabs.TabPane>
      </Tabs>

      <Modal
        title={editorMode === 'create' ? 'Add Model' : 'Edit Model'}
        visible={editorVisible}
        onOk={saveProvider}
        onCancel={() => setEditorVisible(false)}
        style={{ width: 760 }}
      >
        <Space direction="vertical" size="medium" style={{ width: '100%' }}>
          <Input
            value={editorState.providerId}
            onChange={(value) =>
              setEditorState((prev) => ({ ...prev, providerId: value }))
            }
            addBefore="Provider ID"
            disabled={editorMode === 'edit'}
          />
          <Text type="secondary">
            Stable machine-readable ID used by plugins and APIs. Default derives
            from local filename or online model name.
          </Text>
          <Input
            value={editorState.displayName}
            onChange={(value) =>
              setEditorState((prev) => ({ ...prev, displayName: value }))
            }
            addBefore="Display Name"
          />
          <Text type="secondary">
            Human-friendly label shown in the UI. Default also derives from
            local filename or online model name.
          </Text>
          <Select
            value={editorState.type}
            options={providerTypeOptions}
            onChange={(value) =>
              setEditorState((prev) => ({ ...prev, type: value }))
            }
            placeholder="Model type"
            style={{ width: '100%' }}
          />
          <Switch
            checked={editorState.enabled}
            onChange={(value) =>
              setEditorState((prev) => ({ ...prev, enabled: value }))
            }
            checkedText="Enabled"
            uncheckedText="Disabled"
          />
          <Select
            value={editorState.tier}
            options={tierOptions}
            onChange={(value) =>
              setEditorState((prev) => ({ ...prev, tier: value }))
            }
            placeholder="Tier: t1=1B-8B, t2=9B+, t3=large, vl=vision, eb=embedding"
            style={{ width: '100%' }}
          />
          <Text type="secondary">
            Tier meanings: `t1` = 1B-8B, `t2` = 9B+, `t3` = larger flagship
            models, `vl` = vision-language models, `eb` = embedding models.
          </Text>
          <InputNumber
            value={editorState.maxConcurrency}
            min={1}
            step={1}
            disabled={editorState.type === 'llama_cpp'}
            onChange={(value) =>
              setEditorState((prev) => ({
                ...prev,
                maxConcurrency: Number(value || 1),
              }))
            }
            style={{ width: '100%' }}
            placeholder="Max concurrency: local is fixed at 1, online can scale"
          />
          <Text type="secondary">
            Online max concurrency controls how many requests this API target
            may serve in parallel. Local llama.cpp is always fixed at 1.
          </Text>
          <TextArea
            value={editorState.tagsText}
            onChange={(value) =>
              setEditorState((prev) => ({ ...prev, tagsText: value }))
            }
            placeholder="Tags, comma separated. Example: Qwen3.5, 9B, Q4_K_M"
            autoSize={{ minRows: 2, maxRows: 4 }}
          />
          {editorState.type === 'llama_cpp' ? (
            <>
              <Select
                value={editorState.modelPath}
                options={localFiles.map((file) => ({
                  label: `${file.id} (${(
                    file.size /
                    1024 /
                    1024 /
                    1024
                  ).toFixed(2)} GB)`,
                  value: file.path,
                }))}
                onChange={(value) =>
                  setEditorState((prev) => {
                    const selected = localFiles.find(
                      (file) => file.path === value
                    );
                    const baseName =
                      selected?.name.replace(/\.[a-z0-9]+$/i, '') || '';
                    return {
                      ...prev,
                      modelPath: value,
                      providerId: prev.providerId || toProviderId(baseName),
                      displayName: prev.displayName || baseName,
                    };
                  })
                }
                placeholder="Model Path: choose a .gguf/.bin file from storage/data/llm_provider/models"
                style={{ width: '100%' }}
              />
              <Text type="secondary">
                Choose a local gguf/bin model file under
                `storage/data/llm_provider/models`.
              </Text>
              {editorState.tier === 'vl' ? (
                <>
                  <Input
                    value={editorState.mmprojPath}
                    onChange={(value) =>
                      setEditorState((prev) => ({ ...prev, mmprojPath: value }))
                    }
                    addBefore="mmproj Path"
                    placeholder="Absolute path to the multimodal projector file"
                  />
                  <Select
                    value={editorState.mmprojPath}
                    options={mmprojFiles.map((file) => ({
                      label: `${file.id} (${(
                        file.size /
                        1024 /
                        1024 /
                        1024
                      ).toFixed(2)} GB)`,
                      value: file.path,
                    }))}
                    onChange={(value) =>
                      setEditorState((prev) => ({
                        ...prev,
                        mmprojPath: String(value || ''),
                      }))
                    }
                    placeholder="Choose mmproj: select a local projector file from storage/data/llm_provider/models"
                    style={{ width: '100%' }}
                  />
                  <Text type="secondary">
                    VL llama.cpp models need a matching `mmproj` projector file.
                    You can paste a path manually or select one from the scanned
                    local files here.
                  </Text>
                  <Select
                    value={editorState.vlHandler}
                    options={(
                      status.runtime?.llama_cpp_chat_handlers || []
                    ).map((name) => ({
                      label: name,
                      value: name,
                    }))}
                    onChange={(value) =>
                      setEditorState((prev) => ({
                        ...prev,
                        vlHandler: String(value || ''),
                      }))
                    }
                    style={{ width: '100%' }}
                    placeholder="Choose a llama_cpp.llama_chat_format handler class"
                  />
                  <Text type="secondary">
                    Pick the exact handler class exposed by
                    `llama_cpp.llama_chat_format`, for example
                    `Qwen25VLChatHandler`. Note: some local Qwen3-VL + llama.cpp
                    handler combinations are currently unstable and may be
                    blocked to avoid backend crashes.
                  </Text>
                </>
              ) : null}
              <InputNumber
                value={editorState.nCtx}
                min={256}
                step={256}
                onChange={(value) =>
                  setEditorState((prev) => ({
                    ...prev,
                    nCtx: Number(value || 4096),
                  }))
                }
                style={{ width: '100%' }}
                placeholder="n_ctx: local context window"
              />
              <Text type="secondary">
                `n_ctx` is the local context window size. `4096` means the model
                can process roughly 4096 tokens of input/output context.
              </Text>
              <InputNumber
                value={editorState.nGpuLayers}
                min={0}
                step={1}
                onChange={(value) =>
                  setEditorState((prev) => ({
                    ...prev,
                    nGpuLayers: Number(value || 0),
                  }))
                }
                style={{ width: '100%' }}
                placeholder="n_gpu_layers: offload depth"
              />
              <Text type="secondary">
                `n_gpu_layers` controls how many model layers are offloaded to
                GPU. `0` means CPU-only; higher values usually increase GPU
                usage and speed.
              </Text>
            </>
          ) : (
            <>
              <Input
                value={editorState.baseUrl}
                onChange={(value) =>
                  setEditorState((prev) => ({ ...prev, baseUrl: value }))
                }
                addBefore="Base URL"
              />
              <Text type="secondary">
                OpenAI-compatible API root, usually ending with `/v1`.
              </Text>
              <Input
                value={editorState.modelName}
                onChange={(value) =>
                  setEditorState((prev) => ({
                    ...prev,
                    modelName: value,
                    providerId: prev.providerId || toProviderId(value),
                    displayName: prev.displayName || value,
                  }))
                }
                addBefore="Model"
                placeholder="Model: remote API model name"
              />
              <Text type="secondary">
                Remote model name passed to the API. Provider ID and Display
                Name default from this value when first filled.
              </Text>
              <Input.Password
                value={editorState.apiKey}
                onChange={(value) =>
                  setEditorState((prev) => ({ ...prev, apiKey: value }))
                }
                addBefore="API Key"
                placeholder="Leave blank to keep existing secret"
              />
              <InputNumber
                value={editorState.timeout}
                min={1}
                step={5}
                onChange={(value) =>
                  setEditorState((prev) => ({
                    ...prev,
                    timeout: Number(value || 60),
                  }))
                }
                style={{ width: '100%' }}
                placeholder="Timeout: online request timeout in seconds"
              />
              <Text type="secondary">
                Maximum wait time for one online request, in seconds. `60` is a
                reasonable default for most text tasks.
              </Text>
            </>
          )}
          <InputNumber
            value={editorState.temperature}
            min={0}
            max={2}
            step={0.1}
            onChange={(value) =>
              setEditorState((prev) => ({
                ...prev,
                temperature: Number(value || 0),
              }))
            }
            style={{ width: '100%' }}
            placeholder="Temperature: default sampling value"
          />
          <Text type="secondary">
            `temperature` controls randomness. Lower values are more
            deterministic; higher values are more creative.
          </Text>
          <InputNumber
            value={editorState.maxTokens}
            min={1}
            step={32}
            onChange={(value) =>
              setEditorState((prev) => ({
                ...prev,
                maxTokens: Number(value || 1),
              }))
            }
            style={{ width: '100%' }}
            placeholder="Max Tokens: default generation cap"
          />
          <Text type="secondary">
            Upper bound for generated output tokens per request. This is not the
            full context window.
          </Text>
        </Space>
      </Modal>
    </div>
  );
};

export default LLMProviderPage;
