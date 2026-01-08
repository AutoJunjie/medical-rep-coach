# Amazon Nova 2 Sonic 语音交互功能指南

## 概述

本项目集成了 Amazon Nova 2 Sonic 语音到语音模型，实现实时语音对话功能，并支持工具调用（Tool Use）。Nova 2 Sonic 通过双向流式 API 实现低延迟的语音交互体验，同时支持在对话过程中动态调用工具获取信息。

## 功能特性

### ✅ 已实现功能

#### 后端功能
- **AWS Bedrock Runtime 客户端配置**：使用双向流式 API 与 Nova Sonic 通信
- **WebSocket 端点**：`/voice/stream` 支持实时音频流传输
- **双向音频流**：
  - 接收前端发送的音频数据
  - 流式传输到 Nova Sonic 进行处理
  - 将 Nova Sonic 的响应流式返回前端
- **Nova Sonic 输出事件处理**：
  - ASR 转录（用户语音转文字）
  - 文本响应（模型的文字回答）
  - 音频响应（模型的语音输出）
  - 工具使用事件（Tool Use）
- **工具配置和执行**：
  - 使用 `promptStart` 事件的 `toolConfig` 字段配置工具
  - Nova 2 Sonic 特定格式：包含 `toolSpec` 的工具定义
  - 处理模型返回的 `toolUse` 事件
  - 执行工具并通过 `toolResult` 事件返回结果
- **对话上下文维护**：跨音频交互保持对话历史
- **错误处理**：处理音频流中断和 API 失败

#### 工具集成
项目集成了以下工具，可在语音对话中被 Nova Sonic 调用：

1. **scenario_tool**：生成医生人设和场景开场白
2. **objection_tool**：列出常见异议和应对要点
3. **eval_tool**：评估医药代表回答的准确性和合规性

#### 前端功能
- **麦克风访问和音频录制**：使用 Web Audio API
- **WebSocket 客户端**：实时音频流传输
- **音频播放**：播放 Nova Sonic 的语音响应
- **可视化指示器**：
  - 录音状态指示
  - 流式传输状态
  - 语音活动检测
- **按键说话/语音激活控制**
- **文本聊天界面**：与语音界面并存
- **转录显示**：显示用户语音和 AI 响应的文字

### 医疗培训流程集成
- **医生人设场景**：语音交互配合现有医生人设
- **医药代表响应**：支持语音输入回答
- **医生问题和教练反馈**：支持语音输出
- **对话历史保存**：包含语音交互的完整记录

## 技术架构

### Nova 2 Sonic 双向流式 API 工作流程

Nova 2 Sonic 使用特殊的双向流式 API，与标准的 Bedrock Converse API 不同。工作流程如下：

#### 1. 会话初始化

```python
# 发送 sessionStart 事件
{
    "sessionStart": {
        "sessionId": "unique-session-id",
        "inferenceConfig": {
            "temperature": 0.7,
            "maxTokens": 1500
        }
    }
}
```

#### 2. 提示开始（包含工具配置）

```python
# 发送 promptStart 事件，配置工具
{
    "promptStart": {
        "promptName": "unique-prompt-name",
        "sessionId": "session-id",
        "system": [{"text": "System prompt"}],
        "audioConfig": {
            "voice": "en-US-Neutral",
            "language": "en-US"
        },
        "toolConfig": {
            "tools": [
                {
                    "toolSpec": {
                        "name": "scenario_tool",
                        "description": "Generate doctor persona and opening line",
                        "inputSchema": {
                            "json": {
                                "type": "object",
                                "properties": {
                                    "drug": {"type": "string"},
                                    "specialty": {"type": "string"}
                                },
                                "required": ["drug", "specialty"]
                            }
                        }
                    }
                }
            ],
            "toolChoice": {"auto": {}}
        }
    }
}
```

#### 3. 音频流传输

```python
# 发送音频数据块
{
    "audioChunk": {
        "promptName": "prompt-name",
        "sessionId": "session-id",
        "audio": b"raw audio bytes"
    }
}

# 音频结束
{
    "audioEnd": {
        "promptName": "prompt-name",
        "sessionId": "session-id"
    }
}
```

#### 4. 处理输出事件

Nova Sonic 返回的事件序列：

```python
# 1. 完成开始
{"completionStart": {"sessionId": "...", "promptName": "...", "completionId": "..."}}

# 2. ASR 转录（用户说的话）
{"contentStart": {"contentType": "text", "role": "USER"}}
{"text": "转录的用户语音文本"}
{"contentEnd": {}}

# 3. 工具使用（如果模型决定调用工具）
{"contentStart": {"contentType": "toolUse"}}
{
    "toolUse": {
        "toolUseId": "tool-use-id-123",
        "name": "scenario_tool",
        "input": {
            "drug": "阿司匹林",
            "specialty": "心内科"
        }
    }
}
{"contentEnd": {}}

# 4. 文本响应（模型计划说的话）
{"contentStart": {"contentType": "text", "role": "ASSISTANT"}}
{"text": "模型的文本响应"}
{"contentEnd": {}}

# 5. 音频响应（模型的语音）
{"contentStart": {"contentType": "audio"}}
{"audio": {"bytes": b"audio data", "format": "pcm"}}
{"contentEnd": {}}

# 6. 完成结束
{"completionEnd": {"stopReason": "end_turn"}}
```

