// Zero-dependency Web Audio API Feline Sound Synthesizer (Purr, Meow, Mrrp, Chirp, Bell)

export class CatAudioEngine {
  constructor() {
    this.ctx = null;
    this.enabled = true;
    this.purrGain = null;
    this.purrTarget = 0;
    this.purrCurrent = 0;
    this.lastMeowTime = 0;
    this.lastBellTime = 0;
  }

  unlock() {
    if (!this.enabled) return;
    if (!this.ctx) {
      const AudioCtx = window.AudioContext || window.webkitAudioContext;
      if (!AudioCtx) return;
      this.ctx = new AudioCtx();
      this._initPurrRig();
    }
    if (this.ctx && this.ctx.state === "suspended") {
      this.ctx.resume().catch(() => {});
    }
  }

  setEnabled(on) {
    this.enabled = on;
    if (!on && this.purrGain && this.ctx) {
      this.purrTarget = 0;
      this.purrGain.gain.setTargetAtTime(0.0, this.ctx.currentTime, 0.08);
    }
  }

  _initPurrRig() {
    const ctx = this.ctx;
    // Organic feline purr: 26 Hz fundamental + 52 Hz harmonic + subtle breathy pink noise modulated at ~0.55 Hz!
    this.purrGain = ctx.createGain();
    this.purrGain.gain.value = 0.0;

    const lpf = ctx.createBiquadFilter();
    lpf.type = "lowpass";
    lpf.frequency.value = 185;
    lpf.Q.value = 1.6;

    const osc1 = ctx.createOscillator();
    osc1.type = "sawtooth";
    osc1.frequency.value = 26.0;

    const osc2 = ctx.createOscillator();
    osc2.type = "triangle";
    osc2.frequency.value = 52.0;

    const g1 = ctx.createGain();
    g1.gain.value = 0.55;
    const g2 = ctx.createGain();
    g2.gain.value = 0.35;

    // Breathing rhythm LFO (~2.2s inhale/exhale cycle)
    const lfo = ctx.createOscillator();
    lfo.type = "sine";
    lfo.frequency.value = 0.45;
    const lfoAmp = ctx.createGain();
    lfoAmp.gain.value = 0.32;

    const baseAmp = ctx.createGain();
    baseAmp.gain.value = 0.65;
    lfo.connect(lfoAmp);
    lfoAmp.connect(baseAmp.gain);

    // Subtle soft breath texture
    const noiseLen = ctx.sampleRate * 2;
    const noiseBuf = ctx.createBuffer(1, noiseLen, ctx.sampleRate);
    const data = noiseBuf.getChannelData(0);
    let b0 = 0, b1 = 0, b2 = 0;
    for (let i = 0; i < noiseLen; i++) {
      const white = Math.random() * 2 - 1;
      b0 = 0.997 * b0 + white * 0.029;
      b1 = 0.985 * b1 + white * 0.032;
      b2 = 0.950 * b2 + white * 0.048;
      data[i] = (b0 + b1 + b2) * 0.35;
    }
    const noiseSrc = ctx.createBufferSource();
    noiseSrc.buffer = noiseBuf;
    noiseSrc.loop = true;
    const noiseGain = ctx.createGain();
    noiseGain.gain.value = 0.16;

    osc1.connect(g1);
    osc2.connect(g2);
    g1.connect(lpf);
    g2.connect(lpf);
    noiseSrc.connect(noiseGain);
    noiseGain.connect(lpf);

    lpf.connect(baseAmp);
    baseAmp.connect(this.purrGain);
    this.purrGain.connect(ctx.destination);

    osc1.start();
    osc2.start();
    lfo.start();
    noiseSrc.start();
  }

  setPurr(intensity) {
    this.purrTarget = Math.max(0, Math.min(1, intensity));
  }

  update(dt) {
    if (!this.ctx || !this.purrGain) return;
    const target = this.enabled ? this.purrTarget : 0;
    this.purrCurrent += (target - this.purrCurrent) * Math.min(1, dt * 4.5);
    this.purrGain.gain.setTargetAtTime(this.purrCurrent * 0.22, this.ctx.currentTime, 0.05);
  }

