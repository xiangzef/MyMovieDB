"""
================================================================================
日语语音提取翻译模块 - 从视频中提取日语语音并翻译成中文
================================================================================
文件路径: F:\\github\\MyMovieDB\\backend\\translator.py
功能说明:
    1. 从视频文件中提取音频（持久化存储，不自动删除）
    2. 使用 Faster-Whisper 进行日语语音识别（带时间戳）
      - 若 Whisper 不可用或下载模型失败，回退使用 Vosk 日语模型
    3. 使用 Ollama 本地模型翻译日文到中文
    4. 生成带时间戳的 SRT 字幕文件
    5. 音频仅在 SRT 成功生成后才删除
================================================================================
"""

import os
import subprocess
import logging
import urllib.request
from pathlib import Path
from typing import Optional, List, Dict
import json

logger = logging.getLogger(__name__)

# 组件可用性状态
WHISPER_AVAILABLE = False
FASTER_WHISPER_AVAILABLE = False
VOSK_AVAILABLE = False
TRANSLATOR_AVAILABLE = True  # Ollama 模式，代码加载即认为可用

try:
    from faster_whisper import WhisperModel
    FASTER_WHISPER_AVAILABLE = True
    WHISPER_AVAILABLE = True
    logger.info("使用 Faster-Whisper (CTranslate2 优化版)")
except ImportError:
    try:
        import whisper
        WHISPER_AVAILABLE = True
        FASTER_WHISPER_AVAILABLE = False
        logger.info("使用 OpenAI Whisper (原版)")
    except ImportError:
        WHISPER_AVAILABLE = False
        logger.warning("Whisper 未安装，语音识别功能不可用")

# 检查 Vosk（用于 Whisper 不可用时的备选）
try:
    import vosk
    # 检查模型是否存在
    VOSK_MODEL_PATH = r"C:\vosk-model-ja-0.22"
    if os.path.exists(VOSK_MODEL_PATH):
        VOSK_AVAILABLE = True
        logger.info(f"Vosk 日语模型可用: {VOSK_MODEL_PATH}")
    else:
        logger.warning(f"Vosk 模型不存在: {VOSK_MODEL_PATH}")
except ImportError:
    logger.warning("Vosk 未安装")


