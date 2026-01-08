from dotenv import load_dotenv
load_dotenv() # Load environment variables from .env file at the very beginning

# backend_app.py
from flask import Flask, request, jsonify
from flask_cors import CORS # 方便本地开发时处理跨域问题
from flask_sock import Sock
import json
import base64
import uuid
from utils.agent import PharmaRepCoachAgent # 假设您的 agent 在 medical_agent.py
from utils.voice_handler import NovaSonicVoiceHandler, ConversationContext
from utils.tools import scenario_tool, objection_tool, eval_tool
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app) # 允许所有来源的跨域请求,仅用于开发
sock = Sock(app)

# 初始化 PharmaRepCoachAgent
coach_agent = PharmaRepCoachAgent()

# Initialize voice handler
try:
    voice_handler = NovaSonicVoiceHandler()
    
    # Register tools with the voice handler
    voice_handler.register_tool("scenario_tool", scenario_tool)
    voice_handler.register_tool("objection_tool", objection_tool)
    voice_handler.register_tool("eval_tool", eval_tool)
    
    voice_enabled = True
    logger.info("Voice handler initialized successfully with tools")
except Exception as e:
    logger.warning(f"Failed to initialize voice handler: {e}. Voice features will be disabled.")
    voice_handler = None
    voice_enabled = False

# Store active voice sessions
voice_sessions = {}

