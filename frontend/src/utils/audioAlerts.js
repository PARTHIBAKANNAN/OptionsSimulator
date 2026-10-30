/**
 * Web Audio API Sound Synthesizer
 * Zero external audio file/CDN dependencies. Generates crystal-clear harmonic audio alerts.
 */

class SoundEngine {
  constructor() {
    this.ctx = null;
    this.muted = typeof localStorage !== "undefined" ? localStorage.getItem("options_sound_muted") === "true" : false;
    this.volume = typeof localStorage !== "undefined" ? parseFloat(localStorage.getItem("options_sound_volume") || "0.75") : 0.75;
  }

  _init() {
    if (!this.ctx && typeof window !== "undefined") {
      const AudioContext = window.AudioContext || window.webkitAudioContext;
      if (AudioContext) {
        this.ctx = new AudioContext();
      }
    }
    if (this.ctx && this.ctx.state === "suspended") {
      this.ctx.resume();
    }
  }

  isMuted() {
    return this.muted;
  }

  setMuted(muted) {
    this.muted = Boolean(muted);
    if (typeof localStorage !== "undefined") {
      localStorage.setItem("options_sound_muted", this.muted ? "true" : "false");
    }
  }

  toggleMute() {
    this.setMuted(!this.muted);
    return this.muted;
  }

  getVolume() {
    return this.volume;
  }

  setVolume(vol) {
    this.volume = Math.max(0.0, Math.min(1.0, parseFloat(vol) || 0.75));
    if (typeof localStorage !== "undefined") {
      localStorage.setItem("options_sound_volume", this.volume.toString());
    }
  }

  /**
   * 🔔 Order Entry Sound: Ascending energetic double chime (E5 -> B5)
   */
  playOrderEntry() {
    if (this.muted || this.volume <= 0) return;
    try {
      this._init();
      if (!this.ctx) return;
      const now = this.ctx.currentTime;
      const masterGain = this.volume;

      // Note 1: E5 (659 Hz)
      const osc1 = this.ctx.createOscillator();
      const gain1 = this.ctx.createGain();
      osc1.type = "sine";
      osc1.frequency.setValueAtTime(659.25, now);
      gain1.gain.setValueAtTime(0.14 * masterGain, now);
      gain1.gain.exponentialRampToValueAtTime(0.001, now + 0.18);
      osc1.connect(gain1);
      gain1.connect(this.ctx.destination);
      osc1.start(now);
      osc1.stop(now + 0.18);

      // Note 2: B5 (987 Hz)
      const osc2 = this.ctx.createOscillator();
      const gain2 = this.ctx.createGain();
      osc2.type = "triangle";
      osc2.frequency.setValueAtTime(987.77, now + 0.12);
      gain2.gain.setValueAtTime(0.16 * masterGain, now + 0.12);
      gain2.gain.exponentialRampToValueAtTime(0.001, now + 0.35);
      osc2.connect(gain2);
      gain2.connect(this.ctx.destination);
      osc2.start(now + 0.12);
      osc2.stop(now + 0.35);
    } catch (e) {
      console.warn("Audio alert error:", e);
    }
  }

  /**
   * 🛡️ TSL Locked Sound: Resonant harmonic shield lock tone (C5 -> C6 ramp)
   */
  playTslLocked() {
    if (this.muted || this.volume <= 0) return;
    try {
      this._init();
      if (!this.ctx) return;
      const now = this.ctx.currentTime;
      const masterGain = this.volume;

      const osc = this.ctx.createOscillator();
      const gain = this.ctx.createGain();
      osc.type = "sine";
      osc.frequency.setValueAtTime(523.25, now); // C5
      osc.frequency.exponentialRampToValueAtTime(1046.5, now + 0.22); // C6
      gain.gain.setValueAtTime(0.18 * masterGain, now);
      gain.gain.exponentialRampToValueAtTime(0.001, now + 0.42);
      osc.connect(gain);
      gain.connect(this.ctx.destination);
      osc.start(now);
      osc.stop(now + 0.42);
    } catch (e) {
      console.warn("Audio alert error:", e);
    }
  }

  /**
   * 💰 Target / Profit Exit Sound: Triumphant 4-note ascending major arpeggio
   */
  playTargetHit() {
    if (this.muted || this.volume <= 0) return;
    try {
      this._init();
      if (!this.ctx) return;
      const now = this.ctx.currentTime;
      const masterGain = this.volume;

      // C5, E5, G5, C6 triumphant arpeggio
      [523.25, 659.25, 783.99, 1046.5].forEach((freq, idx) => {
        const osc = this.ctx.createOscillator();
        const gain = this.ctx.createGain();
        osc.type = "sine";
        osc.frequency.setValueAtTime(freq, now + idx * 0.07);
        gain.gain.setValueAtTime(0.12 * masterGain, now + idx * 0.07);
        gain.gain.exponentialRampToValueAtTime(0.001, now + idx * 0.07 + 0.28);
        osc.connect(gain);
        gain.connect(this.ctx.destination);
        osc.start(now + idx * 0.07);
        osc.stop(now + idx * 0.07 + 0.28);
      });
    } catch (e) {
      console.warn("Audio alert error:", e);
    }
  }

  playTargetExit() {
    this.playTargetHit();
  }

  /**
   * ⚠️ Stop-Loss Hit Sound: Descending dual harmonic alert tone (A4 -> F4 -> D4)
   */
  playStopLossHit() {
    if (this.muted || this.volume <= 0) return;
    try {
      this._init();
      if (!this.ctx) return;
      const now = this.ctx.currentTime;
      const masterGain = this.volume;

      // Descending minor warning: 440 Hz (A4) -> 349 Hz (F4) -> 293 Hz (D4)
      [440.0, 349.23, 293.66].forEach((freq, idx) => {
        const osc = this.ctx.createOscillator();
        const gain = this.ctx.createGain();
        osc.type = "triangle";
        osc.frequency.setValueAtTime(freq, now + idx * 0.1);
        gain.gain.setValueAtTime(0.15 * masterGain, now + idx * 0.1);
        gain.gain.exponentialRampToValueAtTime(0.001, now + idx * 0.1 + 0.22);
        osc.connect(gain);
        gain.connect(this.ctx.destination);
        osc.start(now + idx * 0.1);
        osc.stop(now + idx * 0.1 + 0.22);
      });
    } catch (e) {
      console.warn("Audio alert error:", e);
    }
  }

  /**
   * 🚨 Emergency Square-Off / Warning Tone: Dual pulse warning buzz
   */
  playSquareOff() {
    if (this.muted || this.volume <= 0) return;
    try {
      this._init();
      if (!this.ctx) return;
      const now = this.ctx.currentTime;
      const masterGain = this.volume;

      const osc = this.ctx.createOscillator();
      const gain = this.ctx.createGain();
      osc.type = "sawtooth";
      osc.frequency.setValueAtTime(392.0, now); // G4
      osc.frequency.setValueAtTime(311.13, now + 0.14); // Eb4
      gain.gain.setValueAtTime(0.12 * masterGain, now);
      gain.gain.exponentialRampToValueAtTime(0.001, now + 0.35);
      osc.connect(gain);
      gain.connect(this.ctx.destination);
      osc.start(now);
      osc.stop(now + 0.35);
    } catch (e) {
      console.warn("Audio alert error:", e);
    }
  }
}

export const soundEngine = new SoundEngine();
