/**
 * Main application entry point
 */
import { ChatModule } from './chat.js';
import { VoiceModule } from './voice.js';
import { EvaluationModule } from './evaluation.js';

// Ensure marked is available or handle potential loading error
if (typeof marked === 'undefined') {
    console.warn('Marked.js library was not loaded. Markdown rendering will be disabled.');
    // Provide a dummy marked.parse function if it's not available to prevent errors
    window.marked = { parse: function(text) { return text; } }; 
}

/**
 * Initialize the application when the DOM is fully loaded
 */
document.addEventListener('DOMContentLoaded', function() {
    // Initialize Chat Module
    ChatModule.init({
        chatWindow: document.getElementById('chat-window'),
        userInput: document.getElementById('user-input'),
        sendBtn: document.getElementById('send-btn'),
        startBtn: document.getElementById('start-btn'),
        endTrainingBtn: document.getElementById('end-training-btn'),
        drugNameInput: document.getElementById('drug-name'),
        departmentInput: document.getElementById('department'),
        difficultySelect: document.getElementById('difficulty'),
        summaryReportDiv: document.getElementById('summary-report'),
        summaryContentDiv: document.getElementById('summary-content'),
        loadingSpinner: document.getElementById('loading-spinner'),
        doctorProfileContent: document.getElementById('doctor-profile-content'),
        realtimeEvaluationContent: document.getElementById('realtime-evaluation-content')
    });
    
    // Initialize Voice Module
    VoiceModule.init({
        voiceButton: document.getElementById('voice-input-button'),
        recordingIndicator: document.getElementById('recording-indicator'),
        userInput: document.getElementById('user-input')
    });
    
    // Initialize Evaluation Module
    EvaluationModule.init({
        doctorProfileContent: document.getElementById('doctor-profile-content'),
        realtimeEvaluationContent: document.getElementById('realtime-evaluation-content')
    });
    
    console.log('Med Coach application initialized');
});
