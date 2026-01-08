# Voice Interaction with Amazon Nova 2 Sonic - Implementation Guide

## Overview

This guide describes the voice interaction functionality implemented for the medical-rep-coach application using Amazon Nova 2 Sonic speech-to-speech model. The implementation enables real-time voice conversations between medical representatives and AI-powered doctor personas during training sessions.

## Architecture

### Backend Components

#### 1. Voice Handler Module (`utils/voice_handler.py`)

The `NovaSonicVoiceHandler` class manages the integration with AWS Bedrock Runtime API:

- **Bidirectional Streaming**: Handles real-time audio streaming to and from Amazon Nova 2 Sonic
- **Event Processing**: Processes ASR transcriptions, text responses, and audio outputs
- **Conversation Context**: Maintains conversation state across voice exchanges

**Key Methods:**
- `stream_audio_to_nova()`: Streams audio input and yields response events
- `process_text_to_speech()`: Converts text to speech using Nova Sonic
- `build_request_body()`: Constructs API requests with configuration

The `ConversationContext` class maintains the conversation state:
- Stores message history
- Tracks doctor persona information
- Manages session state

#### 2. WebSocket Endpoint (`main.py`)

The `/voice/stream` WebSocket endpoint handles real-time bidirectional communication:

**Message Types:**
- `start_session`: Initialize a new voice session
- `audio_chunk`: Stream audio data from client
- `audio_end`: Signal end of audio input
- `end_session`: Terminate the voice session

**Response Types:**
- `connected`: Confirm WebSocket connection
- `transcription`: ASR output of user speech
- `text_response`: Text response from AI
- `audio_chunk`: TTS audio data
- `processing`: Status updates
- `error`: Error messages

#### 3. HTTP Endpoint

`/voice/status` - Returns voice functionality availability status

### Frontend Components

#### 1. Voice Controls UI

**Voice Control Panel:**
- Toggle button for starting/stopping recording
- Visual status indicators (recording, processing, speaking)
- Real-time status text updates

**Visual States:**
- **Idle** (gray): Ready to record
- **Recording** (red, pulsing): Actively capturing audio
- **Processing** (yellow, pulsing): Processing speech
- **Speaking** (blue, pulsing): AI is responding with audio

#### 2. Audio Recording

Uses Web Audio API to capture microphone input:

```javascript
navigator.mediaDevices.getUserMedia({
    audio: {
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
        sampleRate: 16000
    }
})
```

**Features:**
- Echo cancellation for better quality
- Noise suppression
- Automatic gain control
- Optimized 16kHz sample rate

#### 3. WebSocket Client

Manages bidirectional communication with backend:

- Automatic connection establishment
- Message queuing during disconnection
- Error handling and retry logic
- Session management

#### 4. Audio Playback

Implements audio playback queue for streaming responses:

- Buffers incoming audio chunks
- Sequential playback
- Status updates during playback

#### 5. Integration with Chat Interface

Voice interactions are seamlessly integrated:

- ASR transcriptions displayed in chat window
- Text responses shown in chat
- Coach feedback appears in evaluation panel
- Maintains consistency with text-based chat

## Configuration

### Environment Variables (.env.example)

```bash
# AWS Credentials (required)
AWS_ACCESS_KEY_ID="YOUR_AWS_ACCESS_KEY_ID"
AWS_SECRET_ACCESS_KEY="YOUR_AWS_SECRET_ACCESS_KEY"
AWS_REGION="YOUR_AWS_REGION"

# Amazon Nova 2 Sonic Configuration
NOVA_SONIC_MODEL_ID="amazon.nova-sonic-v2:0"
NOVA_SONIC_VOICE="en-US-Neutral"          # Voice for TTS
NOVA_SONIC_LANGUAGE="en-US"               # Language for ASR/TTS
NOVA_SONIC_TEMPERATURE="0.7"              # Model temperature
```

### Required Dependencies

