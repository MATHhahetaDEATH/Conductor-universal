import React, { useEffect, useState } from 'react';
import {
  Button,
  Card,
  Grid,
  Input,
  Space,
  Typography,
  Message,
} from '@arco-design/web-react';

const { Row, Col } = Grid;
const { Title, Text } = Typography;

const HelloWorld: React.FC = () => {
  const [name, setName] = useState('');
  const [greeting, setGreeting] = useState('Hello');
  const [result, setResult] = useState('');

  const loadState = async () => {
    try {
      const res = await fetch('/api/hello_world/state');
      const data = await res.json();
      const state = data?.data || {};
      setGreeting(state.greeting || 'Hello');
      setName(state.last_name || 'world');
      setResult(`${state.greeting || 'Hello'}, ${state.last_name || 'world'}!`);
    } catch (e) {
      Message.error('Failed to load saved name');
    }
  };

  useEffect(() => {
    loadState();
  }, []);

  const sayHello = async () => {
    const target = name.trim() || 'world';
    try {
      const res = await fetch('/api/hello_world/state', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: target }),
      });
      const data = await res.json();
      const state = data?.data || {};
      setGreeting(state.greeting || greeting);
      setName(state.last_name || target);
      setResult(`${state.greeting || greeting}, ${state.last_name || target}!`);
    } catch (e) {
      Message.error('Failed to save name');
    }
  };

  return (
    <div style={{ padding: 24 }}>
      <Title heading={5}>Hello World</Title>
      <Text type="secondary" style={{ display: 'block', marginBottom: 24 }}>
        Native TSX page for the example plugin.
      </Text>

      <Row gutter={[16, 16]}>
        <Col span={12}>
          <Card title="Native React">
            <Space direction="vertical" size="large" style={{ width: '100%' }}>
              <Input
                value={name}
                onChange={setName}
                placeholder="Type a name"
                onPressEnter={sayHello}
              />
              <Space>
                <Button type="primary" onClick={sayHello}>
                  Go
                </Button>
              </Space>
              <Title heading={6} style={{ margin: 0 }}>
                {result || `${greeting}, ...`}
              </Title>
            </Space>
          </Card>
        </Col>
      </Row>
    </div>
  );
};

export default HelloWorld;