class JapaneseVideoTranslator:
    """日语视频语音提取翻译器"""

    def __init__(self, model_size: str = "base"):
        """
        初始化翻译器

        Args:
            model_size: Whisper 模型大小，可选: tiny, base, small, medium, large
                       模型越大识别越准确，但占用资源越多、速度越慢
        """
        self.model_size = model_size
        self.model = None
        self.ollama_translator = None
        self.use_faster = FASTER_WHISPER_AVAILABLE

    def _load_whisper_model(self):
        """加载 Whisper 模型（延迟加载）"""
        if not WHISPER_AVAILABLE:
            raise RuntimeError("Whisper 未安装，请运行: py -3.14 -m pip install faster-whisper")

        if self.model is None:
            logger.info(f"正在加载 Whisper {self.model_size} 模型...")
            if self.use_faster:
                # Faster-Whisper: 使用 CPU int8 量化，速度快内存占用低
                self.model = WhisperModel(
                    self.model_size,
                    device="cpu",
                    compute_type="int8"
                )
            else:
                # 原版 Whisper
                import whisper
                self.model = whisper.load_model(self.model_size)
            logger.info("Whisper 模型加载完成")

    def _translate_with_ollama(self, text: str) -> str:
        """使用 Ollama qwen2.5:7b 翻译日文到中文"""
        import json

        prompt = f"""你是一个专业的日语翻译。请将下面的日语翻译成中文，只输出翻译结果，不要解释。

日语：{text}

中文："""

        req_data = {
            "model": "qwen2.5:7b",
            "prompt": prompt,
            "stream": False
        }

        try:
            req = urllib.request.Request(
                "http://localhost:11434/api/generate",
                data=json.dumps(req_data).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=120) as response:
                result = json.loads(response.read().decode("utf-8"))
                return result.get("response", "").strip()
        except Exception as e:
            logger.error(f"Ollama 翻译失败: {e}")
            return text

    def _extract_audio(self, video_path: str, audio_path: str) -> bool:
        """
        使用 ffmpeg 从视频中提取音频

        Args:
            video_path: 视频文件路径
            audio_path: 输出音频文件路径

        Returns:
            bool: 提取是否成功
        """
        try:
            cmd = [
                'ffmpeg', '-y', '-i', video_path,
                '-vn', '-acodec', 'pcm_s16le', '-ar', '16000', '-ac', '1',
                audio_path
            ]
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=600
            )
            if result.returncode != 0:
                logger.error(f"FFmpeg 音频提取失败: {result.stderr}")
                return False
            return True
        except subprocess.TimeoutExpired:
            logger.error("FFmpeg 执行超时")
            return False
        except FileNotFoundError:
            logger.error("未找到 ffmpeg，请安装 ffmpeg 并将其添加到 PATH")
            return False
        except Exception as e:
            logger.error(f"音频提取失败: {str(e)}")
            return False

    def _transcribe_with_vosk(self, audio_path: str) -> Dict:
        """使用 Vosk 日语模型转录（Whisper 不可用时的备选方案）"""
        import vosk
        import wave

        # 转换为 16kHz mono PCM
        pcm_path = audio_path + ".pcm"
        try:
            cmd = [
                'ffmpeg', '-y', '-i', audio_path,
                '-ar', '16000', '-ac', '1', '-acodec', 'pcm_s16le',
                '-f', 's16le', pcm_path
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            if result.returncode != 0:
                raise RuntimeError(f"音频转换失败: {result.stderr}")
        except Exception as e:
            raise RuntimeError(f"Vosk 音频转换失败: {e}")

        # 加载模型并转录
        model_path = r"C:\vosk-model-ja-0.22"
        model = vosk.Model(model_path)
        recognizer = vosk.KaldiRecognizer(model, 16000)

        with open(pcm_path, "rb") as f:
            while True:
                data = f.read(2000)
                if not data:
                    break
                recognizer.AcceptWaveform(data)

        result_json = recognizer.FinalResult()
        result_dict = json.loads(result_json)

        # 清理临时文件
        try:
            os.remove(pcm_path)
        except:
            pass

        text = result_dict.get("text", "").strip()
        logger.info(f"Vosk 转录完成，识别文字: {len(text)} 字符")

        # Vosk 不提供时间戳，返回空 segments
        return {
            'text': text,
            'segments': []
        }

    def transcribe_audio(self, audio_path: str, language: str = "ja") -> Dict:
        """
        使用 Faster-Whisper 转录音频（带时间戳）
        若 Whisper 不可用或失败，回退使用 Vosk 日语模型

        Args:
            audio_path: 音频文件路径
            language: 音频语言代码，默认日语 (ja)

        Returns:
            Dict: 包含 'text', 'segments' 的转录结果，每个 segment 有 start/end/text
        """
        # 优先尝试 Whisper
        if WHISPER_AVAILABLE:
            try:
                self._load_whisper_model()
                logger.info(f"正在用 Faster-Whisper 转录音频: {audio_path}")

                segments, info = self.model.transcribe(
                    audio_path,
                    language=language,
                    vad_filter=True,
                    vad_min_silence_duration_ms=500
                )

                segment_list = []
                full_text = []

                for seg in segments:
                    seg_text = seg.text.strip()
                    if seg_text:
                        full_text.append(seg_text)
                        segment_list.append({
                            'start': round(seg.start, 2),
                            'end': round(seg.end, 2),
                            'text': seg_text
                        })

                result_text = ' '.join(full_text)
                logger.info(f"转录完成，识别文字: {len(result_text)} 字符，片段数: {len(segment_list)}")

                return {
                    'text': result_text,
                    'segments': segment_list
                }
            except Exception as e:
                logger.warning(f"Faster-Whisper 转录失败，回退到 Vosk: {e}")

        # Whisper 不可用或失败，使用 Vosk
        if VOSK_AVAILABLE:
            logger.info("使用 Vosk 日语模型转录")
            return self._transcribe_with_vosk(audio_path)

        # 两者都不可用
        raise RuntimeError("Whisper 和 Vosk 都不可用，无法进行语音识别")

    def translate_text(self, japanese_text: str) -> str:
        """
        翻译日文文本到中文（使用 Ollama 本地模型）

        Args:
            japanese_text: 日文文本

        Returns:
            str: 中文翻译结果
        """
        if not japanese_text or not japanese_text.strip():
            return ""

        try:
            return self._translate_with_ollama(japanese_text)
        except Exception as e:
            logger.error(f"翻译失败: {str(e)}")
            return japanese_text

    def translate_segments(self, segments: List[Dict]) -> List[Dict]:
        """
        翻译转录片段

        Args:
            segments: 转录片段列表，每个包含 'start', 'end', 'text'

        Returns:
            List[Dict]: 翻译后的片段列表
        """
        if not segments:
            return []

        translated_segments = []
        for seg in segments:
            japanese_text = seg.get('text', '')
            chinese_text = self.translate_text(japanese_text)
            translated_segments.append({
                'start': seg['start'],
                'end': seg['end'],
                'japanese': japanese_text,
                'chinese': chinese_text
            })

        return translated_segments

    def process_video(self, video_path: str, translate: bool = True) -> Dict:
        """
        处理视频：提取音频 -> 语音识别 -> 翻译
        注意：音频文件持久化存储，除非明确调用 delete_audio() 否则不删除

        Args:
            video_path: 视频文件路径
            translate: 是否翻译成中文

        Returns:
            Dict: 处理结果，包含原始日语和中文翻译
        """
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"视频文件不存在: {video_path}")

        result = {
            'video_path': video_path,
            'success': False,
            'original_text': '',
            'translated_text': '',
            'segments': [],
            'audio_path': None,
            'srt_path': None,
            'error': None
        }

        video_dir = os.path.dirname(video_path)
        video_name = os.path.splitext(os.path.basename(video_path))[0]
        audio_path = os.path.join(video_dir, f"{video_name}_audio.wav")
        result['audio_path'] = audio_path

        logger.info(f"开始处理视频: {video_path}")

        # 步骤1：提取音频（持久化存储）
        if not os.path.exists(audio_path):
            logger.info(f"音频文件不存在，正在提取...")
            extract_success = self._extract_audio(video_path, audio_path)
            if not extract_success:
                result['error'] = "音频提取失败，请确保已安装 ffmpeg"
                return result
            logger.info(f"音频已提取: {audio_path}")
        else:
            logger.info(f"使用已有音频: {audio_path}")

        # 步骤2：语音转文字（带时间戳）
        try:
            transcription = self.transcribe_audio(audio_path)
            result['original_text'] = transcription['text']
            result['segments'] = transcription['segments']
        except Exception as e:
            result['error'] = f"语音识别失败: {str(e)}"
            logger.error(result['error'])
            return result

        # 步骤3：翻译
        if translate and transcription['text']:
            try:
                result['translated_text'] = self.translate_text(transcription['text'])

                # 翻译每个片段
                translated_segments = self.translate_segments(transcription['segments'])
                for i, seg in enumerate(translated_segments):
                    if i < len(result['segments']):
                        result['segments'][i]['chinese'] = seg['chinese']
            except Exception as e:
                result['error'] = f"翻译失败: {str(e)}"
                logger.error(result['error'])
                return result

        result['success'] = True
        logger.info(f"视频处理完成，识别文字长度: {len(result['original_text'])}")

        return result

    def get_audio_path(self, video_path: str) -> str:
        """获取音频文件路径（不提取，只计算路径）"""
        video_dir = os.path.dirname(video_path)
        video_name = os.path.splitext(os.path.basename(video_path))[0]
        return os.path.join(video_dir, f"{video_name}_audio.wav")

    def delete_audio(self, video_path: str) -> bool:
        """删除视频对应的音频文件"""
        audio_path = self.get_audio_path(video_path)
        try:
            if os.path.exists(audio_path):
                os.remove(audio_path)
                logger.info(f"已删除音频: {audio_path}")
                return True
            return False
        except Exception as e:
            logger.error(f"删除音频失败: {e}")
            return False


