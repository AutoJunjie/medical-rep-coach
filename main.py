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
    """
    处理音频文件上传并使用 Amazon Transcribe 转换为文本
    """
    try:
        # 检查是否有文件上传
        if 'audio' not in request.files:
            return jsonify({"error": "没有找到音频文件"}), 400
        
        audio_file = request.files['audio']
        
        if audio_file.filename == '':
            return jsonify({"error": "文件名为空"}), 400
        
        # 获取 AWS 配置
        aws_region = os.getenv("AWS_REGION", "us-east-1")
        language_code = os.getenv("TRANSCRIBE_LANGUAGE_CODE", "zh-CN")
        
        # 验证 AWS 凭证是否存在
        if not os.getenv("AWS_ACCESS_KEY_ID") or not os.getenv("AWS_SECRET_ACCESS_KEY"):
            return jsonify({"error": "AWS 凭证未配置。请在 .env 文件中设置 AWS_ACCESS_KEY_ID 和 AWS_SECRET_ACCESS_KEY"}), 500
        
        # 创建临时文件名
        temp_filename = f"temp_audio_{uuid.uuid4()}.webm"
        temp_filepath = os.path.join("/tmp", temp_filename)
        
        # 保存上传的音频文件到临时位置
        audio_file.save(temp_filepath)
        
        try:
            # 初始化 AWS Transcribe 和 S3 客户端
            transcribe_client = boto3.client(
                'transcribe',
                region_name=aws_region,
                aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
                aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY")
            )
            
            s3_client = boto3.client(
                's3',
                region_name=aws_region,
                aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
                aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY")
            )
            
            # 创建或使用现有的 S3 存储桶
            bucket_name = os.getenv("TRANSCRIBE_S3_BUCKET", f"medical-rep-coach-transcribe-{aws_region}")
            s3_key = f"audio/{temp_filename}"
            
            # 创建存储桶（如果不存在）
            try:
                s3_client.head_bucket(Bucket=bucket_name)
            except:
                try:
                    if aws_region == 'us-east-1':
                        s3_client.create_bucket(Bucket=bucket_name)
                    else:
                        s3_client.create_bucket(
                            Bucket=bucket_name,
                            CreateBucketConfiguration={'LocationConstraint': aws_region}
                        )
                    print(f"Created S3 bucket: {bucket_name}")
                except Exception as bucket_error:
                    print(f"Error creating bucket: {str(bucket_error)}")
                    return jsonify({"error": f"无法创建 S3 存储桶: {str(bucket_error)}"}), 500
            
            # 上传音频文件到 S3
            s3_client.upload_file(temp_filepath, bucket_name, s3_key)
            audio_s3_uri = f"s3://{bucket_name}/{s3_key}"
            
            # 创建转录任务
            job_name = f"transcribe_job_{uuid.uuid4()}"
            transcribe_client.start_transcription_job(
                TranscriptionJobName=job_name,
                Media={'MediaFileUri': audio_s3_uri},
                MediaFormat='webm',
                LanguageCode=language_code
            )
            
            # 等待转录完成（最多等待 60 秒）
            max_tries = 60
            while max_tries > 0:
                max_tries -= 1
                job_status = transcribe_client.get_transcription_job(TranscriptionJobName=job_name)
                status = job_status['TranscriptionJob']['TranscriptionJobStatus']
                
                if status in ['COMPLETED', 'FAILED']:
                    break
                
                time.sleep(1)
            
            # 检查转录结果
            if status == 'COMPLETED':
                transcript_uri = job_status['TranscriptionJob']['Transcript']['TranscriptFileUri']
                
                # 获取转录文本
                import urllib.request
                import json as json_module
                
                with urllib.request.urlopen(transcript_uri) as response:
                    transcript_data = json_module.loads(response.read().decode())
                    transcript_text = transcript_data['results']['transcripts'][0]['transcript']
                
                # 清理临时文件和 S3 对象
                try:
                    os.remove(temp_filepath)
                    s3_client.delete_object(Bucket=bucket_name, Key=s3_key)
                    transcribe_client.delete_transcription_job(TranscriptionJobName=job_name)
                except Exception as cleanup_error:
                    print(f"清理资源时出错: {str(cleanup_error)}")
                
                return jsonify({"text": transcript_text}), 200
            
            else:
                # 清理失败的任务
                try:
                    os.remove(temp_filepath)
                    s3_client.delete_object(Bucket=bucket_name, Key=s3_key)
                    transcribe_client.delete_transcription_job(TranscriptionJobName=job_name)
                except:
                    pass
                
                failure_reason = job_status['TranscriptionJob'].get('FailureReason', '未知原因')
                return jsonify({"error": f"转录失败: {failure_reason}"}), 500
        
        except Exception as aws_error:
            # 清理临时文件
            try:
                if os.path.exists(temp_filepath):
                    os.remove(temp_filepath)
            except:
                pass
            
            print(f"AWS Transcribe 错误: {str(aws_error)}")
            return jsonify({"error": f"转录服务错误: {str(aws_error)}"}), 500
    
    except Exception as e:
        print(f"Error in /transcribe endpoint: {str(e)}")
        return jsonify({"error": f"处理音频文件时发生错误: {str(e)}"}), 500


if __name__ == '__main__':
    app.run(debug=True, port=5000) # Flask 默认运行在 5000 端口