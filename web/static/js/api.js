/**
 * API Module - Handles all API calls to the backend
 */
export const API = {
    /**
     * Send a message to the backend chat endpoint
     * @param {string} message - The message to send
     * @returns {Promise<Object>} - The response from the backend
     */
    sendMessage: async function(message) {
        try {
            const response = await fetch('http://127.0.0.1:8080/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ message: message })
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({ detail: "请求后端失败，无法解析错误信息。" }));
                throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
            }

            return await response.json();
        } catch (error) {
            console.error('Error sending message:', error);
            throw error;
        }
    },

    /**
     * Send audio data to the backend for transcription
     * @param {Blob} audioBlob - The audio data to transcribe
     * @returns {Promise<Object>} - The transcription result
     */
    transcribeAudio: async function(audioBlob) {
        try {
            const formData = new FormData();
            formData.append('audio', audioBlob);
            
            const response = await fetch('http://127.0.0.1:8080/transcribe', {
                method: 'POST',
                body: formData
            });
            
            if (!response.ok) {
                throw new Error('语音转录失败');
            }
            
            return await response.json();
        } catch (error) {
            console.error('转录错误:', error);
            throw error;
        }
    }
};
