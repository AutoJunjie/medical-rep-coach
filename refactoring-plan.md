# Med Coach 前端重构计划

## 1. 文件结构拆分

- [ ] 创建基本目录结构
  ```
  /static
    /css
      - main.css
      - chat.css
      - evaluation.css
    /js
      - app.js
      - chat.js
      - voice.js
      - evaluation.js
      - api.js
    /img
  /templates
    - index.html
  ```

## 2. CSS 拆分

- [ ] 从index.html中提取所有CSS到`/static/css/main.css`
- [ ] 按功能模块拆分CSS:
  - [ ] 基础样式和布局 → `main.css`
  - [ ] 聊天界面相关样式 → `chat.css`
  - [ ] 评估区域相关样式 → `evaluation.css`

## 3. JavaScript 拆分

- [ ] 创建`app.js`作为主入口文件
- [ ] 将聊天功能相关代码提取到`chat.js`
- [ ] 将语音输入功能提取到`voice.js`
- [ ] 将评估显示相关代码提取到`evaluation.js`
- [ ] 创建`api.js`处理所有后端API调用

## 4. 模块化设计

- [ ] 使用ES6模块或简单的模块模式组织代码
- [ ] 定义清晰的模块接口和职责
- [ ] 实现事件驱动的组件通信

## 5. 代码优化

- [ ] 实现统一的错误处理机制
- [ ] 添加加载状态和反馈
- [ ] 优化DOM操作，减少重排和重绘
- [ ] 实现数据和视图的分离

## 6. 功能增强

- [ ] 改进语音输入UI/UX
  - [ ] 添加音量可视化
  - [ ] 改进录音状态指示
- [ ] 添加响应式设计，支持移动设备
- [ ] 实现本地会话存储，支持会话恢复

## 7. 代码质量提升

- [ ] 添加JSDoc注释
- [ ] 实现一致的代码风格
- [ ] 添加输入验证和安全处理

## 8. 构建和部署优化

- [ ] 设置简单的构建流程(可选)
- [ ] 添加资源压缩和优化(可选)
- [ ] 配置缓存策略(可选)

## 9. 具体实现步骤

### 第一阶段：基础结构

1. [ ] 创建目录结构
2. [ ] 提取CSS到独立文件
3. [ ] 创建基本JS模块框架

### 第二阶段：功能迁移

1. [ ] 实现API模块
   ```javascript
   // api.js
   export const API = {
     sendMessage: async (message) => {
       // 实现发送消息到后端
     },
     transcribeAudio: async (audioBlob) => {
       // 实现音频转录
     }
   };
   ```

2. [ ] 实现聊天模块
   ```javascript
   // chat.js
   import { API } from './api.js';
   
   export const ChatModule = {
     init: function(config) {
       // 初始化聊天界面
     },
     sendMessage: function(message) {
       // 发送消息并处理响应
     },
     // 其他方法...
   };
   ```

3. [ ] 实现语音输入模块
   ```javascript
   // voice.js
   import { API } from './api.js';
   
   export const VoiceModule = {
     init: function(config) {
       // 初始化语音输入
     },
     startRecording: function() {
       // 开始录音
     },
     stopRecording: function() {
       // 停止录音并处理
     }
   };
   ```

### 第三阶段：整合和测试

1. [ ] 在app.js中整合所有模块
2. [ ] 测试所有功能
3. [ ] 优化性能和用户体验

## 10. 示例代码结构

```javascript
// app.js
import { ChatModule } from './chat.js';
import { VoiceModule } from './voice.js';
import { EvaluationModule } from './evaluation.js';

document.addEventListener('DOMContentLoaded', function() {
  // 初始化各模块
  ChatModule.init({
    chatWindow: document.getElementById('chat-window'),
    userInput: document.getElementById('user-input'),
    sendButton: document.getElementById('send-btn')
  });
  
  VoiceModule.init({
    voiceButton: document.getElementById('voice-input-button'),
    recordingIndicator: document.getElementById('recording-indicator'),
    userInput: document.getElementById('user-input')
  });
  
  EvaluationModule.init({
    evaluationContent: document.getElementById('realtime-evaluation-content'),
    doctorProfile: document.getElementById('doctor-profile-content')
  });
  
  // 设置全局事件监听和状态管理
});
```

## 11. 预期收益

- **可维护性提升**：模块化设计使代码更易于理解和维护
- **开发效率提高**：独立模块可以由不同开发者并行开发
- **性能优化**：通过优化DOM操作和资源加载提升性能
- **扩展性增强**：模块化架构使添加新功能更加简单
- **代码质量改进**：统一的编码风格和错误处理提高代码质量

## 12. 风险和缓解措施

- **功能回归**：确保重构后所有功能正常工作
  - 缓解：编写详细的测试计划，逐一验证功能
- **浏览器兼容性**：ES6模块在旧浏览器中可能不支持
  - 缓解：考虑使用Babel等工具进行转译，或提供兼容性方案
- **重构时间**：完整重构可能需要较长时间
  - 缓解：采用渐进式重构，先拆分最关键的部分

## 13. 时间估计

- 基础结构搭建：1-2天
- 功能迁移：2-3天
- 整合和测试：1-2天
- 优化和完善：1-2天

总计：5-9个工作日（根据代码复杂度和熟悉程度可能有所变化）
