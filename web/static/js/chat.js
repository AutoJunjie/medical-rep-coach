/**
 * Chat Module - Handles chat functionality
 */
import { API } from './api.js';

export const ChatModule = {
    // DOM elements
    elements: {
        chatWindow: null,
        userInput: null,
        sendBtn: null,
        startBtn: null,
        endTrainingBtn: null,
        drugNameInput: null,
        departmentInput: null,
        difficultySelect: null,
        summaryReportDiv: null,
        summaryContentDiv: null,
        loadingSpinner: null,
        doctorProfileContent: null,
        realtimeEvaluationContent: null
    },

    // State
    state: {
        conversationActive: false,
        currentDoctorName: "医生"
    },

    /**
     * Initialize the chat module
     * @param {Object} config - Configuration object with DOM elements
     */
    init: function(config) {
        // Store DOM elements
        this.elements = {
            chatWindow: config.chatWindow,
            userInput: config.userInput,
            sendBtn: config.sendBtn,
            startBtn: config.startBtn,
            endTrainingBtn: config.endTrainingBtn,
            drugNameInput: config.drugNameInput,
            departmentInput: config.departmentInput,
            difficultySelect: config.difficultySelect,
            summaryReportDiv: config.summaryReportDiv,
            summaryContentDiv: config.summaryContentDiv,
            loadingSpinner: config.loadingSpinner,
            doctorProfileContent: config.doctorProfileContent,
            realtimeEvaluationContent: config.realtimeEvaluationContent
        };

        // Set up event listeners
        this._setupEventListeners();
    },

    /**
     * Set up event listeners for chat functionality
     * @private
     */
    _setupEventListeners: function() {
        // Start button click
        this.elements.startBtn.addEventListener('click', () => this._handleStartClick());

        // Send button click
        this.elements.sendBtn.addEventListener('click', () => this._handleSendClick());

        // End training button click
        this.elements.endTrainingBtn.addEventListener('click', () => this._handleEndTrainingClick());

        // Enter key press in input field
        this.elements.userInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.elements.sendBtn.click();
            }
        });
        
        // Auto-resize input field
        this.elements.userInput.addEventListener('input', () => {
            this.elements.userInput.style.height = 'auto';
            this.elements.userInput.style.height = this.elements.userInput.scrollHeight + 'px';
        });
    },

    /**
     * Handle start button click
     * @private
     */
    _handleStartClick: function() {
        const drug = this.elements.drugNameInput.value.trim();
        const department = this.elements.departmentInput.value.trim();
        const difficulty = this.elements.difficultySelect.value;

        if (!drug || !department) {
            this.addMessage("System", "请输入药品和科室信息。", 'system');
            return;
        }

        this.elements.chatWindow.innerHTML = ''; // Clear chat window
        this.elements.summaryReportDiv.style.display = 'none';
        this.elements.summaryContentDiv.textContent = '';
        this.elements.doctorProfileContent.textContent = '正在加载医生档案...';
        this.elements.realtimeEvaluationContent.textContent = '等待用户回复后进行评估...';

        const startMessage = `药品: ${drug}；科室: ${department}；难度: ${difficulty}。点击【Start】`;
        this.addMessage("User", startMessage, 'user');
        this.sendMessageToBackend(startMessage);
        this.state.conversationActive = true;
    },

    /**
     * Handle send button click
     * @private
     */
    _handleSendClick: function() {
        const messageText = this.elements.userInput.value.trim();
        if (messageText && this.state.conversationActive) {
            this.addMessage("User", messageText, 'user');
            this.elements.realtimeEvaluationContent.textContent = '教练正在评估您的回答...';
            this.sendMessageToBackend(messageText);
            this.elements.userInput.value = '';
            this.elements.userInput.style.height = 'auto';
            this.elements.userInput.style.height = this.elements.userInput.scrollHeight + 'px';
        } else if (!this.state.conversationActive) {
            this.addMessage("System", "请先点击 Start 开始新的训练。", 'system');
        }
    },

    /**
     * Handle end training button click
     * @private
     */
    _handleEndTrainingClick: function() {
        if (this.state.conversationActive) {
            const endMessage = "点击【结束训练】";
            this.addMessage("User", endMessage, 'user');
            this.sendMessageToBackend(endMessage);
        } else {
            this.addMessage("System", "当前没有正在进行的训练。", 'system');
        }
    },

    /**
     * Add a message to the chat window
     * @param {string} sender - The sender of the message
     * @param {string} text - The message text
     * @param {string} type - The message type (user, doctor, system, coach)
     */
    addMessage: function(sender, text, type) {
        const messageDiv = document.createElement('div');
        messageDiv.classList.add('message', type);
        
        const contentDiv = document.createElement('div');
        contentDiv.classList.add('message-content');
        contentDiv.textContent = text;

        if (type === 'doctor') {
            const senderNameDiv = document.createElement('div');
            senderNameDiv.classList.add('sender-name');
            senderNameDiv.textContent = sender;
            messageDiv.appendChild(senderNameDiv);
        }
        
        messageDiv.appendChild(contentDiv);
        this.elements.chatWindow.appendChild(messageDiv);
        this.elements.chatWindow.scrollTop = this.elements.chatWindow.scrollHeight;
    },

    /**
     * Show or hide the loading spinner
     * @param {boolean} show - Whether to show the spinner
     */
    showLoading: function(show) {
        this.elements.loadingSpinner.style.display = show ? 'inline-block' : 'none';
    },

    /**
     * Send a message to the backend and process the response
     * @param {string} message - The message to send
     */
    sendMessageToBackend: async function(message) {
        this.showLoading(true);
        try {
            const data = await API.sendMessage(message);
            
            if (data.responses && Array.isArray(data.responses)) {
                data.responses.forEach(res => {
                    if (res.startsWith("Doctor")) {
                        const parts = res.split('▶', 2);
                        this.state.currentDoctorName = parts[0].replace(/^Doctor\s*/, "").trim() || "医生";
                        let messageText = parts.length > 1 ? parts[1].trim() : '';

                        messageText = messageText.replace(/ _ObjectionTool_$/, "").trim();
                        messageText = messageText.replace(/ _EvalTool_$/, "").trim();
                        
                        if (messageText.startsWith("Response: ")) {
                            messageText = messageText.substring("Response: ".length).trim();
                        }
                        if (this.state.currentDoctorName && messageText.startsWith(this.state.currentDoctorName + ": ")) {
                            messageText = messageText.substring((this.state.currentDoctorName + ": ".length)).trim();
                        }
                        if (messageText === this.state.currentDoctorName + ":") {
                            messageText = "";
                        }
                        this.addMessage(this.state.currentDoctorName, messageText, 'doctor');
                    
                    } else if (res.startsWith("Coach")) {
                        const coachMessage = res.replace(/^Coach\s*▶\s*/, '').trim();
                        // Render Markdown in the realtime evaluation panel
                        if (window.marked) {
                            this.elements.realtimeEvaluationContent.innerHTML = marked.parse(coachMessage);
                        } else {
                            this.elements.realtimeEvaluationContent.textContent = coachMessage;
                        }
                    
                    } else if (res.startsWith("Summary")) {
                        const summaryText = res.replace(/^Summary\s*▶\s*/, '').trim();
                        // Render Markdown for summary report
                        if (window.marked) {
                            this.elements.summaryContentDiv.innerHTML = marked.parse(summaryText);
                        } else {
                            this.elements.summaryContentDiv.textContent = summaryText;
                        }
                        this.elements.summaryReportDiv.style.display = 'block';
                        this.elements.realtimeEvaluationContent.textContent = "训练已结束。查看下方总结报告。";
                        this.elements.doctorProfileContent.textContent = "请先开始新的训练以加载医生档案。";
                        this.state.conversationActive = false;
                    
                    } else if (res.startsWith("System     ▶ 【医生档案】")) {
                        const profileInfo = res.replace(/^System\s*▶\s*【医生档案】\s*/, '').trim();
                        this.elements.doctorProfileContent.textContent = profileInfo;
                    
                    } else if (res.startsWith("System: ") || res.startsWith("System     ▶")) {
                        this.addMessage("System", res.replace(/^System(:|\s*▶)\s*/, ''), 'system');
                    
                    } else {
                        this.addMessage("System", res, 'system');
                    }
                });
            } else {
                this.addMessage("System", "后端返回了无效的数据格式。", 'system');
            }

        } catch (error) {
            console.error('Error sending message:', error);
            this.addMessage("System", `错误: ${error.message}`, 'system');
            this.elements.realtimeEvaluationContent.textContent = `错误: ${error.message}`;
        } finally {
            this.showLoading(false);
        }
    }
};
