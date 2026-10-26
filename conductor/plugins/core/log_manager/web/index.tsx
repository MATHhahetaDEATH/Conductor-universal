import React, { useEffect, useMemo, useState } from 'react';
import {
  Button,
  Card,
  Checkbox,
  Grid,
  InputNumber,
  Message,
  Select,
  Space,
  Typography,
} from '@arco-design/web-react';
import {
  IconCode,
  IconDownload,
  IconRefresh,
  IconSave,
} from '@arco-design/web-react/icon';
import Editor from '@monaco-editor/react';
import { useHistory } from 'react-router-dom';
import { authorizedFetch, requestJson } from '@/utils/request';

const { Title, Text } = Typography;
const { Row, Col } = Grid;

const levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'];
const categories = ['core', 'plugin', 'web'];

const LogManager: React.FC = () => {
  const history = useHistory();
  const [records, setRecords] = useState<any[]>([]);
  const [files, setFiles] = useState<any[]>([]);
  const [settings, setSettings] = useState<any>({});
  const [draftSettings, setDraftSettings] = useState<any>({});
  const [category, setCategory] = useState<string>('plugin');
  const [owner, setOwner] = useState<string>();
  const [selectedLevels, setSelectedLevels] = useState<string[]>([
    'INFO',
    'WARNING',
    'ERROR',
    'CRITICAL',
  ]);

  const ownerOptions = useMemo(() => {
    return files
      .filter((file) => file.category === category)
      .map((file) => ({ label: file.owner, value: file.owner }));
  }, [files, category]);

  const loadSettings = async () => {
    const data = await requestJson('/api/logs/settings');
    setSettings(data || {});
    setDraftSettings(data || {});
  };

  const loadFiles = async () => {
    const data = await requestJson<{ files?: any[] }>('/api/logs/files');
    setFiles(data?.files || []);
  };

  const loadRecords = async () => {
    const params = new URLSearchParams();
    params.set('category', category);
    if (owner) params.set('owner', owner);
    if (selectedLevels.length) params.set('levels', selectedLevels.join(','));
    params.set('limit', '500');
    const data = await requestJson<{ records?: any[] }>(`/api/logs/records?${params.toString()}`);
    setRecords(data?.records || []);
  };

  useEffect(() => {
    loadSettings().catch((error) => Message.error(error?.message || 'Failed to load log settings'));
    loadFiles().catch((error) => Message.error(error?.message || 'Failed to load log files'));
  }, []);

  useEffect(() => {
    const refreshRecords = () =>
      loadRecords().catch((error) => Message.error(error?.message || 'Failed to load log records'));
    refreshRecords();
    const timer = window.setInterval(refreshRecords, 2000);
    return () => window.clearInterval(timer);
  }, [category, owner, selectedLevels.join(',')]);

  const setLevel = async (level: string) => {
    try {
      const nextSettings = { ...draftSettings, level };
      setDraftSettings(nextSettings);
      await requestJson('/api/logs/settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(nextSettings),
      });
      await loadSettings();
      Message.success('Log level updated');
    } catch (error: any) {
      Message.error(error?.message || 'Failed to update log level');
    }
  };

  const saveRetention = async () => {
    try {
      await requestJson('/api/logs/settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(draftSettings),
      });
      Message.success('Log settings saved');
      await Promise.all([loadSettings(), loadFiles()]);
    } catch (error: any) {
      Message.error(error?.message || 'Failed to save log settings');
    }
  };

  const downloadLogs = async () => {
    if (!owner) return;
    try {
      const response = await authorizedFetch(`/api/logs/download?category=${encodeURIComponent(category)}&owner=${encodeURIComponent(owner)}`);
      if (!response.ok) throw new Error(`Download failed (${response.status})`);
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `${category}-${owner}.log`;
      link.click();
      URL.revokeObjectURL(url);
    } catch (error: any) {
      Message.error(error?.message || 'Download failed');
    }
  };
  const logText = records.map((record) => record.line).join('\n');

  return (
    <div style={{ padding: 24 }}>
      <Title heading={5}>Logs</Title>
      <Text type="secondary" style={{ display: 'block', marginBottom: 24 }}>
        Realtime logs from the current startup session.
      </Text>
      <Button
        icon={<IconCode />}
        style={{ marginBottom: 16 }}
        onClick={() => history.push('/core/terminal')}
      >
        Terminal
      </Button>

      <Card style={{ marginBottom: 16 }}>
        <Row gutter={[16, 16]}>
          <Col span={5}>
            <Text type="secondary">Session</Text>
            <div>{settings.session}</div>
          </Col>
          <Col span={5}>
            <Text type="secondary">Root Level</Text>
            <Select
              value={settings.level}
              onChange={setLevel}
              style={{ width: '100%', marginTop: 4 }}
            >
              {levels.map((level) => (
                <Select.Option key={level} value={level}>
                  {level}
                </Select.Option>
              ))}
            </Select>
          </Col>
          <Col span={5}>
            <Text type="secondary">Max Storage (MB)</Text>
            <InputNumber
              min={1}
              value={draftSettings.max_total_mb}
              onChange={(value) =>
                setDraftSettings({ ...draftSettings, max_total_mb: value })
              }
              style={{ width: '100%', marginTop: 4 }}
            />
          </Col>
          <Col span={5}>
            <Text type="secondary">Max Age (Days)</Text>
            <InputNumber
              min={0}
              value={draftSettings.max_age_days}
              onChange={(value) =>
                setDraftSettings({ ...draftSettings, max_age_days: value })
              }
              style={{ width: '100%', marginTop: 4 }}
            />
          </Col>
          <Col span={4}>
            <Text type="secondary">Retention</Text>
            <Button
              icon={<IconSave />}
              type="primary"
              long
              style={{ marginTop: 4 }}
              onClick={saveRetention}
            >
              Save
            </Button>
          </Col>
          <Col span={24}>
            <Text type="secondary">Directory</Text>
            <div style={{ wordBreak: 'break-all' }}>{settings.session_dir}</div>
          </Col>
        </Row>
      </Card>

      <Card>
        <Space style={{ marginBottom: 16 }} wrap>
          <Select
            value={category}
            onChange={(value) => {
              setCategory(value);
              setOwner(undefined);
            }}
            style={{ width: 140 }}
          >
            {categories.map((item) => (
              <Select.Option key={item} value={item}>
                {item}
              </Select.Option>
            ))}
          </Select>
          <Select
            allowClear
            value={owner}
            placeholder="All owners"
            options={ownerOptions}
            onChange={setOwner}
            style={{ width: 180 }}
          />
          <Checkbox.Group
            options={levels}
            value={selectedLevels}
            onChange={setSelectedLevels}
          />
          <Button
            icon={<IconRefresh />}
            onClick={() => {
              Promise.all([loadFiles(), loadRecords()]).catch((error) =>
                Message.error(error?.message || 'Failed to refresh logs')
              );
            }}
          >
            Refresh
          </Button>
          {owner && (
            <Button icon={<IconDownload />} onClick={downloadLogs}>Download</Button>
          )}
        </Space>
        <Editor
          height="620px"
          language="log"
          value={logText}
          theme="vs-dark"
          options={{
            readOnly: true,
            minimap: { enabled: false },
            fontSize: 13,
            scrollBeyondLastLine: false,
            automaticLayout: true,
            wordWrap: 'on',
          }}
        />
      </Card>
    </div>
  );
};

export default LogManager;
