from dotenv import load_dotenv
load_dotenv() # Load environment variables from .env file at the very beginning

# backend_app.py
from flask import Flask, request, jsonify
from flask_cors import CORS # 方便本地开发时处理跨域问题
from utils.agent import PharmaRepCoachAgent # 假设您的 agent 在 medical_agent.py
import boto3
import os
import time
import uuid

app = Flask(__name__)
CORS(app) # 允许所有来源的跨域请求，仅用于开发

# 初始化 PharmaRepCoachAgent
coach_agent = PharmaRepCoachAgent()

# 初始化 AWS Transcribe 客户端
def get_transcribe_client():
    """创建并返回 Amazon Transcribe 客户端"""
    return boto3.client(
        'transcribe',
        aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
        aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
        region_name=os.getenv('AWS_REGION', 'us-east-1')
    )

# 初始化 S3 客户端 (用于上传音频文件到 S3)
def get_s3_client():
    """创建并返回 S3 客户端"""
    return boto3.client(
        's3',
        aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
        aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
        region_name=os.getenv('AWS_REGION', 'us-east-1')
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
def transcribe():
    """处理音频文件并使用 Amazon Transcribe 进行转录"""
    try:
        # 检查是否有文件上传
        if 'audio' not in request.files:
            return jsonify({"error": "没有音频文件上传"}), 400
        
        audio_file = request.files['audio']
        
        if audio_file.filename == '':
            return jsonify({"error": "文件名为空"}), 400
        
        # 生成唯一的文件名
        file_extension = audio_file.filename.rsplit('.', 1)[-1] if '.' in audio_file.filename else 'webm'
        unique_filename = f"audio_{uuid.uuid4().hex}.{file_extension}"
        temp_audio_path = os.path.join('/tmp', unique_filename)
        
        # 保存上传的音频文件到临时目录
        audio_file.save(temp_audio_path)
        
        # 获取 S3 存储桶名称 (需要在环境变量中配置)
        s3_bucket = os.getenv('AWS_S3_BUCKET')
        if not s3_bucket:
            # 如果没有配置 S3 存储桶，使用本地文件 URI (仅用于测试)
            os.remove(temp_audio_path)
            return jsonify({"error": "AWS_S3_BUCKET 环境变量未配置。请配置 S3 存储桶以使用转录服务。"}), 500
        
        # 上传文件到 S3
        s3_client = get_s3_client()
        s3_key = f"transcribe-input/{unique_filename}"
        
        try:
            s3_client.upload_file(temp_audio_path, s3_bucket, s3_key)
        except Exception as s3_error:
            os.remove(temp_audio_path)
            return jsonify({"error": f"上传文件到 S3 失败: {str(s3_error)}"}), 500
        
        # 删除本地临时文件
        os.remove(temp_audio_path)
        
        # 创建转录作业
        transcribe_client = get_transcribe_client()
        job_name = f"transcribe_job_{uuid.uuid4().hex}"
        job_uri = f"s3://{s3_bucket}/{s3_key}"
        
        # 启动转录作业
        try:
            transcribe_client.start_transcription_job(
                TranscriptionJobName=job_name,
                Media={'MediaFileUri': job_uri},
                MediaFormat=file_extension if file_extension in ['mp3', 'mp4', 'wav', 'flac', 'ogg', 'amr', 'webm'] else 'webm',
                LanguageCode='zh-CN',  # 中文转录
                Settings={
                    'ShowSpeakerLabels': False,
                }
            )
        except Exception as transcribe_error:
            # 清理 S3 文件
            try:
                s3_client.delete_object(Bucket=s3_bucket, Key=s3_key)
            except:
                pass
            return jsonify({"error": f"启动转录作业失败: {str(transcribe_error)}"}), 500
        
        # 等待转录作业完成
        max_attempts = 60  # 最多等待 60 次（约 60 秒）
        attempt = 0
        
        while attempt < max_attempts:
            try:
                status = transcribe_client.get_transcription_job(TranscriptionJobName=job_name)
                job_status = status['TranscriptionJob']['TranscriptionJobStatus']
                
                if job_status == 'COMPLETED':
                    # 获取转录结果
                    transcript_file_uri = status['TranscriptionJob']['Transcript']['TranscriptFileUri']
                    
                    # 下载并解析转录结果
                    import requests
                    response = requests.get(transcript_file_uri)
                    transcript_data = response.json()
                    
                    # 提取转录文本
                    transcribed_text = transcript_data['results']['transcripts'][0]['transcript']
                    
                    # 清理 S3 文件
                    try:
                        s3_client.delete_object(Bucket=s3_bucket, Key=s3_key)
                    except:
                        pass
                    
                    return jsonify({"text": transcribed_text})
                
                elif job_status == 'FAILED':
                    failure_reason = status['TranscriptionJob'].get('FailureReason', '未知原因')
                    # 清理 S3 文件
                    try:
                        s3_client.delete_object(Bucket=s3_bucket, Key=s3_key)
                    except:
                        pass
                    return jsonify({"error": f"转录作业失败: {failure_reason}"}), 500
                
                # 如果还在处理中，等待 1 秒后重试
                time.sleep(1)
                attempt += 1
                
            except Exception as status_error:
                # 清理 S3 文件
                try:
                    s3_client.delete_object(Bucket=s3_bucket, Key=s3_key)
                except:
                    pass
                return jsonify({"error": f"检查转录状态失败: {str(status_error)}"}), 500
        
        # 超时
        # 清理 S3 文件
        try:
            s3_client.delete_object(Bucket=s3_bucket, Key=s3_key)
        except:
            pass
        return jsonify({"error": "转录作业超时"}), 500
        
    except Exception as e:
        print(f"Error in /transcribe endpoint: {str(e)}")
        return jsonify({"error": f"转录服务错误: {str(e)}"}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000) # Flask 默认运行在 5000 端口