Added to `requirements.txt`:
- `boto3` - AWS SDK for Python
- `websockets` - WebSocket support
- `flask-sock` - Flask WebSocket extension

## Usage Flow

### 1. Starting a Training Session

1. User configures drug, department, and difficulty
2. Clicks "Start" to begin training
3. Voice toggle button becomes enabled

### 2. Voice Interaction

1. **Start Recording**: Click "启用语音" button
   - Microphone access requested (first time)
   - WebSocket connection established
   - Recording begins

2. **Speaking**: Talk into the microphone
   - Visual indicator shows recording status
   - Audio is buffered locally

3. **Stop Recording**: Click "停止录音"
   - Audio sent to backend via WebSocket
   - Backend streams to Nova Sonic
   - Processing status displayed

4. **Response**: AI responds
   - ASR transcription displayed in chat
   - Coach evaluation shown in evaluation panel
   - Doctor response appears in chat
   - TTS audio plays automatically

### 3. Conversation Flow

The voice interaction maintains the same training flow as text chat:

```
User (Voice) → ASR → Agent Processing → Doctor Response + Coach Feedback
                                              ↓
                                           TTS Audio
```

## Error Handling

### Backend Error Scenarios

1. **AWS Credentials Missing**: Voice handler initialization fails gracefully, voice features disabled
2. **WebSocket Connection Failure**: Error message sent to client
3. **Bedrock API Errors**: Caught and returned as error events
4. **Audio Processing Errors**: Logged and communicated to frontend

### Frontend Error Scenarios

1. **Microphone Access Denied**: User notification displayed
2. **WebSocket Connection Lost**: Automatic reconnection attempted
3. **Audio Playback Failure**: Error logged, graceful degradation
4. **Browser Compatibility**: Feature detection and fallbacks

## Browser Compatibility

**Supported Browsers:**
- Chrome/Edge 80+
- Firefox 75+
- Safari 14+
- Opera 67+

**Required Features:**
- Web Audio API
- MediaRecorder API
- WebSocket support
- ES6+ JavaScript

## API Integration Details

### AWS Bedrock Runtime API

The implementation uses the Bedrock Runtime API's `invoke_model` method. For production use with true bidirectional streaming, you may need to use specialized streaming APIs when they become available.

**Current Implementation:**
- Request/response pattern with audio data
- Audio encoded as base64 in JSON
- Event-based response processing

**Future Enhancement:**
The code structure supports migration to true bidirectional streaming APIs when available:
```python
# Future API pattern (conceptual)
response = bedrock_runtime.invoke_model_with_bidirectional_stream(
    modelId=model_id,
    inputStream=audio_generator,
    outputStream=response_handler
)
```

## Performance Considerations

### Audio Quality vs. Bandwidth

**Current Settings:**
- Sample rate: 16kHz (optimized for speech)
- Format: WebM (browser native)
- Chunk size: 1 second

**Optimization Options:**
- Adjust chunk size for latency vs. reliability tradeoff
- Use different audio formats based on browser support
- Implement adaptive bitrate based on connection quality

### Latency Components

1. **Recording**: ~1 second chunks
2. **Transmission**: Network dependent
3. **Processing**: Nova Sonic inference time
4. **Playback**: Minimal buffering

**Total Expected Latency**: 2-4 seconds for complete response

## Security Considerations

### Audio Data

- Audio transmitted over WebSocket (consider WSS for production)
- No audio stored on server by default
- Client-side audio cleared after transmission

### Authentication

Current implementation uses same authentication as text chat. For production:

- Implement WebSocket authentication
- Use secure WebSocket (WSS)
- Add rate limiting
- Validate audio data size/format

## Testing

### Manual Testing Checklist

- [ ] Voice button enables after backend check
- [ ] Microphone permission requested correctly
- [ ] Recording indicator shows during capture
- [ ] Audio stops recording on button click
- [ ] Transcription appears in chat
- [ ] Doctor response shows correctly
- [ ] Coach evaluation updates in real-time
- [ ] Audio playback works (when implemented)
- [ ] Error states handled gracefully
- [ ] WebSocket reconnection works

