import React, { useRef, useState, useEffect } from 'react';
import { useHistory } from 'react-router-dom';
import {
  Button,
  Message,
  Popconfirm,
  Space,
  Card,
  Descriptions,
  Tag,
  Spin,
  Alert,
  Table,
  Modal,
  Form,
  Input,
  Typography,
  Divider,
} from '@arco-design/web-react';
import {
  IconPlus,
  IconDelete,
  IconRefresh,
  IconHistory,
  IconStorage,
  IconCode,
} from '@arco-design/web-react/icon';
import {
  listBackups,
  createBackup,
  deleteBackup,
  getBackupStatus,
  restoreBackup,
} from '@/services/backup';

const { Title } = Typography;

const PrimeBackup: React.FC = () => {
  const history = useHistory();
  const [status, setStatus] = useState<any>(null);
  const [statusLoading, setStatusLoading] = useState(true);
  const [backupsData, setBackupsData] = useState<any[]>([]);
  const [tableLoading, setTableLoading] = useState(false);

  const [createModalVisible, setCreateModalVisible] = useState(false);
  const [restoreModalVisible, setRestoreModalVisible] = useState(false);
  const [selectedBackupId, setSelectedBackupId] = useState<number | null>(null);

  const [createForm] = Form.useForm();
  const [restoreForm] = Form.useForm();

  const fetchStatus = async () => {
    setStatusLoading(true);
    try {
      const res = await getBackupStatus();
      if (res?.data) {
        setStatus(res.data);
      }
    } catch (e) {
      Message.error('Failed to load backup status');
    } finally {
      setStatusLoading(false);
    }
  };

  const fetchBackups = async () => {
    setTableLoading(true);
    try {
      const res = await listBackups();
      const data = res?.data?.backups || [];
      const sortedData = [...data].sort((a, b) => b.id - a.id);
      setBackupsData(sortedData);
    } catch (e) {
      console.error(e);
      Message.error('Failed to load backup history');
    } finally {
      setTableLoading(false);
    }
  };

  useEffect(() => {
    fetchStatus();
    fetchBackups();
  }, []);

  const handleCreate = async () => {
    try {
      const values = await createForm.validate();
      const res = await createBackup({ comment: values.comment });
      if (res.success) {
        Message.success(res.message || 'Backup task queued successfully');
        setCreateModalVisible(false);
        createForm.resetFields();
        fetchBackups();
      } else {
        Message.error(res.errorMessage || 'Failed to trigger backup');
      }
    } catch (e: any) {
      if (e?.message) Message.error(e.message);
    }
  };

  const handleDelete = async (id: number) => {
    try {
      const res = await deleteBackup({ id });
      if (res.success) {
        Message.success(res.message || 'Delete task queued successfully');
        fetchBackups();
      } else {
        Message.error(res.errorMessage || 'Failed to delete backup');
      }
    } catch (e) {
      Message.error('An error occurred');
    }
  };

  const handleRestore = async () => {
    if (selectedBackupId === null) return;
    try {
      const values = await restoreForm.validate();
      const res = await restoreBackup({
        id: selectedBackupId,
        path: values.path,
      });
      if (res.success) {
        Message.success(res.message || 'Restoration task queued successfully');
        setRestoreModalVisible(false);
        restoreForm.resetFields();
      } else {
        Message.error(res.errorMessage || 'Failed to trigger restoration');
      }
    } catch (e: any) {
      if (e?.message) Message.error(e.message);
    }
  };

  const columns = [
    {
      title: 'ID',
      dataIndex: 'id',
      width: 80,
    },
    {
      title: 'Comment',
      dataIndex: 'comment',
      ellipsis: true,
    },
    {
      title: 'Creator',
      dataIndex: 'creator',
      width: 120,
      render: (val: string) => <Tag color="arcoblue">{val}</Tag>,
    },
    {
      title: 'Timestamp',
      dataIndex: 'timestamp',
      width: 200,
      render: (val: number) => {
        if (!val) return '-';
        return new Date(val * 1000).toLocaleString();
      },
    },
    {
      title: 'Tags',
      dataIndex: 'tags',
      width: 200,
      render: (tags: any) => {
        if (!tags || Object.keys(tags).length === 0) return '-';
        return (
          <Space size={4} wrap>
            {Object.entries(tags).map(([k, v]) => (
              <Tag key={k} size="small">
                {k}: {String(v)}
              </Tag>
            ))}
          </Space>
        );
      },
    },
    {
      title: 'Action',
      width: 180,
      render: (_, record) => (
        <Space>
          <Button
            type="text"
            size="small"
            icon={<IconHistory />}
            onClick={() => {
              setSelectedBackupId(record.id);
              setRestoreModalVisible(true);
            }}
          >
            Restore
          </Button>
          <Popconfirm
            title="Delete this backup?"
            content="Are you sure to delete this backup permanently?"
            onOk={() => handleDelete(record.id)}
            okButtonProps={{ status: 'danger' }}
          >
            <Button
              status="danger"
              type="text"
              size="small"
              icon={<IconDelete />}
            >
              Delete
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  const statusItems = status
    ? [
        {
          label: 'Service State',
          value: status.enabled ? (
            <Tag color="green">Enabled</Tag>
          ) : (
            <Tag color="red">Disabled</Tag>
          ),
        },
        { label: 'Backup Source', value: status.source_root },
        { label: 'Storage Output', value: status.storage_root },
        { label: 'Concurrency', value: status.concurrency },
      ]
    : [];

  return (
    <div style={{ padding: 24 }}>
      <Title heading={5}>PrimeBackup Management</Title>
      <Typography.Text
        type="secondary"
        style={{ marginBottom: 24, display: 'block' }}
      >
        High-performance deduplicated backup system.
      </Typography.Text>
      <Button
        icon={<IconCode />}
        style={{ marginBottom: 16 }}
          onClick={() => history.push('/core/terminal')}
      >
        Terminal
      </Button>

      <Card
        style={{ marginBottom: 16 }}
        title="System Status"
        extra={
          <Button
            icon={<IconRefresh />}
            type="text"
            size="small"
            onClick={fetchStatus}
          >
            Refresh
          </Button>
        }
      >
        <Spin loading={statusLoading} style={{ width: '100%' }}>
          {status ? (
            <Descriptions
              column={2}
              data={statusItems}
              labelStyle={{ paddingRight: 32, color: 'var(--color-text-3)' }}
              valueStyle={{ fontWeight: 'bold' }}
            />
          ) : (
            <Alert
              type="error"
              content="Failed to load system status. Is the plugin properly loaded?"
            />
          )}
        </Spin>
      </Card>

      <Card
        title="Backup History"
        extra={
          <Space>
            <Button icon={<IconRefresh />} onClick={fetchBackups}>
              Refresh
            </Button>
            <Button
              type="primary"
              icon={<IconPlus />}
              onClick={() => setCreateModalVisible(true)}
            >
              Create Backup
            </Button>
          </Space>
        }
      >
        <Table
          loading={tableLoading}
          rowKey="id"
          columns={columns}
          data={backupsData}
        />
      </Card>

      {/* Create Modal */}
      <Modal
        title="Create New Backup"
        visible={createModalVisible}
        onOk={handleCreate}
        onCancel={() => setCreateModalVisible(false)}
        autoFocus={false}
        focusLock={true}
      >
        <Form form={createForm} layout="vertical">
          <Form.Item
            label="Comment"
            field="comment"
            rules={[{ required: true, message: 'Please enter a comment' }]}
          >
            <Input placeholder="Enter a brief description for this backup" />
          </Form.Item>
        </Form>
      </Modal>

      {/* Restore Modal */}
      <Modal
        title={`Restore Backup #${selectedBackupId}`}
        visible={restoreModalVisible}
        onOk={handleRestore}
        onCancel={() => setRestoreModalVisible(false)}
      >
        <Alert
          type="warning"
          showIcon
          style={{ marginBottom: 16 }}
          content="Restoring will overwrite existing files in the target directory if they have the same name."
        />
        <Form form={restoreForm} layout="vertical">
          <Form.Item
            label="Target Path"
            field="path"
            rules={[{ required: true, message: 'Please enter a target path' }]}
            extra="The relative path where the backup will be extracted (e.g. ./restored_world)."
          >
            <Input placeholder="e.g. ./restored_world" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default PrimeBackup;
