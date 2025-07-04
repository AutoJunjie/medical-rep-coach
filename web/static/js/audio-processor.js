// AudioWorklet processor for handling audio data
class AudioProcessor extends AudioWorkletProcessor {
    constructor() {
        super();
        this.bufferSize = 4096;
        this.buffer = new Float32Array(this.bufferSize);
        this.bufferIndex = 0;
    }
    
    process(inputs, outputs, parameters) {
        const input = inputs[0];
        if (input.length > 0) {
            const inputChannel = input[0];
            
            // Add input data to buffer
            for (let i = 0; i < inputChannel.length; i++) {
                this.buffer[this.bufferIndex++] = inputChannel[i];
                
                // When buffer is full, send data
                if (this.bufferIndex >= this.bufferSize) {
                    // Convert to 16-bit integers
                    const pcmData = new Int16Array(this.bufferSize);
                    for (let j = 0; j < this.bufferSize; j++) {
                        pcmData[j] = this.buffer[j] * 0x7FFF;
                    }
                    
                    // Send data to main thread
                    this.port.postMessage({
                        buffer: pcmData.buffer
                    }, [pcmData.buffer]);
                    
                    // Reset buffer
                    this.buffer = new Float32Array(this.bufferSize);
                    this.bufferIndex = 0;
                }
            }
        }
        
        return true;
    }
}

registerProcessor('audio-processor', AudioProcessor);
