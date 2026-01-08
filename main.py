from dotenv import load_dotenv
load_dotenv() # Load environment variables from .env file at the very beginning

# backend_app.py
from flask import Flask, request, jsonify
from flask_cors import CORS # 方便本地开发时处理跨域问题
from flask_sock import Sock
import json
import asyncio
import base64
from utils.agent import PharmaRepCoachAgent # 假设您的 agent 在 medical_agent.py
from utils.voice_handler import NovaSonicVoiceHandler, ConversationContext
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app) # 允许所有来源的跨域请求，仅用于开发
sock = Sock(app)

# 初始化 PharmaRepCoachAgent
coach_agent = PharmaRepCoachAgent()

# Initialize voice handler
try:
    voice_handler = NovaSonicVoiceHandler()
    voice_enabled = True
    logger.info("Voice handler initialized successfully")
except Exception as e:
    logger.warning(f"Failed to initialize voice handler: {e}. Voice features will be disabled.")
    voice_handler = None
    voice_enabled = False

# Store active voice sessions
voice_sessions = {}

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


@app.route('/voice/status', methods=['GET'])
def voice_status():
    """Endpoint to check if voice functionality is available."""
    return jsonify({
        "enabled": voice_enabled,
        "model": voice_handler.model_id if voice_handler else None
    })


@sock.route('/voice/stream')
def voice_stream(ws):
    """
    WebSocket endpoint for bidirectional voice streaming.
    Handles real-time audio communication with Nova Sonic.
    """
    if not voice_enabled:
        ws.send(json.dumps({
            "type": "error",
            "error": "Voice functionality is not available"
        }))
        ws.close()
        return
    
    session_id = None
    conversation_context = ConversationContext()
    
    try:
        logger.info("New voice stream connection established")
        
        # Send connection confirmation
        ws.send(json.dumps({
            "type": "connected",
            "message": "Voice stream connected"
        }))
        
        while True:
            # Receive message from client
            message = ws.receive()
            
            if message is None:
                break
            
            try:
                data = json.loads(message)
                message_type = data.get('type')
                
                if message_type == 'start_session':
                    # Start a new voice session
                    session_id = data.get('session_id')
                    system_prompt = data.get('system_prompt', '')
                    doctor_persona = data.get('doctor_persona')
                    
                    if doctor_persona:
                        conversation_context.set_doctor_persona(doctor_persona)
                    
                    conversation_context.current_session_id = session_id
                    voice_sessions[session_id] = conversation_context
                    
                    logger.info(f"Started voice session: {session_id}")
                    ws.send(json.dumps({
                        "type": "session_started",
                        "session_id": session_id
                    }))
                
                elif message_type == 'audio_chunk':
                    # Receive audio chunk from client
                    audio_data = base64.b64decode(data.get('audio', ''))
                    
                    if not session_id or session_id not in voice_sessions:
                        ws.send(json.dumps({
                            "type": "error",
                            "error": "No active session"
                        }))
                        continue
                    
                    # Process audio chunk (this is simplified)
                    # In a real implementation, you would buffer chunks and process them
                    logger.debug(f"Received audio chunk: {len(audio_data)} bytes")
                    
                    # Send acknowledgment
                    ws.send(json.dumps({
                        "type": "audio_received",
                        "size": len(audio_data)
                    }))
                
                elif message_type == 'audio_end':
                    # Client finished sending audio
                    if not session_id or session_id not in voice_sessions:
                        ws.send(json.dumps({
                            "type": "error",
                            "error": "No active session"
                        }))
                        continue
                    
                    logger.info("Audio input ended, processing...")
                    
                    # Get the system prompt based on current state
                    ctx = voice_sessions[session_id]
                    doctor_persona = ctx.get_doctor_persona()
                    
                    if doctor_persona:
                        system_prompt = coach_agent._get_doctor_system_prompt()
                    else:
                        system_prompt = "你是一个医药代表培训协调员。"
                    
                    # Process the audio with Nova Sonic (simplified for demo)
                    # In real implementation, you would:
                    # 1. Send accumulated audio to Nova Sonic
                    # 2. Get ASR transcription
                    # 3. Get text response
                    # 4. Get TTS audio
                    # 5. Stream back to client
                    
                    # For now, send a mock response
                    ws.send(json.dumps({
                        "type": "processing",
                        "message": "Processing your speech..."
                    }))
                    
                    # Simulate ASR transcription
                    transcription = data.get('transcription', '用户语音输入')
                    ws.send(json.dumps({
                        "type": "transcription",
                        "text": transcription,
                        "role": "user"
                    }))
                    
                    # Get response from agent
                    agent_responses = coach_agent.handle_message(transcription)
                    
                    for response in agent_responses:
                        if response.startswith("Doctor"):
                            parts = response.split('▶', 2)
                            doctor_name = parts[0].replace("Doctor", "").strip()
                            message_text = parts[1].strip() if len(parts) > 1 else ''
                            
                            # Send text response
                            ws.send(json.dumps({
                                "type": "text_response",
                                "text": message_text,
                                "speaker": f"Doctor {doctor_name}"
                            }))
                            
                            # Generate TTS audio for doctor response
                            # This is where you would call Nova Sonic TTS
                            # For now, send a placeholder
                            ws.send(json.dumps({
                                "type": "audio_start",
                                "speaker": f"Doctor {doctor_name}"
                            }))
                            
                            # In real implementation, stream audio chunks here
                            # ws.send(json.dumps({
                            #     "type": "audio_chunk",
                            #     "audio": base64.b64encode(audio_chunk).decode('utf-8')
                            # }))
                            
                            ws.send(json.dumps({
                                "type": "audio_end"
                            }))
                        
                        elif response.startswith("Coach"):
                            coach_message = response.replace("Coach ▶", "").strip()
                            ws.send(json.dumps({
                                "type": "text_response",
                                "text": coach_message,
                                "speaker": "Coach"
                            }))
                        
                        elif response.startswith("System"):
                            system_message = response.replace("System:", "").replace("System ▶", "").strip()
                            ws.send(json.dumps({
                                "type": "system_message",
                                "text": system_message
                            }))
                    
                    ws.send(json.dumps({
                        "type": "processing_complete"
                    }))
                
                elif message_type == 'end_session':
                    # End the voice session
                    if session_id and session_id in voice_sessions:
                        del voice_sessions[session_id]
                    
                    logger.info(f"Ended voice session: {session_id}")
                    ws.send(json.dumps({
                        "type": "session_ended"
                    }))
                    break
                
                else:
                    logger.warning(f"Unknown message type: {message_type}")
                    ws.send(json.dumps({
                        "type": "error",
                        "error": f"Unknown message type: {message_type}"
                    }))
            
            except json.JSONDecodeError as e:
                logger.error(f"JSON decode error: {e}")
                ws.send(json.dumps({
                    "type": "error",
                    "error": "Invalid JSON format"
                }))
            except Exception as e:
                logger.error(f"Error processing message: {e}")
                ws.send(json.dumps({
                    "type": "error",
                    "error": str(e)
                }))
    
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        # Clean up session
        if session_id and session_id in voice_sessions:
            del voice_sessions[session_id]
        logger.info("Voice stream connection closed")

if __name__ == '__main__':
    app.run(debug=True, port=5000) # Flask 默认运行在 5000 端口