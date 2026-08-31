function playMomoSound() {
    try {
        const ctx = new (window.AudioContext || window.webkitAudioContext)();

        function playNote(freq, startTime, duration, volume = 0.5) {
            const osc = ctx.createOscillator();
            const gain = ctx.createGain();
            osc.connect(gain);
            gain.connect(ctx.destination);
            osc.type = 'sine';
            osc.frequency.setValueAtTime(freq, startTime);
            gain.gain.setValueAtTime(0, startTime);
            gain.gain.linearRampToValueAtTime(volume, startTime + 0.05);
            gain.gain.exponentialRampToValueAtTime(0.01, startTime + duration);
            osc.start(startTime);
            osc.stop(startTime + duration);
        }

        const t = ctx.currentTime;
        playNote(880,     t + 0.0,  0.55);  // A5  - nốt 1
        playNote(1318.51, t + 0.35, 0.55);  // E6  - nốt 2
        playNote(1046.50, t + 0.70, 0.55);  // C6  - nốt 3
        playNote(1567.98, t + 1.05, 0.90);  // G6  - nốt 4 (cao, dài hơn)
        playNote(1318.51, t + 1.55, 0.65);  // E6  - nốt 5 (kết)

    } catch(e) {
        console.log("Audio not supported");
    }
}
