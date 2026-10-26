import React, { useState, useEffect } from 'react';
import { useHistory } from 'react-router-dom';
import {
  Card,
  Grid,
  Statistic,
  Button,
  Message,
  Space,
  Typography,
} from '@arco-design/web-react';
import {
  IconCode,
  IconPoweroff,
  IconRefresh,
} from '@arco-design/web-react/icon';

const { Row, Col } = Grid;

const Dashboard: React.FC = () => {
  const history = useHistory();
  const [status, setStatus] = useState<any>(null);

  const fetchStatus = async () => {
    try {
      const resp = await fetch('/api/dashboard/status');
      const data = await resp.json();
      if (data.success) {
        setStatus(data.data);
      }
    } catch (e) {
      Message.error('Failed to fetch system status');
    }
  };

  useEffect(() => {
    fetchStatus();
    const timer = setInterval(fetchStatus, 5000);
    return () => clearInterval(timer);
  }, []);

  const formatUptime = (seconds: number) => {
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = seconds % 60;
    return `${h}h ${m}m ${s}s`;
  };

  return (
    <div style={{ padding: 24 }}>
      <Typography.Title heading={5}>System Dashboard</Typography.Title>
      <Typography.Text
        type="secondary"
        style={{ marginBottom: 24, display: 'block' }}
      >
        Overview of Conductor Kernel status.
      </Typography.Text>

      <Row gutter={[16, 16]}>
        <Col span={6}>
          <Card bordered={false}>
            <Statistic
              title="Kernel Version"
              value={status?.version || '...'}
              style={{ color: '#3f51b5' }}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card bordered={false}>
            <Statistic
              title="System Uptime"
              value={status ? formatUptime(status.uptime) : '...'}
              style={{ color: '#cf1322' }}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card bordered={false}>
            <Statistic
              title="Loaded Plugins"
              value={status?.plugins_count || 0}
              suffix="Total"
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card bordered={false}>
            <Statistic
              title="Debug Mode"
              value={status?.debug ? 'Enabled' : 'Disabled'}
            />
          </Card>
        </Col>
      </Row>

      <Card title="Quick Actions" style={{ marginTop: 24 }}>
        <Space size="medium">
          <Button
            status="danger"
            icon={<IconPoweroff />}
            onClick={() => Message.info('Shutdown command sent (Mock)')}
          >
            Shutdown Kernel
          </Button>
          <Button icon={<IconRefresh />} onClick={() => fetchStatus()}>
            Refresh Data
          </Button>
          <Button
            icon={<IconCode />}
            onClick={() => history.push('/core/terminal')}
          >
            Terminal
          </Button>
        </Space>
      </Card>
    </div>
  );
};

export default Dashboard;
