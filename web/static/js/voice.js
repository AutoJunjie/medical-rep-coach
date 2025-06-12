/**
 * Voice Module - Handles voice recording and transcription
 */
import { API } from './api.js';

export const VoiceModule = {
    // DOM elements
    elements: {
        voiceButton: null,
        recordingIndicator: null,
        userInput: null
    },

    // State
    state: {
        mediaRecorder: null,
        audioChunks: [],
        isRecording: false
    },

    /**
     * Initialize the voice module
     * @param {Object} config - Configuration object with DOM elements
     */
    init: function(config) {
        // Store DOM elements
        this.elements = {
            voiceButton: config.voiceButton,
            recordingIndicator: config.recordingIndicator,
            userInput: config.userInput
        };

        // Set up event listeners
        this._setupEventListeners();
    },

    /**
     * Set up event listeners for voice functionality
     * @private
     */
    _setupEventListeners: function() {
        this.elements.voiceButton.addEventListener('click', () => this.toggleRecording());
    },

    /**
     * Toggle recording state
     */
    toggleRecording: async function() {
        if (this.state.isRecording) {
            this.stopRecording();
        } else {
            await this.startRecording();
        }
    },

    /**
     * Start recording audio
     */
    startRecording: async function() {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            this.state.audioChunks = [];
            
            this.state.mediaRecorder = new MediaRecorder(stream);
            
            this.state.mediaRecorder.ondataavailable = (event) => {
                this.state.audioChunks.push(event.data);
            };
            
            this.state.mediaRecorder.onstop = async () => {
                await this._processRecording(stream);
            };
            
            this.state.mediaRecorder.start();
            this.elements.voiceButton.innerHTML = '<i class="fas fa-stop"></i>';
            this.elements.voiceButton.classList.add('recording');
            this.elements.recordingIndicator.style.display = 'inline';
            this.state.isRecording = true;
            
        } catch (error) {
            console.error('无法访问麦克风:', error);
            alert('无法访问麦克风: ' + error.message);
        }
    },

    /**
     * Stop recording audio
     */
    stopRecording: function() {
        if (this.state.mediaRecorder && this.state.isRecording) {
            this.state.mediaRecorder.stop();
            this.elements.voiceButton.innerHTML = '<i class="fas fa-microphone"></i>';
            this.elements.voiceButton.classList.remove('recording');
            this.elements.recordingIndicator.style.display = 'none';
            this.state.isRecording = false;
        }
    },

    /**
     * Process the recorded audio
     * @param {MediaStream} stream - The media stream to close
     * @private
     */
    _processRecording: async function(stream) {
        // Process recording data
        const audioBlob = new Blob(this.state.audioChunks, { type: 'audio/wav' });
        
        // Show processing status
        const originalValue = this.elements.userInput.value;
        this.elements.userInput.value = "正在转录语音...";
        this.elements.userInput.disabled = true;
        
        try {
            // Send to backend for transcription
            const data = await API.transcribeAudio(audioBlob);
            
            // Fill transcribed text into input box
            this.elements.userInput.value = data.text;
            this.elements.userInput.disabled = false;
            this.elements.userInput.focus();
            
        } catch (error) {
            console.error('转录错误:', error);
            this.elements.userInput.value = originalValue;
            this.elements.userInput.disabled = false;
            alert('语音转录失败: ' + error.message);
        }
        
        // Close all audio tracks
        stream.getTracks().forEach(track => track.stop());
    }
};