#### 5. 工具结果返回

当模型调用工具后，需要发送工具执行结果：

```python
# 发送 toolResult 事件
{
    "toolResult": {
        "promptName": "prompt-name",
        "sessionId": "session-id",
        "toolUseId": "tool-use-id-123",
        "content": [
            {"text": "工具执行结果"}
        ]
    }
}
```

模型会接收工具结果后继续生成响应。

## 配置说明

### 环境变量

在 `.env` 文件中配置以下变量：

```bash
# AWS 凭证
AWS_ACCESS_KEY_ID="your-access-key"
AWS_SECRET_ACCESS_KEY="your-secret-key"
AWS_REGION="us-east-1"

# Bedrock 模型配置（用于文本聊天）
BEDROCK_MODEL_ID="anthropic.claude-3-sonnet-20240229-v1:0"

# Nova 2 Sonic 语音配置
NOVA_SONIC_MODEL_ID="amazon.nova-sonic-v2:0"
NOVA_SONIC_VOICE="en-US-Neutral"
NOVA_SONIC_LANGUAGE="en-US"
NOVA_SONIC_TEMPERATURE="0.7"
```

### 支持的语音选项

Nova 2 Sonic 支持多种语音和语言：

- **英语**：`en-US-Neutral`, `en-US-Female`, `en-US-Male`
- **中文**：`zh-CN-Neutral`, `zh-CN-Female`, `zh-CN-Male`
- 更多语言请参考 AWS 文档

## 工具定义格式

### Nova 2 Sonic 工具定义结构

```python
{
    "name": "tool_name",
    "description": "Clear description of what the tool does",
    "input_schema": {
        "type": "object",
        "properties": {
            "param1": {
                "type": "string",
                "description": "Description of param1"
            },
            "param2": {
                "type": "string",
                "enum": ["option1", "option2"],
                "description": "Description of param2"
            }
        },
        "required": ["param1"]
    }
}
```

### 工具注册

在 `main.py` 中注册工具处理函数：

```python
voice_handler = NovaSonicVoiceHandler()

# 注册工具
voice_handler.register_tool("scenario_tool", scenario_tool)
voice_handler.register_tool("objection_tool", objection_tool)
voice_handler.register_tool("eval_tool", eval_tool)
```

### 工具执行流程

1. 客户端发送音频输入
2. Nova Sonic 处理并决定是否需要调用工具
3. 如果需要，返回 `toolUse` 事件
4. 服务器执行工具函数
5. 发送 `toolResult` 事件给模型
6. 模型使用工具结果生成最终响应

## API 端点

### 1. 检查语音功能状态

```http
GET /voice/status
```

**响应示例**：
```json
{
    "enabled": true,
    "model": "amazon.nova-sonic-v2:0"
}
```

### 2. WebSocket 语音流

```
ws://localhost:5000/voice/stream
```

#### 消息格式

**客户端 → 服务器**：

1. 开始会话
```json
{
    "type": "start_session",
    "session_id": "unique-session-id",
    "system_prompt": "你是一个医药代表培训协调员。",
    "doctor_persona": {...}
}
```

2. 发送音频块
```json
{
    "type": "audio_chunk",
    "audio": "base64-encoded-audio-data"
}
```

3. 音频结束
```json
{
    "type": "audio_end"
}
```

4. 结束会话
```json
{
    "type": "end_session"
}
```

**服务器 → 客户端**：

1. 连接确认
```json
{
    "type": "connected",
    "message": "Voice stream connected"
}
```

2. ASR 转录
```json
{
    "type": "transcription",
    "text": "用户说的话",
    "role": "user"
}
```

3. 文本响应
```json
{
    "type": "text_response",
    "text": "AI 的文字回答",
    "speaker": "Assistant"
}
```

4. 音频响应
```json
{
    "type": "audio_chunk",
    "audio": "base64-encoded-audio",
    "format": "pcm"
}
```

5. 工具使用通知
```json
{
    "type": "tool_use",
    "toolName": "scenario_tool",
    "toolUseId": "tool-use-id"
}
```

6. 工具结果通知
```json
{
    "type": "tool_result",
    "toolUseId": "tool-use-id",
    "result": {...}
}
```

7. 处理完成
```json
{
    "type": "processing_complete",
    "stopReason": "end_turn"
}
```

## 前端集成示例

### HTML 结构

```html
<div id="voice-controls">
    <button id="start-recording" class="voice-btn">
        🎤 开始录音
    </button>
    <button id="stop-recording" class="voice-btn" disabled>
        ⏹️ 停止录音
    </button>
    <div id="voice-status">准备就绪</div>
</div>

<div id="transcription-display">
    <!-- 显示转录和响应 -->
</div>
```

