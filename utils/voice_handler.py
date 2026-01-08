"""
Voice interaction handler for Amazon Nova 2 Sonic speech-to-speech model.
This module manages bidirectional audio streaming with AWS Bedrock Runtime
and implements proper tool configuration and handling.
"""

import os
import json
import boto3
import logging
from typing import Optional, Dict, Any, List, Callable
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class NovaSonicVoiceHandler:
    """
    Handler for Amazon Nova 2 Sonic speech-to-speech interactions.
    Manages bidirectional streaming with AWS Bedrock Runtime and tool configuration.
    """
    
    def __init__(self):
        """Initialize the Nova Sonic voice handler with AWS credentials and configuration."""
        self.aws_region = os.getenv("AWS_REGION", "us-east-1")
        self.model_id = os.getenv("NOVA_SONIC_MODEL_ID", "amazon.nova-sonic-v2:0")
        self.voice = os.getenv("NOVA_SONIC_VOICE", "en-US-Neutral")
        self.language = os.getenv("NOVA_SONIC_LANGUAGE", "en-US")
        self.temperature = float(os.getenv("NOVA_SONIC_TEMPERATURE", "0.7"))
        
        # Initialize Bedrock Runtime client
        self.bedrock_runtime = boto3.client(
            service_name='bedrock-runtime',
            region_name=self.aws_region,
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY")
        )
        
        # Tool registry for executing tools
        self.tool_registry: Dict[str, Callable] = {}
        
        logger.info(f"Initialized NovaSonicVoiceHandler with model: {self.model_id}")
    
    def register_tool(self, name: str, handler: Callable):
        """
        Register a tool handler function.
        
        Args:
            name: Name of the tool
            handler: Callable that executes the tool
        """
        self.tool_registry[name] = handler
        logger.info(f"Registered tool: {name}")
    
    def build_tool_config(self, tools: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Build tool configuration in Nova 2 Sonic format.
        
        Args:
            tools: List of tool definitions with name, description, and input_schema
            
        Returns:
            Tool configuration dictionary for promptStart event
        """
        if not tools:
            return {}
        
        tool_specs = []
        for tool in tools:
            tool_spec = {
                "toolSpec": {
                    "name": tool["name"],
                    "description": tool["description"],
                    "inputSchema": {
                        "json": tool["input_schema"]
                    }
                }
            }
            tool_specs.append(tool_spec)
        
        return {
            "tools": tool_specs,
            "toolChoice": {"auto": {}}  # Let the model decide when to use tools
        }
    
    def create_session_start_event(self, session_id: str) -> Dict[str, Any]:
        """
        Create a sessionStart event for Nova Sonic bidirectional streaming.
        
        Args:
            session_id: Unique session identifier
            
        Returns:
            sessionStart event dictionary
        """
        return {
            "sessionStart": {
                "sessionId": session_id,
                "inferenceConfig": {
                    "temperature": self.temperature,
                    "maxTokens": 1500
                }
            }
        }
    
    def create_prompt_start_event(
        self,
        prompt_name: str,
        session_id: str,
        system_prompt: str,
        tool_config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create a promptStart event with optional tool configuration.
        
        Args:
            prompt_name: Unique prompt identifier
            session_id: Session identifier
            system_prompt: System prompt text
            tool_config: Optional tool configuration
            
        Returns:
            promptStart event dictionary
        """
        event = {
            "promptStart": {
                "promptName": prompt_name,
                "sessionId": session_id,
                "system": [{"text": system_prompt}],
                "audioConfig": {
                    "voice": self.voice,
                    "language": self.language
                }
            }
        }
        
        # Add tool configuration if provided
        if tool_config and "tools" in tool_config:
            event["promptStart"]["toolConfig"] = tool_config
        
        return event
    
    def create_audio_chunk_event(
        self,
        audio_bytes: bytes,
        prompt_name: str,
        session_id: str
    ) -> Dict[str, Any]:
        """
        Create an audio chunk event for streaming user audio.
        
        Args:
            audio_bytes: Raw audio data
            prompt_name: Prompt identifier
            session_id: Session identifier
            
        Returns:
            Audio chunk event dictionary
        """
        return {
            "audioChunk": {
                "promptName": prompt_name,
                "sessionId": session_id,
                "audio": audio_bytes
            }
        }
    
    def create_audio_end_event(
        self,
        prompt_name: str,
        session_id: str
    ) -> Dict[str, Any]:
        """
        Create an audioEnd event to signal completion of audio input.
        
        Args:
            prompt_name: Prompt identifier
            session_id: Session identifier
            
        Returns:
            audioEnd event dictionary
        """
        return {
            "audioEnd": {
                "promptName": prompt_name,
                "sessionId": session_id
            }
        }
    
    def create_tool_result_event(
        self,
        tool_use_id: str,
        content: List[Dict[str, Any]],
        prompt_name: str,
        session_id: str
    ) -> Dict[str, Any]:
        """
        Create a toolResult event to send tool execution results back to the model.
        
        Args:
            tool_use_id: ID from the toolUse event
            content: Tool result content (list of dicts with "text" or "json" keys)
            prompt_name: Prompt identifier
            session_id: Session identifier
            
        Returns:
            toolResult event dictionary
        """
        return {
            "toolResult": {
                "promptName": prompt_name,
                "sessionId": session_id,
                "toolUseId": tool_use_id,
                "content": content
            }
        }
    
    def execute_tool(self, tool_use: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a tool based on toolUse event from the model.
        
        Args:
            tool_use: Tool use event containing name, toolUseId, and input
            
        Returns:
            Tool execution result
        """
        tool_name = tool_use.get("name")
        tool_input = tool_use.get("input", {})
        
        if tool_name not in self.tool_registry:
            logger.warning(f"Tool '{tool_name}' not found in registry")
            return {
                "status": "error",
                "content": [{"text": f"Tool '{tool_name}' is not available"}]
            }
        
        try:
            # Execute the tool handler
            handler = self.tool_registry[tool_name]
            result = handler(**tool_input)
            
            logger.info(f"Executed tool '{tool_name}' successfully")
            return result
            
        except Exception as e:
            logger.error(f"Error executing tool '{tool_name}': {e}")
            return {
                "status": "error",
                "content": [{"text": f"Error executing tool: {str(e)}"}]
            }
    
    def invoke_bidirectional_stream(
        self,
        session_id: str,
        prompt_name: str,
        system_prompt: str,
        audio_chunks: List[bytes],
        tools: Optional[List[Dict[str, Any]]] = None
    ) -> List[Dict[str, Any]]:
        """
        Invoke Nova Sonic with bidirectional streaming and tool support.
        
        Args:
            session_id: Unique session identifier
            prompt_name: Unique prompt identifier
            system_prompt: System prompt for the conversation
            audio_chunks: List of audio data chunks from user
            tools: Optional list of tool definitions
            
        Returns:
            List of response events (ASR, text, audio, toolUse, etc.)
        """
        try:
            # Build tool configuration if tools are provided
            tool_config = self.build_tool_config(tools) if tools else None
            
            # Prepare input events
            input_events = []
            
            # 1. Session start event
            input_events.append(self.create_session_start_event(session_id))
            
            # 2. Prompt start event with tool config
            input_events.append(
                self.create_prompt_start_event(
                    prompt_name, 
                    session_id, 
                    system_prompt,
                    tool_config
                )
            )
            
            # 3. Audio chunk events
            for chunk in audio_chunks:
                if chunk:
                    input_events.append(
                        self.create_audio_chunk_event(chunk, prompt_name, session_id)
                    )
            
            # 4. Audio end event
            input_events.append(
                self.create_audio_end_event(prompt_name, session_id)
            )
            
            # Invoke the bidirectional stream API
            logger.info(f"Invoking bidirectional stream for session {session_id}")
            
            response = self.bedrock_runtime.invoke_model_with_bidirectional_stream(
                modelId=self.model_id,
                inputStream=self._event_stream_generator(input_events)
            )
            
            # Process response events
            response_events = []
            output_stream = response.get('outputStream', [])
            
            for event in output_stream:
                processed_event = self._process_output_event(event, session_id, prompt_name)
                if processed_event:
                    response_events.append(processed_event)
                    
                    # If the event is a toolUse, execute the tool and send result back
                    if processed_event.get("type") == "toolUse":
                        tool_result = self.execute_tool(processed_event)
                        
                        # Send tool result back to the model
                        tool_result_event = self.create_tool_result_event(
                            processed_event["toolUseId"],
                            tool_result.get("content", [{"text": "Tool executed"}]),
                            prompt_name,
                            session_id
                        )
                        
                        # Continue the conversation with tool result
                        # Note: In a real implementation, you would send this back through the stream
                        response_events.append({
                            "type": "toolResult",
                            "toolUseId": processed_event["toolUseId"],
                            "result": tool_result
                        })
            
            return response_events
            
        except ClientError as e:
            logger.error(f"AWS Bedrock API error: {e}")
            return [{
                "type": "error",
                "error": f"Bedrock API error: {str(e)}"
            }]
        except Exception as e:
            logger.error(f"Error in bidirectional streaming: {e}")
            return [{
                "type": "error",
                "error": f"Streaming error: {str(e)}"
            }]
    
    def _event_stream_generator(self, events: List[Dict[str, Any]]):
        """
        Generator that yields events for the input stream.
        
        Args:
            events: List of event dictionaries
            
        Yields:
            Event dictionaries for the stream
        """
        for event in events:
            yield event
    
    def _process_output_event(
        self,
        event: Dict[str, Any],
        session_id: str,
        prompt_name: str
    ) -> Optional[Dict[str, Any]]:
        """
        Process an output event from Nova Sonic.
        
        Args:
            event: Raw event from the output stream
            session_id: Session identifier
            prompt_name: Prompt identifier
            
        Returns:
            Processed event dictionary or None
        """
        try:
            # completionStart event
            if "completionStart" in event:
                return {
                    "type": "completionStart",
                    "sessionId": event["completionStart"].get("sessionId"),
                    "promptName": event["completionStart"].get("promptName"),
                    "completionId": event["completionStart"].get("completionId")
                }
            
            # contentStart event
            if "contentStart" in event:
                content_start = event["contentStart"]
                return {
                    "type": "contentStart",
                    "contentType": content_start.get("contentType"),
                    "role": content_start.get("role")
                }
            
            # ASR transcription (text content from user)
            if "text" in event and event.get("role") == "USER":
                return {
                    "type": "transcription",
                    "text": event["text"]
                }
            
            # Text response from assistant
            if "text" in event and event.get("role") == "ASSISTANT":
                return {
                    "type": "text",
                    "text": event["text"]
                }
            
            # Audio response
            if "audio" in event:
                return {
                    "type": "audio",
                    "audio": event["audio"].get("bytes"),
                    "format": event["audio"].get("format", "pcm")
                }
            
            # Tool use event
            if "toolUse" in event:
                tool_use = event["toolUse"]
                return {
                    "type": "toolUse",
                    "toolUseId": tool_use.get("toolUseId"),
                    "name": tool_use.get("name"),
                    "input": tool_use.get("input", {})
                }
            
            # contentEnd event
            if "contentEnd" in event:
                return {
                    "type": "contentEnd"
                }
            
            # completionEnd event
            if "completionEnd" in event:
                return {
                    "type": "completionEnd",
                    "stopReason": event["completionEnd"].get("stopReason")
                }
            
            # Other events
            return None
            
        except Exception as e:
            logger.error(f"Error processing output event: {e}")
            return {
                "type": "error",
                "error": str(e)
            }


class ConversationContext:
    """
    Maintains conversation context for voice interactions.
    """
    
    def __init__(self):
        """Initialize conversation context."""
        self.messages = []
        self.current_session_id = None
        self.current_prompt_name = None
        self.doctor_persona = None
        self.mode = "waiting_for_start"
        self.audio_buffer = []
    
    def add_message(self, role: str, content: str):
        """
        Add a message to the conversation history.
        
        Args:
            role: Role of the speaker (user/assistant)
            content: Text content of the message
        """
        message = {
            "role": role,
            "content": content
        }
        self.messages.append(message)
    
    def add_audio_chunk(self, audio_bytes: bytes):
        """
        Buffer audio chunks for processing.
        
        Args:
            audio_bytes: Raw audio data
        """
        self.audio_buffer.append(audio_bytes)
    
    def clear_audio_buffer(self) -> List[bytes]:
        """
        Clear and return the audio buffer.
        
        Returns:
            List of buffered audio chunks
        """
        chunks = self.audio_buffer.copy()
        self.audio_buffer = []
        return chunks
    
    def get_conversation_history(self) -> List[Dict[str, str]]:
        """Get the conversation history."""
        return self.messages.copy()
    
    def clear(self):
        """Clear the conversation context."""
        self.messages = []
        self.current_session_id = None
        self.current_prompt_name = None
        self.doctor_persona = None
        self.mode = "waiting_for_start"
        self.audio_buffer = []
    
    def set_doctor_persona(self, persona: dict):
        """Set the current doctor persona."""
        self.doctor_persona = persona
    
    def get_doctor_persona(self) -> Optional[dict]:
        """Get the current doctor persona."""
        return self.doctor_persona
