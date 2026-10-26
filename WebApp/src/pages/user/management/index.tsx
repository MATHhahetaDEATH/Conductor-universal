import React, { useEffect, useState } from 'react';
import axios from 'axios';
import {
  Button,
  Card,
  Form,
  Input,
  Message,
  Modal,
  Popconfirm,
  Select,
  Space,
  Switch,
  Table,
  Tag,
} from '@arco-design/web-react';
import {
  IconDelete,
  IconEdit,
  IconPlus,
  IconRefresh,
} from '@arco-design/web-react/icon';
import useLocale from '@/utils/useLocale';
import styles from './style/index.module.less';

type UserRecord = {
  username: string;
  name: string;
  display_name: string;
  permission_level: number;
  permission_name: string;
  disabled: boolean;
  created_at?: string;
};

const permissionOptions = [
  { label: 'GUEST', value: 0 },
  { label: 'USER', value: 1 },
  { label: 'HELPER', value: 2 },
  { label: 'ADMIN', value: 3 },
  { label: 'OWNER', value: 4 },
];

function UserManagement() {
  const t = useLocale();
  const [users, setUsers] = useState<UserRecord[]>([]);
  const [loading, setLoading] = useState(false);
  const [visible, setVisible] = useState(false);
  const [editingUser, setEditingUser] = useState<UserRecord | null>(null);
  const [saving, setSaving] = useState(false);
  const [form] = Form.useForm();

  const fetchUsers = () => {
    setLoading(true);
    axios
      .get('/api/users')
      .then((res) => setUsers(res.data.data || []))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    fetchUsers();
  }, []);

  const openCreate = () => {
    setEditingUser(null);
    form.resetFields();
    form.setFieldsValue({ permission_level: 1, disabled: false });
    setVisible(true);
  };

  const openEdit = (record: UserRecord) => {
    setEditingUser(record);
    form.resetFields();
    form.setFieldsValue({
      display_name: record.display_name,
      permission_level: record.permission_level,
      disabled: record.disabled,
    });
    setVisible(true);
  };

  const submit = async () => {
    const values = await form.validate();
    setSaving(true);
    const request = editingUser
      ? axios.patch(`/api/users/${editingUser.username}`, values)
      : axios.post('/api/users', values);
    request
      .then(() => {
        Message.success(t['user.management.saveSuccess']);
        setVisible(false);
        fetchUsers();
      })
      .catch((error) => {
        Message.error(
          error?.response?.data?.errorMessage || t['user.management.saveFailed']
        );
      })
      .finally(() => setSaving(false));
  };

  const remove = (username: string) => {
    axios
      .delete(`/api/users/${username}`)
      .then(() => {
        Message.success(t['user.management.deleteSuccess']);
        fetchUsers();
      })
      .catch((error) => {
        Message.error(
          error?.response?.data?.errorMessage ||
            t['user.management.deleteFailed']
        );
      });
  };

  const columns = [
    {
      title: t['user.management.username'],
      dataIndex: 'username',
      render: (_, record: UserRecord) => (
        <Space>
          <span className={styles.username}>{record.username}</span>
          {record.username === 'root' && <Tag color="arcoblue">OWNER</Tag>}
        </Space>
      ),
    },
    {
      title: t['user.management.displayName'],
      dataIndex: 'display_name',
    },
    {
      title: t['user.management.permission'],
      dataIndex: 'permission_name',
      render: (value: string) => (
        <Tag color={value === 'OWNER' ? 'red' : 'green'}>{value}</Tag>
      ),
    },
    {
      title: t['user.management.status'],
      dataIndex: 'disabled',
      render: (disabled: boolean) => (
        <Tag color={disabled ? 'gray' : 'green'}>
          {disabled
            ? t['user.management.disabled']
            : t['user.management.enabled']}
        </Tag>
      ),
    },
    {
      title: t['user.management.createdAt'],
      dataIndex: 'created_at',
      render: (value: string) =>
        value ? new Date(value).toLocaleString() : '-',
    },
    {
      title: t['user.management.actions'],
      render: (_, record: UserRecord) => (
        <Space>
          <Button
            icon={<IconEdit />}
            size="small"
            type="text"
            onClick={() => openEdit(record)}
          />
          <Popconfirm
            title={t['user.management.deleteConfirm']}
            disabled={record.username === 'root'}
            onOk={() => remove(record.username)}
          >
            <Button
              icon={<IconDelete />}
              size="small"
              type="text"
              status="danger"
              disabled={record.username === 'root'}
            />
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <Card>
      <div className={styles.toolbar}>
        <div>
          <div className={styles.title}>{t['menu.user.management']}</div>
          <div className={styles.subtitle}>{t['user.management.subtitle']}</div>
        </div>
        <Space>
          <Button icon={<IconRefresh />} onClick={fetchUsers} />
          <Button type="primary" icon={<IconPlus />} onClick={openCreate}>
            {t['user.management.create']}
          </Button>
        </Space>
      </div>
      <Table
        rowKey="username"
        columns={columns}
        data={users}
        loading={loading}
        pagination={false}
      />
      <Modal
        title={
          editingUser
            ? t['user.management.editUser']
            : t['user.management.createUser']
        }
        visible={visible}
        confirmLoading={saving}
        onCancel={() => setVisible(false)}
        onOk={submit}
      >
        <Form form={form} layout="vertical">
          {!editingUser && (
            <Form.Item
              field="username"
              label={t['user.management.username']}
              rules={[{ required: true }]}
            >
              <Input />
            </Form.Item>
          )}
          <Form.Item
            field="display_name"
            label={t['user.management.displayName']}
          >
            <Input />
          </Form.Item>
          <Form.Item
            field="password"
            label={
              editingUser
                ? t['user.management.newPassword']
                : t['user.management.password']
            }
            rules={editingUser ? [] : [{ required: true }]}
          >
            <Input.Password />
          </Form.Item>
          <Form.Item
            field="permission_level"
            label={t['user.management.permission']}
            rules={[{ required: true }]}
          >
            <Select options={permissionOptions} />
          </Form.Item>
          <Form.Item
            field="disabled"
            label={t['user.management.disabled']}
            triggerPropName="checked"
          >
            <Switch disabled={editingUser?.username === 'root'} />
          </Form.Item>
        </Form>
      </Modal>
    </Card>
  );
}

export default UserManagement;
