import React, { useState } from 'react';
import { Button, Card, Input, Message, Space, Typography } from '@arco-design/web-react';

const WebTerminal: React.FC = () => {
  const [input, setInput] = useState('!!help');
  const [output, setOutput] = useState('');
  const execute = async () => {
    const response = await fetch('/api/core/cli/execute', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ input }) });
    const payload = await response.json();
    if (!payload.success) Message.error(payload.errorMessage || 'Command failed');
    setOutput((payload.data?.responses || []).map((item) => item.message).join('\n'));
  };
  return <Card style={{ margin: 24 }}><Typography.Title heading={5}>Core Web Terminal</Typography.Title><Space direction="vertical" style={{ width: '100%' }}><Input value={input} onChange={setInput} onPressEnter={execute} /><Button type="primary" onClick={execute}>Execute</Button><pre>{output}</pre></Space></Card>;
};

export default WebTerminal;
