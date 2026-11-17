// 사용: swift music.swift events.json out.wav 총초
// macOS 기본 GS 악기(gs_instruments.dls, General MIDI 128가지 + 드럼)로 오프라인 렌더한다.
//
// events.json 은 둘 중 하나:
//   [ {t, dur, note, vel, inst}, ... ]                       — 예전 형식(피아노·현악, 홀 잔향 28)
//   {"mix": {...}, "reverb": "mediumRoom", "wet": 20, "events": [...]}
// inst: "piano"(0) · "strings"(49) · "drums"(GM 드럼, 36 킥 · 38 스네어 · 42 닫힌 하이햇 …) · "gm<번호>"(GM 악기 번호,
//       예: gm4 일렉 피아노 · gm33 베이스 · gm89 따뜻한 패드 · gm11 비브라폰 · gm24 나일론 기타 · gm46 하프)
// mix: {"<inst>": {"vol": 0~1, "dry": true}} — dry 면 잔향을 거치지 않는다(드럼·베이스).
import AVFoundation
import AudioToolbox

struct Ev: Decodable { let t: Double; let dur: Double; let note: Int; let vel: Int; let inst: String }
struct Mix: Decodable { let vol: Double?; let dry: Bool? }
struct Song: Decodable { let events: [Ev]; let mix: [String: Mix]?; let reverb: String?; let wet: Double? }

let args = CommandLine.arguments
let data = try Data(contentsOf: URL(fileURLWithPath: args[1]))
var song: Song
if let s = try? JSONDecoder().decode(Song.self, from: data) {
    song = s
} else {
    song = Song(events: try JSONDecoder().decode([Ev].self, from: data), mix: ["strings": Mix(vol: 0.55, dry: false)],
                reverb: nil, wet: nil)
}
let outURL = URL(fileURLWithPath: args[2]); let total = Double(args[3])!
let dls = URL(fileURLWithPath: "/System/Library/Components/CoreAudio.component/Contents/Resources/gs_instruments.dls")

let presets: [String: AVAudioUnitReverbPreset] = ["largeHall": .largeHall, "mediumHall": .mediumHall,
    "mediumRoom": .mediumRoom, "smallRoom": .smallRoom, "largeRoom": .largeRoom, "plate": .plate, "cathedral": .cathedral]
let engine = AVAudioEngine()
let wetBus = AVAudioMixerNode(), dryBus = AVAudioMixerNode(), reverb = AVAudioUnitReverb()
reverb.loadFactoryPreset(presets[song.reverb ?? "largeHall"] ?? .largeHall); reverb.wetDryMix = Float(song.wet ?? 28)
let fmt = AVAudioFormat(standardFormatWithSampleRate: 44100, channels: 2)!
for n in [wetBus, dryBus, reverb] as [AVAudioNode] { engine.attach(n) }
engine.connect(wetBus, to: reverb, format: fmt); engine.connect(reverb, to: engine.mainMixerNode, format: fmt)
engine.connect(dryBus, to: engine.mainMixerNode, format: fmt)

var samplers: [String: AVAudioUnitSampler] = [:]
for name in Set(song.events.map { $0.inst }).sorted() {
    let s = AVAudioUnitSampler(); engine.attach(s)
    let m = song.mix?[name]
    engine.connect(s, to: (m?.dry ?? false) ? dryBus : wetBus, format: fmt)
    s.volume = Float(m?.vol ?? 1.0)
    samplers[name] = s
}
try engine.enableManualRenderingMode(.offline, format: fmt, maximumFrameCount: 512)
try engine.start()
let msb = UInt8(kAUSampler_DefaultMelodicBankMSB), lsb = UInt8(kAUSampler_DefaultBankLSB)
for (name, s) in samplers {
    if name == "drums" {
        try s.loadSoundBankInstrument(at: dls, program: 0, bankMSB: UInt8(kAUSampler_DefaultPercussionBankMSB), bankLSB: lsb)
    } else {
        let program: UInt8 = name == "piano" ? 0 : name == "strings" ? 49 : UInt8(name.dropFirst(2)) ?? 0
        try s.loadSoundBankInstrument(at: dls, program: program, bankMSB: msb, bankLSB: lsb)
    }
}

struct Act { let t: Double; let on: Bool; let note: UInt8; let vel: UInt8; let s: AVAudioUnitSampler }
var acts: [Act] = []
for e in song.events {
    let s = samplers[e.inst]!
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