### JavaScript WebSocket 连接

```javascript
// 连接 WebSocket
const ws = new WebSocket('ws://localhost:5000/voice/stream');

// 音频上下文
let audioContext;
let mediaRecorder;
let sessionId;

ws.onopen = () => {
    console.log('WebSocket connected');
    
    // 开始会话
    sessionId = generateSessionId();
    ws.send(JSON.stringify({
        type: 'start_session',
        session_id: sessionId,
        system_prompt: '你是一个医药代表培训协调员。'
    }));
};

ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    
    switch(data.type) {
        case 'transcription':
            displayTranscription(data.text, 'user');
            break;
        case 'text_response':
            displayTranscription(data.text, 'assistant');
            break;
        case 'audio_chunk':
            playAudioChunk(data.audio, data.format);
            break;
        case 'tool_use':
            console.log(`Tool being used: ${data.toolName}`);
            break;
        case 'processing_complete':
            console.log('Processing complete');
            break;
    }
};

// 开始录音
async function startRecording() {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    audioContext = new AudioContext({ sampleRate: 16000 });
    
    mediaRecorder = new MediaRecorder(stream);
    
    mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
            // 转换为 base64 并发送
            const reader = new FileReader();
            reader.onload = () => {
                const base64Audio = btoa(reader.result);
                ws.send(JSON.stringify({
                    type: 'audio_chunk',
                    audio: base64Audio
                }));
            };
            reader.readAsBinaryString(event.data);
        }
    };
    
    mediaRecorder.start(100); // 每 100ms 发送一次
}

// 停止录音
function stopRecording() {
    if (mediaRecorder && mediaRecorder.state === 'recording') {
        mediaRecorder.stop();
        ws.send(JSON.stringify({ type: 'audio_end' }));
    }
}
```

## 使用场景示例

### 场景 1：基本语音对话

用户通过麦克风说话，Nova Sonic 识别语音、生成文本响应和语音响应。

### 场景 2：语音触发工具调用

用户说："请帮我设置一个心内科医生的培训场景，药品是阿司匹林。"

Nova Sonic 识别后调用 `scenario_tool`，生成医生人设和开场白。

### 场景 3：多轮对话与工具

1. 用户语音输入医药代表的回答
2. Nova Sonic 调用 `eval_tool` 评估回答
3. 返回评分和改进建议（文本 + 语音）

## 最佳实践

### 工具定义
- **清晰的描述**：工具描述要准确，帮助模型理解何时使用
- **参数说明**：每个参数都要有详细的 description
- **必需参数**：明确指定 required 字段

### 系统提示
- **引导工具使用**：在系统提示中说明可用的工具
- **设定角色**：明确 AI 的角色和任务
- **语言风格**：指定期望的回答风格

### 错误处理
- **网络中断**：检测 WebSocket 连接状态
- **音频质量**：处理低质量音频输入
- **工具执行失败**：返回有意义的错误信息

### 性能优化
- **音频缓冲**：合理设置音频块大小
- **并发控制**：限制同时进行的会话数
- **资源清理**：及时清理结束的会话

## 故障排除

### 问题 1：语音无法识别

**可能原因**：
- 麦克风权限未授予
- 音频格式不正确
- 采样率不匹配

**解决方案**：
- 检查浏览器麦克风权限
- 确保音频格式为 PCM 16kHz
- 查看浏览器控制台错误信息

### 问题 2：工具未被调用

**可能原因**：
- 工具定义不清晰
- 系统提示未提及工具
- 用户输入与工具功能不匹配

**解决方案**：
- 改进工具 description
- 在系统提示中明确说明工具功能
- 调整 temperature 参数（降低以提高确定性）

### 问题 3：连接中断

**可能原因**：
- 网络不稳定
- AWS 凭证过期
- Bedrock 配额超限

**解决方案**：
- 实现自动重连机制
- 刷新 AWS 凭证
- 检查 AWS 账户配额

## 参考资料

- [Amazon Nova 2 Sonic User Guide](https://docs.aws.amazon.com/nova/latest/nova2-userguide/)
- [Nova Sonic Tool Configuration](https://docs.aws.amazon.com/nova/latest/nova2-userguide/sonic-tool-configuration.html)
- [Bidirectional Streaming API](https://docs.aws.amazon.com/nova/latest/userguide/input-events.html)
- [Tool Use Documentation](https://docs.aws.amazon.com/nova/latest/userguide/speech-tools-use.html)

## 更新日志

### v2.0 - 2026-01-08
- ✅ 实现 Nova 2 Sonic 双向流式 API 集成
- ✅ 添加工具配置支持（promptStart.toolConfig）
- ✅ 实现 toolUse 事件处理
- ✅ 实现 toolResult 事件发送
- ✅ 集成三个医疗培训工具（scenario, objection, eval）
- ✅ 完善错误处理和日志记录
- 🔧 修复工具解析问题（相比 v1.0）

### v1.0 - 2026-01-07
- ❌ 初始实现（存在工具使用解析问题）
- ⚠️ 已回滚
