from dotenv import load_dotenv
load_dotenv() # Load environment variables from .env file at the very beginning

# backend_app.py
from flask import Flask, request, jsonify
from flask_cors import CORS # 方便本地开发时处理跨域问题
from utils.agent import PharmaRepCoachAgent # 假设您的 agent 在 medical_agent.py

app = Flask(__name__)
CORS(app) # 允许所有来源的跨域请求，仅用于开发

# 初始化 PharmaRepCoachAgent
coach_agent = PharmaRepCoachAgent()

@app.route('/chat', methods=['POST'])
def chat():
    try:
        data = request.get_json()
        user_message = data.get('message')

        if not user_message:
            return jsonify({"error": "Missing message in request"}), 400

        agent_responses = coach_agent.handle_message(user_message)
        
        # 确保即使出现内部错误，也返回一个包含错误信息的列表
        if not isinstance(agent_responses, list):
             # 如果 agent_responses 不是列表（例如，agent 内部出错返回了单个字符串或 None）
             # 将其包装或提供一个标准错误格式
             print(f"Warning: agent_responses was not a list: {agent_responses}")
             agent_responses = [f"System: 处理时发生内部错误。收到的响应: {str(agent_responses)}"]


        return jsonify({"responses": agent_responses})

    except Exception as e:
        print(f"Error in /chat endpoint: {str(e)}") # Log the error server-side
        # 返回一个包含错误信息的列表，以便前端可以显示
        return jsonify({"responses": [f"System: 服务器处理请求时发生错误: {str(e)}"]}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000) # Flask 默认运行在 5000 端口