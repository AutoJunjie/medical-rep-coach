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
import asyncio
import websockets
import json
import base64
import threading
from amazon_transcribe.client import TranscribeStreamingClient
from amazon_transcribe.handlers import TranscriptResultStreamHandler
from amazon_transcribe.model import TranscriptEvent

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

# 配置Polly客户端(用于文字转语音)
def get_polly_client():
    return boto3.client(
        'polly',
        region_name=os.getenv('AWS_REGION', 'us-east-1'),
        aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
        aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY')
    )

# WebSocket处理函数
async def transcribe_stream(websocket):
    """处理WebSocket连接的异步函数"""
    print(f"New WebSocket connection: {websocket.remote_address}")
    
    # 创建流式转录客户端
    client = None
    stream = None
    transcript_task = None
    
    try:
        # 处理来自客户端的消息
        async for message in websocket:
            data = json.loads(message)
            
            if data['type'] == 'start':
                # 开始新的转录会话
                print("Starting new transcription session")
                
                # 创建Transcribe流式客户端
                client = TranscribeStreamingClient(region=os.getenv('AWS_REGION', 'us-east-1'))
                
                # 配置流式转录
                stream = await client.start_stream_transcription(
                    language_code="zh-CN",
                    media_encoding="pcm",
                    media_sample_rate_hz=16000
                )
                
                # 启动转录结果处理任务
                transcript_task = asyncio.create_task(
                    handle_transcript_results(stream.output_stream, websocket)
                )
                
                # 通知客户端转录已开始
                await websocket.send(json.dumps({
                    "type": "info",
                    "message": "转录会话已开始"
                }))
            
            elif data['type'] == 'audio':
                # 确保流已经初始化
                if not stream:
                    await websocket.send(json.dumps({
                        "type": "error",
                        "message": "转录会话尚未开始"
                    }))
                    continue
                
                # 解码base64音频数据
                audio_data = base64.b64decode(data['data'])
                
                # 发送音频数据到流
                await stream.input_stream.send_audio_event(audio_data)
            
            elif data['type'] == 'end':
                # 结束转录流
                if stream:
                    await stream.input_stream.end_stream()
                
                # 等待转录任务完成
                if transcript_task:
                    try:
                        await asyncio.wait_for(transcript_task, timeout=5.0)
                    except asyncio.TimeoutError:
                        transcript_task.cancel()
                
                # 重置状态，准备下一次转录
                client = None
                stream = None
                transcript_task = None
                
                await websocket.send(json.dumps({
                    "type": "info",
                    "message": "转录会话已结束"
                }))
    
    except Exception as e:
        print(f"WebSocket error: {str(e)}")
        try:
            await websocket.send(json.dumps({
                "type": "error",
                "message": str(e)
            }))
        except:
            pass
    finally:
        # 确保流被关闭
        if stream:
            try:
                await stream.input_stream.end_stream()
            except:
                pass
        
        # 取消转录任务
        if transcript_task and not transcript_task.done():
            transcript_task.cancel()
        
        print(f"WebSocket connection closed: {websocket.remote_address}")

async def handle_transcript_results(output_stream, websocket):
    """处理转录结果流"""
    full_transcript = ""
    
    try:
        async for event in output_stream:
            if hasattr(event, 'transcript') and event.transcript:
                results = event.transcript.results
                
                for result in results:
                    if result.alternatives:
                        transcript = result.alternatives[0].transcript
                        
                        if result.is_partial:
                            # 发送部分结果
                            await websocket.send(json.dumps({
                                "type": "partial",
                                "transcript": transcript
                            }))
                        else:
                            # 发送最终结果
                            full_transcript += transcript + " "
                            await websocket.send(json.dumps({
                                "type": "final",
                                "transcript": transcript
                            }))
    
    except Exception as e:
        print(f"Error handling transcript results: {e}")
        try:
            await websocket.send(json.dumps({
                "type": "error",
                "message": f"转录处理错误: {str(e)}"
            }))
        except:
            pass
    
    finally:
        # 发送完整转录结果
        if full_transcript.strip():
            try:
                await websocket.send(json.dumps({
                    "type": "complete",
                    "transcript": full_transcript.strip()
                }))
            except:
                pass

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

@app.route('/text-to-speech', methods=['POST'])
def text_to_speech():
    """将文本转换为语音"""
    try:
        data = request.get_json()
        text = data.get('text')
        voice_id = data.get('voice_id', 'Zhiyu')  # 默认使用中文女声
        
        if not text:
            return jsonify({"error": "Missing text in request"}), 400
        
        # 限制文本长度（Polly有字符限制）
        if len(text) > 3000:
            text = text[:3000] + "..."
        
        # 获取Polly客户端
        polly_client = get_polly_client()
        
        # 调用Polly进行语音合成
        response = polly_client.synthesize_speech(
            Text=text,
            OutputFormat='mp3',
            VoiceId=voice_id,
            Engine='neural',  # 使用神经网络引擎获得更自然的语音
            LanguageCode='cmn-CN'  # 中文普通话
        )
        
        # 获取音频流
        audio_stream = response['AudioStream']
        audio_data = audio_stream.read()
        
        # 将音频数据编码为base64
        audio_base64 = base64.b64encode(audio_data).decode('utf-8')
        
        return jsonify({
            "audio_data": audio_base64,
            "content_type": "audio/mpeg"
        })
        
    except Exception as e:
        print(f"Error in /text-to-speech endpoint: {str(e)}")
        return jsonify({"error": str(e)}), 500

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

@app.route('/reset', methods=['POST'])
def reset_session():
    """重置会话状态"""
    try:
        global coach_agent
        # 重新初始化coach_agent来清除会话状态
        coach_agent = PharmaRepCoachAgent()
        return jsonify({"status": "success", "message": "会话状态已重置"}), 200
    except Exception as e:
        print(f"重置会话状态时出错: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/websocket-port', methods=['GET'])
def get_websocket_port():
    """返回WebSocket服务器的端口"""
    return jsonify({"port": 18765})

if __name__ == '__main__':
    # 启动WebSocket服务器
    async def start_websocket_server():
        # 使用固定端口
        port = 18765
        
        print(f"尝试在端口 {port} 上启动WebSocket服务器")
        
        try:
            async with websockets.serve(
                transcribe_stream,
                "localhost", 
                port
            ):
                print(f"WebSocket server started on ws://localhost:{port}")
                await asyncio.Future()  # 运行直到被取消
        except OSError as e:
            print(f"启动WebSocket服务器失败: {e}")
    
    # 在单独的线程中启动WebSocket服务器
    def run_websocket_server():
        try:
            asyncio.run(start_websocket_server())
        except Exception as e:
            print(f"WebSocket服务器线程错误: {e}")
    
    websocket_thread = threading.Thread(target=run_websocket_server)
    websocket_thread.daemon = True
    websocket_thread.start()
    
    # 启动Flask应用
    app.run(debug=True, port=18080, use_reloader=False)  # 禁用重新加载器，避免启动多个WebSocket服务器