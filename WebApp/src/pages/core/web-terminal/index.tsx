import React, { useState } from 'react';
import { Button, Card, Input, Message, Space, Typography } from '@arco-design/web-react';
import { requestJson } from '@/utils/request';

const WebTerminal: React.FC = () => {
  const [input, setInput] = useState('!!help');
  const [output, setOutput] = useState('');
  const execute = async () => {
    try {
      const data = await requestJson<{ responses?: Array<{ message: string }> }>('/api/core/cli/execute', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ input }) });
      const responses = data?.responses || [];
      setOutput(responses.length ? responses.map((item) => item.message).join('\n') : '(No response)');
    } catch (error: any) {
      Message.error(error?.message || 'Unable to reach command service');
      setOutput('');
    }
  };
  return <Card style={{ margin: 24 }}><Typography.Title heading={5}>Core Web Terminal</Typography.Title><Space direction="vertical" style={{ width: '100%' }}><Input value={input} onChange={setInput} onPressEnter={execute} /><Button type="primary" onClick={execute}>Execute</Button><pre>{output}</pre></Space></Card>;
};

export default WebTerminal;
