from __future__ import annotations
import asyncio
import io
import json
from pathlib import Path
import time
import wave
import numpy as np
from .config import STATE
from .storage import bound_root

KWS = "models/wake_word/sherpa-onnx-kws-zipformer-gigaspeech-3.3M-2024-01-01"
ASR = "models/speech_to_text/sherpa-onnx-whisper-tiny.en"

class Speech:
    def __init__(self):
        self.recognizer=None
        self.lock=asyncio.Lock()

    def kws(self, phrase="Hey Jarvis"):
        import sherpa_onnx
        import sentencepiece
        root=bound_root(STATE/"storage.json")
        processor=sentencepiece.SentencePieceProcessor(model_file=root.runtime_path(KWS+"/bpe.model"))
        pieces=processor.encode(phrase.upper(),out_type=str)
        tokens=root.read(KWS+"/tokens.txt").decode().splitlines()
        vocabulary={s.rsplit(" ",1)[0] for s in tokens}
        if not pieces or any(x not in vocabulary for x in pieces):
            raise ValueError("Wake phrase cannot be represented by this detector")
        keywords=STATE/"keywords.txt"
        keywords.write_text(" ".join(pieces)+"\n")
        return sherpa_onnx.KeywordSpotter(tokens=root.runtime_path(KWS+"/tokens.txt"),
            encoder=root.runtime_path(KWS+"/encoder-epoch-12-avg-2-chunk-16-left-64.onnx"),
            decoder=root.runtime_path(KWS+"/decoder-epoch-12-avg-2-chunk-16-left-64.onnx"),
            joiner=root.runtime_path(KWS+"/joiner-epoch-12-avg-2-chunk-16-left-64.onnx"),
            keywords_file=str(keywords),num_threads=1,keywords_threshold=0.25,provider="cpu")

    def transcribe_sync(self, samples):
        import sherpa_onnx
        root=bound_root(STATE/"storage.json")
        if self.recognizer is None:
            self.recognizer=sherpa_onnx.OfflineRecognizer.from_whisper(
                encoder=root.runtime_path(ASR+"/tiny.en-encoder.int8.onnx"),
                decoder=root.runtime_path(ASR+"/tiny.en-decoder.int8.onnx"),
                tokens=root.runtime_path(ASR+"/tiny.en-tokens.txt"),num_threads=2,provider="cpu")
        # Verify binding even when the model is already resident.
        fd=root._anchor()
        import os
        os.close(fd)
        stream=self.recognizer.create_stream()
        stream.accept_waveform(16000,samples)
        self.recognizer.decode_stream(stream)
        return stream.result.text.strip()

    async def transcribe(self,samples):
        async with self.lock:
            return await asyncio.to_thread(self.transcribe_sync,samples)

    def decode_wav(self,data):
        with wave.open(io.BytesIO(data),"rb") as f:
            if f.getnchannels()!=1 or f.getsampwidth()!=2 or f.getframerate()!=16000 or f.getnframes()>16000*25:
                raise ValueError("Expected at most 25 seconds of mono 16 kHz PCM16 WAV")
            return np.frombuffer(f.readframes(f.getnframes()),dtype="<i2").astype(np.float32)/32768

async def voice_session(ws, device, config, inference, speech, sessions):
    """Audio is ephemeral PCM; never saved. Mac/iPhone capture stays on device.

    Energy VAD provides bounded recording, not speaker identification or an echo
    canceller. Clients suppress microphone frames during local TTS.
    """
    from starlette.websockets import WebSocketDisconnect
    cfg=config["voice"]
    kws=None; stream=None; mode="muted"; chunks=[]; duration=0.0; quiet=0.0
    began=False; follow_until=0.0; task=None
    conversation="voice-"+device["id"]
    key=device["id"]
    sessions[key]="connected"

    async def send(event,**data):
        sessions[key]=data.get("status",event)
        await ws.send_json({"event":event,**data})

    async def reply(audio):
        nonlocal mode
        try:
            mode="busy"
            await send("status",status="Transcribing locally")
            started=time.perf_counter()
            text=await speech.transcribe(audio)
            asr_seconds=time.perf_counter()-started
            if not text:
                mode="listening";await send("status",status="No speech detected");return
            await send("transcript",text=text)
            await send("status",status="Thinking locally")
            result=await inference.respond(text,conversation,device)
            mode="speaking"
            await send("speak",text=result["text"],metrics={**result["metrics"],"asr_seconds":asr_seconds},tools=result["tools"])
        except asyncio.CancelledError:
            raise
        except Exception as e:
            mode="listening"
            await send("error",text=str(e)[:500])

    try:
        await send("status",status="Microphone connected; choose Wake or Push to talk")
        while True:
            packet=await ws.receive()
            if packet["type"]=="websocket.disconnect":break
            if packet.get("text"):
                command=json.loads(packet["text"])
                action=command.get("action")
                if action=="wake":
                    kws=await asyncio.to_thread(speech.kws,cfg["wake_phrase"])
                    stream=kws.create_stream();mode="listening"
                    await send("status",status="Listening for "+cfg["wake_phrase"])
                elif action=="ptt":
                    mode="recording";chunks=[];duration=quiet=0.;began=False
                    await send("status",status="Listening to your question")
                elif action in ("cancel","mute"):
                    if task and not task.done():task.cancel();await asyncio.gather(task,return_exceptions=True)
                    chunks=[];mode="muted" if action=="mute" else "listening"
                    await send("stop_speaking")
                    await send("status",status="Muted" if mode=="muted" else "Cancelled")
                elif action=="spoken_done":
                    mode="listening";follow_until=time.monotonic()+cfg["follow_up_seconds"]
                    await send("status",status="Follow-up listening")
                elif action=="finish" and mode=="recording":
                    if chunks and began:task=asyncio.create_task(reply(np.concatenate(chunks)))
                    else:mode="listening"
                continue
            data=packet.get("bytes")
            if not data or mode in ("muted","busy","speaking"):continue
            if len(data)>16000*4 or len(data)%4:raise ValueError("Invalid audio frame")
            samples=np.frombuffer(data,dtype="<f4")
            if not np.all(np.isfinite(samples)) or np.max(np.abs(samples),initial=0)>1.01:
                raise ValueError("Invalid audio sample")
            seconds=len(samples)/16000
            energy=float(np.sqrt(np.mean(samples*samples))) if len(samples) else 0
            if mode=="listening":
                if time.monotonic()<follow_until and energy>cfg["energy_threshold"]:
                    mode="recording";chunks=[];duration=quiet=0.;began=False
                elif kws:
                    stream.accept_waveform(16000,samples)
                    while kws.is_ready(stream):
                        kws.decode_stream(stream)
                        if kws.get_result(stream):
                            kws.reset_stream(stream);mode="awaiting_ack"
                            await send("ack",text="Yes?")
                            break
                    continue
                else:continue
            if mode=="awaiting_ack":continue
            if mode=="recording":
                chunks.append(samples.copy());duration+=seconds
                if energy>cfg["energy_threshold"]:began=True;quiet=0
                else:quiet+=seconds
                if (began and quiet>=cfg["silence_seconds"]) or duration>=cfg["max_record_seconds"]:
                    if began:task=asyncio.create_task(reply(np.concatenate(chunks)));mode="busy"
                    else:mode="listening";await send("status",status="No speech detected")
                    chunks=[]
    except (WebSocketDisconnect,RuntimeError):pass
    finally:
        if task and not task.done():task.cancel();await asyncio.gather(task,return_exceptions=True)
        sessions.pop(key,None)
