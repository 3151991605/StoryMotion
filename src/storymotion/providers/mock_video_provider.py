from __future__ import annotations

import subprocess
from pathlib import Path

from storymotion.models import ShotPackage


MOCK_COLORS = (
    "0x111827",
    "0x172554",
    "0x312e81",
    "0x4c1d95",
    "0x581c87",
    "0x3b0764",
)


def _ass_time(seconds: float) -> str:
    centiseconds = round(seconds * 100)
    hours, remainder = divmod(centiseconds, 360000)
    minutes, remainder = divmod(remainder, 6000)
    whole_seconds, centiseconds = divmod(remainder, 100)
    return f"{hours}:{minutes:02d}:{whole_seconds:02d}.{centiseconds:02d}"


def _escape_ass(text: str) -> str:
    return text.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}")


def _wrap_ass(text: str, width: int = 20) -> str:
    compact = " ".join(text.split())
    return "\\N".join(
        compact[index : index + width]
        for index in range(0, len(compact), width)
    )


class MockVideoProvider:
    def __init__(
        self,
        *,
        ffmpeg_path: Path,
        width: int = 720,
        height: int = 1280,
        frame_rate: int = 24,
    ) -> None:
        self.ffmpeg_path = Path(ffmpeg_path)
        self.width = width
        self.height = height
        self.frame_rate = frame_rate

    def build_ass_timeline(self, package: ShotPackage) -> str:
        header = """[Script Info]
ScriptType: v4.00+
PlayResX: 720
PlayResY: 1280
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Microsoft YaHei,34,&H00FFFFFF,&H000000FF,&H00101010,&H88000000,-1,0,0,0,100,100,1,0,1,3,1,2,48,48,120,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
        events: list[str] = []
        elapsed = 0.0
        shot_count = len(package.shots)
        for index, shot in enumerate(package.shots, start=1):
            start = elapsed
            end = elapsed + shot.duration
            visual = _wrap_ass(_escape_ass(shot.visual_description[:100]))
            text = (
                f"{{\\an8\\fs40}}{_escape_ass(package.title)}\\N"
                f"{{\\an8\\fs30}}SHOT {index}/{shot_count} · {shot.scene_id} · "
                f"{shot.duration:g}s\\N{shot.shot_type} · {shot.camera_movement}"
                f"\\N\\N{{\\an2\\fs32}}{visual}"
            )
            events.append(
                f"Dialogue: 0,{_ass_time(start)},{_ass_time(end)},Default,,0,0,0,,{text}"
            )
            elapsed = end
        return header + "\n".join(events) + "\n"

    def build_ffmpeg_command(
        self,
        package: ShotPackage,
        *,
        ass_file: Path,
        output_file: Path,
    ) -> list[str]:
        command = [str(self.ffmpeg_path), "-y", "-hide_banner"]
        filter_parts: list[str] = []
        video_labels: list[str] = []
        for index, shot in enumerate(package.shots):
            color = MOCK_COLORS[index % len(MOCK_COLORS)]
            command.extend(
                [
                    "-f",
                    "lavfi",
                    "-i",
                    f"color=c={color}:s={self.width}x{self.height}:r={self.frame_rate}:d={shot.duration:g}",
                ]
            )
            fade_out_start = max(0.0, shot.duration - 0.25)
            filter_parts.append(
                f"[{index}:v]format=yuv420p,"
                f"fade=t=in:st=0:d=0.25,"
                f"fade=t=out:st={fade_out_start:g}:d=0.25[v{index}]"
            )
            video_labels.append(f"[v{index}]")

        audio_input_index = len(package.shots)
        command.extend(
            [
                "-f",
                "lavfi",
                "-t",
                f"{package.target_duration:g}",
                "-i",
                "anullsrc=channel_layout=stereo:sample_rate=48000",
            ]
        )
        filter_parts.append(
            f"{''.join(video_labels)}concat=n={len(package.shots)}:v=1:a=0[base]"
        )
        filter_parts.append(f"[base]ass={ass_file.name}[video]")
        command.extend(
            [
                "-filter_complex",
                ";".join(filter_parts),
                "-map",
                "[video]",
                "-map",
                f"{audio_input_index}:a",
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-crf",
                "23",
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "aac",
                "-b:a",
                "96k",
                "-shortest",
                "-movflags",
                "+faststart",
                str(output_file),
            ]
        )
        return command

    def render(
        self,
        package: ShotPackage,
        *,
        output_file: Path,
    ) -> Path:
        output_file = output_file.resolve()
        output_file.parent.mkdir(parents=True, exist_ok=True)
        ass_file = output_file.parent / "timeline.ass"
        ass_file.write_text(self.build_ass_timeline(package), encoding="utf-8")
        command = self.build_ffmpeg_command(
            package, ass_file=ass_file, output_file=output_file
        )
        completed = subprocess.run(
            command,
            cwd=output_file.parent,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        if completed.returncode != 0:
            raise RuntimeError(
                "FFmpeg mock render failed: " + completed.stderr[-2000:]
            )
        return output_file
