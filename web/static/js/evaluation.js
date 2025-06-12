/**
 * Evaluation Module - Handles doctor profile and evaluation display
 */
export const EvaluationModule = {
    // DOM elements
    elements: {
        doctorProfileContent: null,
        realtimeEvaluationContent: null
    },

    /**
     * Initialize the evaluation module
     * @param {Object} config - Configuration object with DOM elements
     */
    init: function(config) {
        // Store DOM elements
        this.elements = {
            doctorProfileContent: config.doctorProfileContent,
            realtimeEvaluationContent: config.realtimeEvaluationContent
        };
    },

    /**
     * Update the doctor profile content
     * @param {string} profileText - The profile text to display
     */
    updateDoctorProfile: function(profileText) {
        this.elements.doctorProfileContent.textContent = profileText;
    },

    /**
     * Update the evaluation content
     * @param {string} evaluationText - The evaluation text to display
     * @param {boolean} useMarkdown - Whether to render as markdown
     */
    updateEvaluation: function(evaluationText, useMarkdown = true) {
        if (useMarkdown && window.marked) {
            this.elements.realtimeEvaluationContent.innerHTML = marked.parse(evaluationText);
        } else {
            this.elements.realtimeEvaluationContent.textContent = evaluationText;
        }
    },

    /**
     * Reset the evaluation content
     */
    resetEvaluation: function() {
        this.elements.realtimeEvaluationContent.textContent = '等待用户回复后进行评估...';
    },

    /**
     * Reset the doctor profile content
     */
    resetDoctorProfile: function() {
        this.elements.doctorProfileContent.textContent = '请先开始训练以加载医生档案。';
    },

    /**
     * Set loading state for evaluation
     */
    setEvaluationLoading: function() {
        this.elements.realtimeEvaluationContent.textContent = '教练正在评估您的回答...';
    },

    /**
     * Set training ended state
     */
    setTrainingEnded: function() {
        this.elements.realtimeEvaluationContent.textContent = '训练已结束。查看下方总结报告。';
        this.resetDoctorProfile();
    }
};