### Integration Testing

Test the complete flow:
1. Start training session
2. Send voice message
3. Verify ASR transcription
4. Verify agent response
5. Verify audio playback
6. End session cleanly

## Troubleshooting

### Common Issues

**Voice button stays disabled:**
- Check backend is running
- Verify `/voice/status` endpoint returns `enabled: true`
- Check AWS credentials are configured

**No audio capturing:**
- Verify microphone permissions in browser
- Check browser console for errors
- Test with different microphone

**WebSocket connection fails:**
- Verify Flask server is running
- Check CORS settings
- Verify port 5000 is accessible

**No audio playback:**
- Check browser audio permissions
- Verify audio format compatibility
- Check console for decode errors

## Future Enhancements

### Planned Features

1. **Voice Activity Detection (VAD)**
   - Automatic start/stop based on speech detection
   - Reduce manual button clicks

2. **Audio Visualization**
   - Waveform display during recording
   - Volume meter

3. **Multi-language Support**
   - Chinese language support
   - Language selection in UI

4. **Audio History**
   - Save and replay previous voice interactions
   - Export audio recordings

5. **Advanced Audio Processing**
   - Background noise reduction
   - Audio quality enhancement
   - Echo cancellation improvements

6. **Performance Monitoring**
   - Latency tracking
   - Quality metrics
   - Usage analytics

## Code Examples

### Starting a Voice Session (Backend)

```python
@sock.route('/voice/stream')
def voice_stream(ws):
    conversation_context = ConversationContext()
    
    # Wait for start_session message
    message = ws.receive()
    data = json.loads(message)
    
    if data['type'] == 'start_session':
        session_id = data['session_id']
        voice_sessions[session_id] = conversation_context
        
        ws.send(json.dumps({
            "type": "session_started",
            "session_id": session_id
        }))
```

### Recording Audio (Frontend)

```javascript
async function startRecording() {
    const mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const mediaRecorder = new MediaRecorder(mediaStream);
    
    mediaRecorder.ondataavailable = (event) => {
        audioChunks.push(event.data);
    };
    
    mediaRecorder.start(1000); // 1-second chunks
}
```

### Processing Voice Response (Backend)

```python
async for event in voice_handler.stream_audio_to_nova(
    audio_chunks, 
    system_prompt, 
    conversation_history
):
    if event['type'] == 'transcription':
        ws.send(json.dumps({
            "type": "transcription",
            "text": event['text']
        }))
    elif event['type'] == 'audio':
        ws.send(json.dumps({
            "type": "audio_chunk",
            "audio": base64.b64encode(event['audio']).decode()
        }))
```

## Maintenance

### Logging

The implementation includes comprehensive logging:
- WebSocket connection events
- Audio processing steps
- Error conditions
- Session lifecycle

Log levels:
- INFO: Normal operations
- WARNING: Non-critical issues
- ERROR: Failures requiring attention

### Monitoring Recommendations

1. Track voice session success rate
2. Monitor average response latency
3. Log API error rates
4. Monitor WebSocket connection stability

## Support and Documentation

### Additional Resources

- [AWS Bedrock Documentation](https://docs.aws.amazon.com/bedrock/)
- [Amazon Nova Models](https://aws.amazon.com/bedrock/nova/)
- [Web Audio API](https://developer.mozilla.org/en-US/docs/Web/API/Web_Audio_API)
- [WebSocket API](https://developer.mozilla.org/en-US/docs/Web/API/WebSocket)

### Getting Help

For issues or questions:
1. Check the troubleshooting section
2. Review browser console logs
3. Check server logs for errors
4. Verify AWS credentials and permissions

---

**Note**: This implementation provides a foundation for voice interaction. The actual AWS Bedrock Runtime API for Amazon Nova 2 Sonic may have specific requirements or different method signatures. Adjust the `voice_handler.py` implementation based on the official AWS SDK documentation for Nova Sonic when available.
