// 사용: swift music.swift events.json out.wav 총초  (events: [{t, dur, note, vel, inst: "piano"|"strings"}])
// macOS 기본 GS 악기(gs_instruments.dls)로 피아노(0)·현악(49)을 오프라인 렌더하고 홀 잔향을 건다.
import AVFoundation
import AudioToolbox

struct Ev: Decodable { let t: Double; let dur: Double; let note: Int; let vel: Int; let inst: String }
let args = CommandLine.arguments
let events = try JSONDecoder().decode([Ev].self, from: Data(contentsOf: URL(fileURLWithPath: args[1])))
let outURL = URL(fileURLWithPath: args[2]); let total = Double(args[3])!
let dls = URL(fileURLWithPath: "/System/Library/Components/CoreAudio.component/Contents/Resources/gs_instruments.dls")

let engine = AVAudioEngine()
let piano = AVAudioUnitSampler(), strings = AVAudioUnitSampler()
let sub = AVAudioMixerNode(), reverb = AVAudioUnitReverb()
reverb.loadFactoryPreset(.largeHall); reverb.wetDryMix = 28
for n in [piano, strings, sub, reverb] as [AVAudioNode] { engine.attach(n) }
let fmt = AVAudioFormat(standardFormatWithSampleRate: 44100, channels: 2)!
engine.connect(piano, to: sub, format: fmt); engine.connect(strings, to: sub, format: fmt)
engine.connect(sub, to: reverb, format: fmt); engine.connect(reverb, to: engine.mainMixerNode, format: fmt)
strings.volume = 0.55
try engine.enableManualRenderingMode(.offline, format: fmt, maximumFrameCount: 512)
try engine.start()
let msb = UInt8(kAUSampler_DefaultMelodicBankMSB), lsb = UInt8(kAUSampler_DefaultBankLSB)
try piano.loadSoundBankInstrument(at: dls, program: 0, bankMSB: msb, bankLSB: lsb)
try strings.loadSoundBankInstrument(at: dls, program: 49, bankMSB: msb, bankLSB: lsb)

struct Act { let t: Double; let on: Bool; let note: UInt8; let vel: UInt8; let s: AVAudioUnitSampler }
var acts: [Act] = []
for e in events {
    let s = e.inst == "strings" ? strings : piano
    acts.append(Act(t: e.t, on: true, note: UInt8(e.note), vel: UInt8(e.vel), s: s))
    acts.append(Act(t: e.t + e.dur, on: false, note: UInt8(e.note), vel: 0, s: s))
}
acts.sort { $0.t < $1.t || ($0.t == $1.t && !$0.on && $1.on) }

let file = try AVAudioFile(forWriting: outURL, settings: fmt.settings)
let buf = AVAudioPCMBuffer(pcmFormat: engine.manualRenderingFormat, frameCapacity: engine.manualRenderingMaximumFrameCount)!
let totalFrames = AVAudioFramePosition(total * 44100)
var i = 0
while engine.manualRenderingSampleTime < totalFrames {
    let now = Double(engine.manualRenderingSampleTime) / 44100
    while i < acts.count && acts[i].t <= now {
        let a = acts[i]
        if a.on { a.s.startNote(a.note, withVelocity: a.vel, onChannel: 0) } else { a.s.stopNote(a.note, onChannel: 0) }
        i += 1
    }
    let frames = min(buf.frameCapacity, AVAudioFrameCount(totalFrames - engine.manualRenderingSampleTime))
    let st = try engine.renderOffline(frames, to: buf)
    if st == .success { try file.write(from: buf) } else { print("render status", st.rawValue); break }
}
engine.stop(); print("wrote", outURL.path)
