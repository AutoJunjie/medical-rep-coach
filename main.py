from dotenv import load_dotenv
load_dotenv() # Load environment variables from .env file at the very beginning

# backend_app.py
import os
import uuid
import boto3
from flask import Flask, request, jsonify
from flask_cors import CORS # 方便本地开发时处理跨域问题
from utils.agent import PharmaRepCoachAgent # 假设您的 agent 在 medical_agent.py
from werkzeug.utils import secure_filename

# 确保有上传文件的目录
UPLOAD_FOLDER = 'temp_audio'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

app = Flask(__name__)
CORS(app) # 允许所有来源的跨域请求，仅用于开发
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# 初始化 PharmaRepCoachAgent
coach_agent = PharmaRepCoachAgent()

# 配置AWS客户端
def get_transcribe_client():
    return boto3.client(
        'transcribe',
        region_name=os.getenv('AWS_REGION', 'us-east-1'),
        aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
        aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY')
    )

# 配置S3客户端(用于存储音频文件)
def get_s3_client():
    return boto3.client(
        's3',
        region_name=os.getenv('AWS_REGION', 'us-east-1'),
        aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
        aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY')
    )

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

@app.route('/transcribe', methods=['POST'])
def transcribe_audio():
    if 'audio' not in request.files:
        return jsonify({"error": "No audio file provided"}), 400
    
    audio_file = request.files['audio']
    
    try:
        # 生成唯一文件名
        filename = f"{uuid.uuid4()}.wav"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(filename))
        
        # 保存上传的文件
        audio_file.save(filepath)
        
        # 获取S3配置
        s3_bucket = os.getenv('S3_BUCKET')
        
        if not s3_bucket:
            return jsonify({"error": "S3_BUCKET environment variable not set"}), 500
        
        # 上传到S3
        s3_key = f"audio/{filename}"
        
        s3_client = get_s3_client()
        s3_client.upload_file(filepath, s3_bucket, s3_key)
        
        # 创建转录任务
        transcribe_client = get_transcribe_client()
        job_name = f"transcription-{uuid.uuid4().hex[:8]}"
        job_uri = f"s3://{s3_bucket}/{s3_key}"
        
        transcribe_client.start_transcription_job(
            TranscriptionJobName=job_name,
            Media={'MediaFileUri': job_uri},
            MediaFormat='wav',
            LanguageCode='zh-CN'  # 中文
        )
        
        # 等待任务完成
        import time
        max_wait_time = 30  # 最多等待30秒
        start_time = time.time()
        
        while True:
            status = transcribe_client.get_transcription_job(TranscriptionJobName=job_name)
            if status['TranscriptionJob']['TranscriptionJobStatus'] in ['COMPLETED', 'FAILED']:
                break
                
            # 检查是否超时
            if time.time() - start_time > max_wait_time:
                raise Exception("转录任务超时")
                
            time.sleep(1)
        
        if status['TranscriptionJob']['TranscriptionJobStatus'] == 'COMPLETED':
            # 获取转录结果
            transcript_uri = status['TranscriptionJob']['Transcript']['TranscriptFileUri']
            import requests
            transcript_response = requests.get(transcript_uri)
            transcript_data = transcript_response.json()
            
            # 提取文本
            transcript_text = transcript_data['results']['transcripts'][0]['transcript']
            
            # 清理临时文件
            os.remove(filepath)
            
            # 删除S3文件
            s3_client.delete_object(Bucket=s3_bucket, Key=s3_key)
            
            return jsonify({"text": transcript_text})
        else:
            error_reason = status['TranscriptionJob'].get('FailureReason', '未知错误')
            return jsonify({"error": f"转录失败: {error_reason}"}), 500
        
    except Exception as e:
        # 确保清理临时文件
        if 'filepath' in locals() and os.path.exists(filepath):
            os.remove(filepath)
        
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=8080) # Flask 默认运行在 8080 端口