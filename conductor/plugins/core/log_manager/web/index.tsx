import React, { useEffect, useMemo, useState } from 'react';
import {
  Button,
  Card,
  Checkbox,
  Grid,
  InputNumber,
  Link,
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
    const res = await fetch('/api/logs/settings');
    const data = await res.json();
    setSettings(data.data || {});
    setDraftSettings(data.data || {});
  };

  const loadFiles = async () => {
    const res = await fetch('/api/logs/files');
    const data = await res.json();
    setFiles(data?.data?.files || []);
  };

  const loadRecords = async () => {
    const params = new URLSearchParams();
    params.set('category', category);
    if (owner) params.set('owner', owner);
    if (selectedLevels.length) params.set('levels', selectedLevels.join(','));
    params.set('limit', '500');
    const res = await fetch(`/api/logs/records?${params.toString()}`);
    const data = await res.json();
    setRecords(data?.data?.records || []);
  };

  useEffect(() => {
    loadSettings();
    loadFiles();
  }, []);

  useEffect(() => {
    loadRecords();
    const timer = window.setInterval(loadRecords, 2000);
    return () => window.clearInterval(timer);
  }, [category, owner, selectedLevels.join(',')]);

  const setLevel = async (level: string) => {
    const nextSettings = { ...draftSettings, level };
    setDraftSettings(nextSettings);
    await fetch('/api/logs/settings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(nextSettings),
    });
    loadSettings();
  };

  const saveRetention = async () => {
    const res = await fetch('/api/logs/settings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(draftSettings),
    });
    const data = await res.json();
    if (data.success) {
      Message.success('Log settings saved');
      loadSettings();
      loadFiles();
    } else {
      Message.error(data.errorMessage || 'Failed to save log settings');
    }
  };

  const downloadUrl = owner
    ? `/api/logs/download?category=${category}&owner=${owner}`
    : '';
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
              loadFiles();
              loadRecords();
            }}
          >
            Refresh
          </Button>
          {downloadUrl && (
            <Link href={downloadUrl}>
              <Button icon={<IconDownload />}>Download</Button>
            </Link>
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