def format_time(seconds: float) -> str:
    """将秒数转换为 SRT 时间戳格式 HH:MM:SS,mmm"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def generate_srt(segments: List[Dict], output_path: str) -> bool:
    """
    生成 SRT 字幕文件

    Args:
        segments: 片段列表，每个包含 start, end, text, chinese
        output_path: 输出 SRT 文件路径

    Returns:
        bool: 是否成功
    """
    if not segments:
        return False

    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            for i, seg in enumerate(segments):
                text = seg.get('text', seg.get('japanese', '')).strip()
                if not text:
                    continue
                chinese = seg.get('chinese', '')
                f.write(f"{i+1}\n")
                f.write(f"{format_time(seg['start'])} --> {format_time(seg['end'])}\n")
                if chinese:
                    f.write(f"{text}\n{chinese}\n\n")
                else:
                    f.write(f"{text}\n\n")
        return True
    except Exception as e:
        logger.error(f"生成 SRT 失败: {e}")
        return False


def format_transcript(segments: List[Dict], include_translation: bool = True) -> str:
    """
    格式化转录文本为带时间戳的格式

    Args:
        segments: 转录片段列表
        include_translation: 是否包含中文翻译

    Returns:
        str: 格式化后的文本
    """
    lines = []
    for seg in segments:
        start = format_time(seg['start'])
        end = format_time(seg['end'])
        japanese = seg.get('japanese', seg.get('text', ''))
        chinese = seg.get('chinese', '')

        if include_translation and chinese:
            lines.append(f"[{start} -> {end}] {japanese}\n翻译: {chinese}\n")
        else:
            lines.append(f"[{start} -> {end}] {japanese}\n")

    return "".join(lines)


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("用法: python translator.py <视频文件路径>")
        sys.exit(1)

    video_path = sys.argv[1]

    translator = JapaneseVideoTranslator(model_size="base")

    print(f"正在处理视频: {video_path}")
    print("=" * 60)

    result = translator.process_video(video_path, translate=True)

    if result['success']:
        print("\n【原始日语】")
        print(result['original_text'])
        print("\n【中文翻译】")
        print(result['translated_text'])
        print("\n【逐段对照】")
        print(format_transcript(result['segments']))
    else:
        print(f"处理失败: {result['error']}")