  playMeow(kind = "meow") {
    if (!this.enabled) return;
    this.unlock();
    if (!this.ctx) return;
    const now = this.ctx.currentTime;
    if (now - this.lastMeowTime < 0.35) return;
    this.lastMeowTime = now;

    const ctx = this.ctx;
    const osc = ctx.createOscillator();
    const oscSub = ctx.createOscillator();
    const formant1 = ctx.createBiquadFilter();
    const formant2 = ctx.createBiquadFilter();
    const env = ctx.createGain();

    osc.type = "sawtooth";
    oscSub.type = "triangle";

    formant1.type = "bandpass";
    formant1.Q.value = 3.2;
    formant2.type = "bandpass";
    formant2.Q.value = 4.0;

    if (kind === "mrrp") {
      // Cute short questioning trill on nose boop / wake
      const dur = 0.22;
      osc.frequency.setValueAtTime(340, now);
      osc.frequency.exponentialRampToValueAtTime(620, now + dur * 0.85);
      oscSub.frequency.setValueAtTime(170, now);
      oscSub.frequency.exponentialRampToValueAtTime(310, now + dur * 0.85);

      formant1.frequency.setValueAtTime(650, now);
      formant1.frequency.linearRampToValueAtTime(1050, now + dur);
      formant2.frequency.setValueAtTime(1500, now);

      env.gain.setValueAtTime(0.001, now);
      env.gain.linearRampToValueAtTime(0.11, now + 0.04);
      env.gain.exponentialRampToValueAtTime(0.001, now + dur);

      this._startStopVoice(osc, oscSub, formant1, formant2, env, now, dur);
    } else if (kind === "chirp") {
      // Excited laser/toy "ek-ek / chirrup!"
      const dur = 0.14;
      osc.frequency.setValueAtTime(520, now);
      osc.frequency.exponentialRampToValueAtTime(840, now + 0.07);
      osc.frequency.exponentialRampToValueAtTime(620, now + dur);
      oscSub.frequency.setValueAtTime(260, now);

      formant1.frequency.setValueAtTime(920, now);
      formant2.frequency.setValueAtTime(2100, now);

      env.gain.setValueAtTime(0.001, now);
      env.gain.linearRampToValueAtTime(0.09, now + 0.025);
      env.gain.exponentialRampToValueAtTime(0.001, now + dur);

      this._startStopVoice(osc, oscSub, formant1, formant2, env, now, dur);
    } else {
      // Expressive sweet "mee-oww"
      const dur = 0.56;
      const base = 420 + Math.random() * 55;
      osc.frequency.setValueAtTime(base * 0.88, now);
      osc.frequency.exponentialRampToValueAtTime(base * 1.48, now + 0.16);
      osc.frequency.exponentialRampToValueAtTime(base * 0.84, now + dur);

      oscSub.frequency.setValueAtTime(base * 0.44, now);
      oscSub.frequency.exponentialRampToValueAtTime(base * 0.74, now + 0.16);
      oscSub.frequency.exponentialRampToValueAtTime(base * 0.42, now + dur);

      formant1.frequency.setValueAtTime(620, now);
      formant1.frequency.linearRampToValueAtTime(980, now + 0.18);
      formant1.frequency.linearRampToValueAtTime(540, now + dur);

      formant2.frequency.setValueAtTime(1400, now);
      formant2.frequency.linearRampToValueAtTime(2150, now + 0.18);
      formant2.frequency.linearRampToValueAtTime(1250, now + dur);

      env.gain.setValueAtTime(0.001, now);
      env.gain.linearRampToValueAtTime(0.13, now + 0.07);
      env.gain.setValueAtTime(0.12, now + 0.24);
      env.gain.exponentialRampToValueAtTime(0.001, now + dur);

      this._startStopVoice(osc, oscSub, formant1, formant2, env, now, dur);
    }
  }

  _startStopVoice(osc, oscSub, f1, f2, env, now, dur) {
    const mix = this.ctx.createGain();
    mix.gain.value = 0.5;
    osc.connect(mix);
    oscSub.connect(mix);

    mix.connect(f1);
    mix.connect(f2);
    f1.connect(env);
    f2.connect(env);
    env.connect(this.ctx.destination);

    osc.start(now);
    oscSub.start(now);
    osc.stop(now + dur + 0.03);
    oscSub.stop(now + dur + 0.03);
  }

  playBell(strength = 0.7) {
    if (!this.enabled || !this.ctx) return;
    const now = this.ctx.currentTime;
    if (now - this.lastBellTime < 0.25) return;
    this.lastBellTime = now;

    const freqs = [2920, 4410, 6180];
    freqs.forEach((f, idx) => {
      const osc = this.ctx.createOscillator();
      const g = this.ctx.createGain();
      osc.type = "sine";
      osc.frequency.setValueAtTime(f + (Math.random() - 0.5) * 35, now);
      const amp = (0.028 / (idx + 1)) * Math.min(1, strength);
      g.gain.setValueAtTime(amp, now);
      g.gain.exponentialRampToValueAtTime(0.0001, now + 0.34 - idx * 0.06);
      osc.connect(g);
      g.connect(this.ctx.destination);
      osc.start(now);
      osc.stop(now + 0.38);
    });
  }
}
