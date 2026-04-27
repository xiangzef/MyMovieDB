"""
================================================================================
日语语音提取翻译模块 - 从视频中提取日语语音并翻译成中文
================================================================================
文件路径: F:\\github\\MyMovieDB\\backend\\translator.py
功能说明:
    1. 从视频文件中提取音频
    2. 使用 Faster-Whisper 进行日语语音识别
    3. 使用 deep-translator 翻译日文到中文
依赖库:
    - faster-whisper: CTranslate2 优化的 Whisper（推荐，比原版快4倍）
    - deep-translator: 翻译引擎（Google/DeepL）
    - ffmpeg: 音频提取
================================================================================
"""

import os
import subprocess
import tempfile
import logging
from pathlib import Path
from typing import Optional, List, Dict
import re

logger = logging.getLogger(__name__)

# 优先使用 faster-whisper（已安装），回退到 openai-whisper
WHISPER_AVAILABLE = False
FASTER_WHISPER_AVAILABLE = False

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

try:
    from deep_translator import GoogleTranslator
    TRANSLATOR_AVAILABLE = True
except ImportError:
    TRANSLATOR_AVAILABLE = False
    logger.warning("deep-translator 未安装，翻译功能不可用")


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
        self.translator = None
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

    def _load_translator(self):
        """加载翻译器（延迟加载）"""
        if not TRANSLATOR_AVAILABLE:
            raise RuntimeError("deep-translator 未安装，请运行: py -3.14 -m pip install deep-translator")

        if self.translator is None:
            self.translator = GoogleTranslator(source='ja', target='zh-CN')

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

    def transcribe_audio(self, audio_path: str, language: str = "ja") -> Dict:
        """
        使用 Whisper 转录音频

        Args:
            audio_path: 音频文件路径
            language: 音频语言代码，默认日语 (ja)

        Returns:
            Dict: 包含 'text', 'segments' 的转录结果
        """
        self._load_whisper_model()

        logger.info(f"正在转录音频: {audio_path}")

        if self.use_faster:
            # Faster-Whisper API
            segments, info = self.model.transcribe(
                audio_path,
                language=language,
                beam_size=5,
                vad_filter=True
            )
            segments_list = []
            for seg in segments:
                segments_list.append({
                    'start': seg.start,
                    'end': seg.end,
                    'text': seg.text.strip()
                })
            return {
                'text': ' '.join(s['text'] for s in segments_list),
                'segments': segments_list
            }
        else:
            # 原版 Whisper API
            result = self.model.transcribe(audio_path, language=language)
            return {
                'text': result['text'].strip(),
                'segments': [
                    {
                        'start': seg['start'],
                        'end': seg['end'],
                        'text': seg['text'].strip()
                    }
                    for seg in result.get('segments', [])
                ]
            }

    def translate_text(self, japanese_text: str) -> str:
        """
        翻译日文文本到中文

        Args:
            japanese_text: 日文文本

        Returns:
            str: 中文翻译结果
        """
        if not japanese_text or not japanese_text.strip():
            return ""

        self._load_translator()

        try:
            result = self.translator.translate(japanese_text)
            return result
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
            'error': None
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            audio_path = os.path.join(temp_dir, "audio.wav")

            logger.info(f"开始处理视频: {video_path}")

            extract_success = self._extract_audio(video_path, audio_path)

            if not extract_success:
                result['error'] = "音频提取失败，请确保已安装 ffmpeg"
                return result

            try:
                transcription = self.transcribe_audio(audio_path)
                result['original_text'] = transcription['text']
                result['segments'] = transcription['segments']

                if translate and transcription['text']:
                    result['translated_text'] = self.translate_text(transcription['text'])

                    translated_segments = self.translate_segments(transcription['segments'])
                    for i, seg in enumerate(translated_segments):
                        result['segments'][i]['chinese'] = seg['chinese']

                result['success'] = True
                logger.info(f"视频处理完成，识别文字长度: {len(result['original_text'])}")

            except Exception as e:
                result['error'] = str(e)
                logger.error(f"视频处理失败: {str(e)}")

        return result


def format_time(seconds: float) -> str:
    """将秒数转换为时间戳格式 HH:MM:SS"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


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