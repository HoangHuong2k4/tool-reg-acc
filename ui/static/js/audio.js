function playMomoSound() {
    try {
        const ctx = new (window.AudioContext || window.webkitAudioContext)();
        for (let i = 0; i < 20; i++) {
            const t = ctx.currentTime + i * 0.4; // 0.4s delay between each "ting"
            
            const osc1 = ctx.createOscillator();
            const gain1 = ctx.createGain();
            osc1.connect(gain1);
            gain1.connect(ctx.destination);
            osc1.type = 'sine';
            osc1.frequency.setValueAtTime(880, t); 
            gain1.gain.setValueAtTime(0, t);
            gain1.gain.linearRampToValueAtTime(0.5, t + 0.05);
            gain1.gain.exponentialRampToValueAtTime(0.01, t + 0.5);
            osc1.start(t);
            osc1.stop(t + 0.5);
            
            const osc2 = ctx.createOscillator();
            const gain2 = ctx.createGain();
            osc2.connect(gain2);
            gain2.connect(ctx.destination);
            osc2.type = 'sine';
            osc2.frequency.setValueAtTime(1318.51, t + 0.15); 
            gain2.gain.setValueAtTime(0, t + 0.15);
            gain2.gain.linearRampToValueAtTime(0.5, t + 0.2);
            gain2.gain.exponentialRampToValueAtTime(0.01, t + 0.8);
            osc2.start(t + 0.15);
            osc2.stop(t + 0.8);
        }
    } catch(e) {
        console.log("Audio not supported");
    }
}
