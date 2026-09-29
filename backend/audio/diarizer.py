import numpy as np
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import logging

try:
    import torch
    TORCH_AVAILABLE = True
except Exception:
    torch = None
    TORCH_AVAILABLE = False

try:
    from pyannote.audio import Pipeline
    from pyannote.core import Segment
    PYANNOTE_AVAILABLE = True
except Exception:  # pyannote.audio 是可选重型依赖
    Pipeline = None
    Segment = None
    PYANNOTE_AVAILABLE = False

logger = logging.getLogger(__name__)


class SpeakerDiarizer:
    """使用pyannote.audio进行说话人分离，区分产研双方（农业专家和企业家）"""

    def __init__(self, auth_token: str, use_auth_token: bool = True):
        self.auth_token = auth_token
        self.use_auth_token = use_auth_token
        self.pipeline = None
        self.device = None

    def _ensure_pipeline(self):
        """惰性加载 pyannote 流水线；未安装时给出确定性错误。"""
        if not PYANNOTE_AVAILABLE:
            raise RuntimeError("pyannote.audio 未安装，说话人分离不可用（离线环境请勿调用）")
        if self.pipeline is None:
            logger.info("初始化pyannote说话人分离模型...")
            self.pipeline = Pipeline.from_pretrained(
                "pyannote/speaker-diarization-3.1",
                use_auth_token=self.auth_token
            )
            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
            if torch.cuda.is_available():
                self.pipeline.to(self.device)
            logger.info(f"模型加载完成，使用设备: {self.device}")
        return self.pipeline

    def diarize(self, audio_path: str, num_speakers: int = None) -> List[Dict]:
        """
        对音频进行说话人分离
        返回每个说话人的时间段列表
        """
        logger.info(f"开始说话人分离: {audio_path}")

        diarization = self._ensure_pipeline()(audio_path, num_speakers=num_speakers)

        segments = []
        for segment, _, speaker in diarization.itertracks(yield_label=True):
            segments.append({
                "speaker": speaker,
                "start": segment.start,
                "end": segment.end,
                "duration": segment.end - segment.start
            })

        logger.info(f"说话人分离完成，检测到 {len(set(s['speaker'] for s in segments))} 个说话人")
        return segments

    def merge_with_transcript(
        self,
        diarization_segments: List[Dict],
        transcript_segments: List[Dict]
    ) -> List[Dict]:
        """
        将说话人分离结果与转录文本合并
        为每个转录片段分配说话人标签
        """
        merged = []

        for trans_seg in transcript_segments:
            trans_start = trans_seg["start"]
            trans_end = trans_seg["end"]
            trans_mid = (trans_start + trans_end) / 2

            best_speaker = None
            best_overlap = 0

            for dia_seg in diarization_segments:
                overlap_start = max(trans_start, dia_seg["start"])
                overlap_end = min(trans_end, dia_seg["end"])
                overlap = max(0, overlap_end - overlap_start)

                if overlap > best_overlap:
                    best_overlap = overlap
                    best_speaker = dia_seg["speaker"]

            if best_speaker is None:
                for dia_seg in diarization_segments:
                    if dia_seg["start"] <= trans_mid <= dia_seg["end"]:
                        best_speaker = dia_seg["speaker"]
                        break

            if best_speaker is None and diarization_segments:
                closest = min(
                    diarization_segments,
                    key=lambda s: min(abs(s["start"] - trans_mid), abs(s["end"] - trans_mid))
                )
                best_speaker = closest["speaker"]

            merged.append({
                **trans_seg,
                "speaker": best_speaker or "SPEAKER_00"
            })

        return merged

    def identify_roles(
        self,
        merged_segments: List[Dict],
        role_keywords: Dict[str, List[str]] = None
    ) -> Dict[str, str]:
        """
        根据对话内容识别说话人角色
        区分农业专家（研发方）和企业家（产业方）
        """
        if role_keywords is None:
            role_keywords = {
                "expert": [
                    "研究", "实验", "数据", "论文", "实验室", "技术", "蛋白含量",
                    "营养", "成分", "菌株", "基因", "分子", "饲料配方", "转化率",
                    "养殖技术", "环境参数", "温度", "湿度", "密度", "周期"
                ],
                "entrepreneur": [
                    "市场", "投资", "成本", "利润", "产能", "规模化", "销售",
                    "渠道", "品牌", "法规", "政策", "审批", "资质", "供应链",
                    "物流", "包装", "定价", "竞争", "商业模式", "融资"
                ]
            }

        speaker_texts = {}
        for seg in merged_segments:
            speaker = seg["speaker"]
            if speaker not in speaker_texts:
                speaker_texts[speaker] = []
            speaker_texts[speaker].append(seg["text"])

        speaker_roles = {}
        for speaker, texts in speaker_texts.items():
            full_text = " ".join(texts)
            expert_score = sum(1 for kw in role_keywords["expert"] if kw in full_text)
            entrepreneur_score = sum(1 for kw in role_keywords["entrepreneur"] if kw in full_text)

            if expert_score > entrepreneur_score:
                role = "expert"
            elif entrepreneur_score > expert_score:
                role = "entrepreneur"
            else:
                role = "expert" if len(speaker_roles) == 0 else "entrepreneur"

            speaker_roles[speaker] = role

        logger.info(f"说话人角色识别结果: {speaker_roles}")
        return speaker_roles

    def format_dialogue(self, merged_segments: List[Dict], speaker_roles: Dict[str, str]) -> str:
        """
        将对话格式化为带角色标记的文本
        """
        role_names = {
            "expert": "【农业专家】",
            "entrepreneur": "【企业家】"
        }

        dialogue_lines = []
        for seg in merged_segments:
            speaker = seg["speaker"]
            role = speaker_roles.get(speaker, "expert")
            role_label = role_names.get(role, "【未知】")
            timestamp = f"[{self._format_time(seg['start'])} - {self._format_time(seg['end'])}]"
            dialogue_lines.append(f"{timestamp} {role_label}: {seg['text']}")

        return "\n".join(dialogue_lines)

    @staticmethod
    def _format_time(seconds: float) -> str:
        """将秒数格式化为 MM:SS"""
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes:02d}:{secs:02d}"
