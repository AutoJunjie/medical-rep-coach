"""
Voice interaction handler for Amazon Nova 2 Sonic speech-to-speech model.
This module manages bidirectional audio streaming between the frontend and AWS Bedrock Runtime.
"""

import os
import json
import boto3
import asyncio
import logging
from typing import AsyncGenerator, Optional, Dict, Any
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class NovaSonicVoiceHandler:
    """
    Handler for Amazon Nova 2 Sonic speech-to-speech interactions.
    Manages bidirectional streaming with AWS Bedrock Runtime.
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
        
        logger.info(f"Initialized NovaSonicVoiceHandler with model: {self.model_id}")
    
    def build_request_body(self, system_prompt: str, conversation_history: list) -> dict:
        """
        Build the request body for Nova Sonic model.
        
        Args:
            system_prompt: System prompt to guide the model's behavior
            conversation_history: List of previous conversation messages
            
        Returns:
            Dictionary containing the request configuration
        """
        request_body = {
            "schemaVersion": "messages-v1",
            "system": [{"text": system_prompt}] if system_prompt else [],
            "messages": conversation_history,
            "inferenceConfig": {
                "temperature": self.temperature,
                "maxTokens": 1500
            },
            "audioConfig": {
                "voice": self.voice,
                "language": self.language
            }
        }
        
        return request_body
    
    async def stream_audio_to_nova(
        self, 
        audio_chunks: AsyncGenerator[bytes, None],
        system_prompt: str,
        conversation_history: list
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Stream audio to Nova Sonic and yield response events.
        
        Args:
            audio_chunks: Async generator yielding audio data chunks
            system_prompt: System prompt for the model
            conversation_history: Previous conversation messages
            
        Yields:
            Dict containing response events (ASR, text, audio)
        """
        try:
            request_body = self.build_request_body(system_prompt, conversation_history)
            
            # Create async generator for input stream
            async def audio_input_stream():
                """Generator that yields audio chunks for the bedrock API."""
                # First, send the initial request configuration
                yield {
                    "modelStreamEvent": {
                        "contentBlockStart": {
                            "start": {
                                "type": "audio"
                            }
                        }
                    }
                }
                
                # Then stream audio chunks
                async for chunk in audio_chunks:
                    if chunk:
                        yield {
                            "modelStreamEvent": {
                                "contentBlockDelta": {
                                    "delta": {
                                        "audio": {
                                            "bytes": chunk
                                        }
                                    }
                                }
                            }
                        }
                
                # Signal end of audio input
                yield {
                    "modelStreamEvent": {
                        "contentBlockStop": {
                            "contentBlockIndex": 0
                        }
                    }
                }
            
            # Note: The actual Bedrock Runtime API for bidirectional streaming
            # might use different method names. This is a conceptual implementation.
            # You may need to adjust based on the actual boto3 API.
            
            # Invoke the model with bidirectional streaming
            response = await asyncio.to_thread(
                self._invoke_model_with_bidirectional_stream,
                request_body,
                audio_input_stream
            )
            
            # Process response events
            async for event in self._process_response_stream(response):
                yield event
                
        except ClientError as e:
            logger.error(f"AWS Bedrock API error: {e}")
            yield {
                "error": f"Bedrock API error: {str(e)}",
                "type": "error"
            }
        except Exception as e:
            logger.error(f"Error in stream_audio_to_nova: {e}")
            yield {
                "error": f"Streaming error: {str(e)}",
                "type": "error"
            }
    
    def _invoke_model_with_bidirectional_stream(self, request_body, audio_input_stream):
        """
        Invoke the Bedrock Runtime API with bidirectional streaming.
        This is a synchronous wrapper for the async streaming.
        
        Note: The actual implementation depends on the boto3 API for Nova Sonic.
        """
        # This is a placeholder for the actual API call
        # The real implementation would use:
        # response = self.bedrock_runtime.invoke_model_with_response_stream(
        #     modelId=self.model_id,
        #     body=json.dumps(request_body),
        #     contentType='application/json',
        #     accept='application/json'
        # )
        
        # For Nova Sonic with bidirectional streaming, the API might be different
        # This is a conceptual implementation
        response = self.bedrock_runtime.invoke_model(
            modelId=self.model_id,
            body=json.dumps(request_body),
            contentType='application/json',
            accept='application/json'
        )
        
        return response
    
    async def _process_response_stream(self, response) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Process the response stream from Nova Sonic.
        
        Args:
            response: Response object from Bedrock API
            
        Yields:
            Processed event dictionaries
        """
        try:
            # Parse the response body
            response_body = json.loads(response['body'].read())
            
            # Extract different types of outputs
            for content in response_body.get('content', []):
                if 'text' in content:
                    # Text response from the model
                    yield {
                        "type": "text",
                        "text": content['text']
                    }
                
                if 'audio' in content:
                    # Audio response (TTS output)
                    audio_data = content['audio'].get('bytes')
                    if audio_data:
                        yield {
                            "type": "audio",
                            "audio": audio_data,
                            "format": content['audio'].get('format', 'pcm')
                        }
            
            # Extract ASR transcription if available
            if 'transcription' in response_body:
                yield {
                    "type": "transcription",
                    "text": response_body['transcription']
                }
            
            # Stop reason
            if 'stopReason' in response_body:
                yield {
                    "type": "stop",
                    "reason": response_body['stopReason']
                }
                
        except Exception as e:
            logger.error(f"Error processing response stream: {e}")
            yield {
                "type": "error",
                "error": str(e)
            }
    
    async def process_text_to_speech(
        self, 
        text: str, 
        system_prompt: Optional[str] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Convert text to speech using Nova Sonic.
        
        Args:
            text: Text to convert to speech
            system_prompt: Optional system prompt
            
        Yields:
            Audio data chunks
        """
        try:
            request_body = {
                "schemaVersion": "messages-v1",
                "system": [{"text": system_prompt}] if system_prompt else [],
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"text": text}
                        ]
                    }
                ],
                "inferenceConfig": {
                    "temperature": self.temperature,
                    "maxTokens": 1500
                },
                "audioConfig": {
                    "voice": self.voice,
                    "language": self.language,
                    "outputFormat": "pcm"
                }
            }
            
            response = await asyncio.to_thread(
                self.bedrock_runtime.invoke_model,
                modelId=self.model_id,
                body=json.dumps(request_body),
                contentType='application/json',
                accept='application/json'
            )
            
            async for event in self._process_response_stream(response):
                yield event
                
        except Exception as e:
            logger.error(f"Error in text-to-speech: {e}")
            yield {
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
        self.doctor_persona = None
        self.mode = "waiting_for_start"
    
    def add_message(self, role: str, content: str, audio_data: Optional[bytes] = None):
        """
        Add a message to the conversation history.
        
        Args:
            role: Role of the speaker (user/assistant)
            content: Text content of the message
            audio_data: Optional audio data for the message
        """
        message = {
            "role": role,
            "content": [{"text": content}]
        }
        
        if audio_data:
            message["content"].append({
                "audio": {"bytes": audio_data}
            })
        
        self.messages.append(message)
    
    def get_conversation_history(self) -> list:
        """Get the conversation history for the model."""
        return self.messages.copy()
    
    def clear(self):
        """Clear the conversation history."""
        self.messages = []
        self.current_session_id = None
        self.doctor_persona = None
        self.mode = "waiting_for_start"
    
    def set_doctor_persona(self, persona: dict):
        """Set the current doctor persona."""
        self.doctor_persona = persona
    
    def get_doctor_persona(self) -> Optional[dict]:
        """Get the current doctor persona."""
        return self.doctor_persona