# Define tool schemas for Nova Sonic
TOOL_DEFINITIONS = [
    {
        "name": "scenario_tool",
        "description": "Generate doctor persona and opening line for a medical training scenario",
        "input_schema": {
            "type": "object",
            "properties": {
                "drug": {
                    "type": "string",
                    "description": "Name of the drug"
                },
                "specialty": {
                    "type": "string",
                    "description": "Medical specialty of the doctor"
                },
                "level": {
                    "type": "string",
                    "enum": ["basic", "intermediate", "advanced"],
                    "description": "Experience level of the doctor"
                },
                "lang": {
                    "type": "string",
                    "enum": ["zh", "en"],
                    "description": "Language for the response"
                }
            },
            "required": ["drug", "specialty"]
        }
    },
    {
        "name": "objection_tool",
        "description": "List common objections and key points for handling them for a specific drug and topic",
        "input_schema": {
            "type": "object",
            "properties": {
                "drug": {
                    "type": "string",
                    "description": "Name of the drug"
                },
                "topic": {
                    "type": "string",
                    "enum": ["efficacy", "safety", "cost", "convenience"],
                    "description": "Topic of concern"
                }
            },
            "required": ["drug", "topic"]
        }
    },
    {
        "name": "eval_tool",
        "description": "Evaluate the medical representative's response for accuracy and compliance",
        "input_schema": {
            "type": "object",
            "properties": {
                "repUtterance": {
                    "type": "string",
                    "description": "The medical representative's response"
                },
                "context": {
                    "type": "string",
                    "description": "The conversation context"
                }
            },
            "required": ["repUtterance", "context"]
        }
    }
]

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
    Handles real-time audio communication with Nova Sonic and tool execution.
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
                    session_id = data.get('session_id', str(uuid.uuid4()))
                    system_prompt = data.get('system_prompt', '你是一个医药代表培训协调员。')
                    doctor_persona = data.get('doctor_persona')
                    
                    if doctor_persona:
                        conversation_context.set_doctor_persona(doctor_persona)
                        system_prompt = coach_agent._get_doctor_system_prompt()
                    
                    conversation_context.current_session_id = session_id
                    conversation_context.current_prompt_name = f"prompt_{uuid.uuid4().hex[:8]}"
                    voice_sessions[session_id] = conversation_context
                    
                    logger.info(f"Started voice session: {session_id}")
                    ws.send(json.dumps({
                        "type": "session_started",
                        "session_id": session_id
                    }))
                
                elif message_type == 'audio_chunk':
                    # Receive and buffer audio chunk from client
                    audio_data = base64.b64decode(data.get('audio', ''))
                    
                    if not session_id or session_id not in voice_sessions:
                        ws.send(json.dumps({
                            "type": "error",
                            "error": "No active session"
                        }))
                        continue
                    
                    # Buffer the audio chunk
                    ctx = voice_sessions[session_id]
                    ctx.add_audio_chunk(audio_data)
                    
                    logger.debug(f"Buffered audio chunk: {len(audio_data)} bytes")
                    
                    # Send acknowledgment
                    ws.send(json.dumps({
                        "type": "audio_received",
                        "size": len(audio_data)
                    }))
                
                elif message_type == 'audio_end':
                    # Client finished sending audio - process with Nova Sonic
                    if not session_id or session_id not in voice_sessions:
                        ws.send(json.dumps({
                            "type": "error",
                            "error": "No active session"
                        }))
                        continue
                    
                    logger.info("Audio input ended, processing with Nova Sonic...")
                    
                    # Get the conversation context
                    ctx = voice_sessions[session_id]
                    audio_chunks = ctx.clear_audio_buffer()
                    
                    if not audio_chunks:
                        ws.send(json.dumps({
                            "type": "error",
                            "error": "No audio data received"
                        }))
                        continue
                    
                    # Get the system prompt based on current state
                    doctor_persona = ctx.get_doctor_persona()
                    if doctor_persona:
                        system_prompt = coach_agent._get_doctor_system_prompt()
                    else:
                        system_prompt = "你是一个医药代表培训协调员。"
                    
                    # Send processing notification
                    ws.send(json.dumps({
                        "type": "processing",
                        "message": "Processing your speech with Nova Sonic..."
                    }))
                    
                    # Invoke Nova Sonic with bidirectional streaming and tool support
                    response_events = voice_handler.invoke_bidirectional_stream(
                        session_id=ctx.current_session_id,
                        prompt_name=ctx.current_prompt_name,
                        system_prompt=system_prompt,
                        audio_chunks=audio_chunks,
                        tools=TOOL_DEFINITIONS
                    )
                    
                    # Process and send response events to client
                    for event in response_events:
                        event_type = event.get("type")
                        
                        if event_type == "transcription":
                            # ASR transcription of user speech
                            transcription_text = event.get("text", "")
                            ctx.add_message("user", transcription_text)
                            
                            ws.send(json.dumps({
                                "type": "transcription",
                                "text": transcription_text,
                                "role": "user"
                            }))
                        
                        elif event_type == "text":
                            # Text response from the model
                            text_response = event.get("text", "")
                            ctx.add_message("assistant", text_response)
                            
                            ws.send(json.dumps({
                                "type": "text_response",
                                "text": text_response,
                                "speaker": "Assistant"
                            }))
                        
                        elif event_type == "audio":
                            # Audio response from the model
                            audio_bytes = event.get("audio")
                            if audio_bytes:
                                ws.send(json.dumps({
                                    "type": "audio_chunk",
                                    "audio": base64.b64encode(audio_bytes).decode('utf-8'),
                                    "format": event.get("format", "pcm")
                                }))
                        
                        elif event_type == "toolUse":
                            # Tool use notification
                            ws.send(json.dumps({
                                "type": "tool_use",
                                "toolName": event.get("name"),
                                "toolUseId": event.get("toolUseId")
                            }))
                        
                        elif event_type == "toolResult":
                            # Tool result notification
                            ws.send(json.dumps({
                                "type": "tool_result",
                                "toolUseId": event.get("toolUseId"),
                                "result": event.get("result")
                            }))
                        
                        elif event_type == "error":
                            # Error during processing
                            ws.send(json.dumps({
                                "type": "error",
                                "error": event.get("error")
                            }))
                        
                        elif event_type == "completionEnd":
                            # Processing complete
                            ws.send(json.dumps({
                                "type": "processing_complete",
                                "stopReason": event.get("stopReason")
                            }))
                    
                    # Update prompt name for next interaction
                    ctx.current_prompt_name = f"prompt_{uuid.uuid4().hex[:8]}"
                
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
                logger.error(f"Error processing message: {e}", exc_info=True)
                ws.send(json.dumps({
                    "type": "error",
                    "error": str(e)
                }))
    
    except Exception as e:
        logger.error(f"WebSocket error: {e}", exc_info=True)
    finally:
        # Clean up session
        if session_id and session_id in voice_sessions:
            del voice_sessions[session_id]
        logger.info("Voice stream connection closed")

if __name__ == '__main__':
    app.run(debug=True, port=5000) # Flask 默认运行在 5000 端口