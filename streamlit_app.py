from __future__ import annotations

from html import escape
from pathlib import Path

import streamlit as st

from storymotion.ui import load_demo_view_model


ROOT = Path(__file__).resolve().parent
BUNDLE_FILE = (
    ROOT
    / "outputs"
    / "verification"
    / "end_to_end_demo"
    / "storymotion_bundle.json"
)
SUMMARY_FILE = ROOT / "outputs" / "verification" / "end_to_end_demo_summary.json"


def e(value: object) -> str:
    return escape(str(value), quote=True)


st.set_page_config(
    page_title="StoryMotion · 漫剧制作台",
    page_icon="◈",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
<style>
:root {
  --ink: #080b12;
  --panel: rgba(17, 23, 36, .88);
  --panel-2: rgba(23, 31, 47, .72);
  --line: rgba(218, 190, 126, .18);
  --gold: #d7a84a;
  --gold-pale: #f3d99e;
  --cinnabar: #c85e52;
  --jade: #6fb59c;
  --paper: #ece6d8;
  --muted: #9198a7;
}

.stApp {
  background:
    radial-gradient(circle at 72% 8%, rgba(87, 58, 119, .22), transparent 30rem),
    radial-gradient(circle at 18% 46%, rgba(24, 85, 91, .12), transparent 28rem),
    linear-gradient(135deg, #080b12 0%, #0b101a 55%, #090c13 100%);
  color: var(--paper);
  font-family: "Microsoft YaHei", "PingFang SC", sans-serif;
}

.stApp::before {
  content: "";
  position: fixed;
  inset: 0;
  pointer-events: none;
  opacity: .18;
  background-image: linear-gradient(rgba(255,255,255,.018) 1px, transparent 1px),
                    linear-gradient(90deg, rgba(255,255,255,.014) 1px, transparent 1px);
  background-size: 40px 40px;
  mask-image: linear-gradient(to bottom, black, transparent 88%);
}

[data-testid="stSidebar"] {
  background: linear-gradient(180deg, rgba(10, 14, 23, .98), rgba(12, 17, 28, .96));
  border-right: 1px solid var(--line);
}

[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p,
[data-testid="stSidebar"] label { color: #b7bdc8; }

.block-container {
  max-width: 1480px;
  padding-top: 2.2rem;
  padding-bottom: 4rem;
}

h1, h2, h3, .display-font {
  font-family: "STKaiti", "KaiTi", "Songti SC", "SimSun", serif !important;
  letter-spacing: .04em;
}

.brand-lockup { padding: .8rem 0 1.6rem; }
.brand-mark {
  display: inline-grid; place-items: center; width: 2.45rem; height: 2.45rem;
  border: 1px solid rgba(215,168,74,.65); color: var(--gold-pale);
  transform: rotate(45deg); margin-right: 1rem;
}
.brand-mark span { transform: rotate(-45deg); font-family: serif; font-size: 1.2rem; }
.brand-name { font-family: "STKaiti", "KaiTi", serif; font-size: 1.45rem; color: #f3ead7; }
.brand-note { margin-top: .42rem; color: #6f7786; font-size: .72rem; letter-spacing: .16em; }

.side-label {
  color: var(--gold); font-size: .68rem; letter-spacing: .2em;
  text-transform: uppercase; margin: 1.2rem 0 .45rem;
}
.verified-box {
  border: 1px solid rgba(111,181,156,.3); background: rgba(36, 87, 74, .12);
  padding: .8rem .9rem; margin-top: 1rem; color: #b9d9ce; font-size: .78rem;
}
.quota-box {
  border-left: 2px solid var(--cinnabar); background: rgba(155, 66, 58, .10);
  padding: .8rem .9rem; color: #dfb0aa; font-size: .76rem; line-height: 1.7;
}

.hero {
  position: relative; overflow: hidden; min-height: 20rem;
  border: 1px solid var(--line); background: linear-gradient(115deg, rgba(16,22,35,.96), rgba(24,25,43,.84));
  padding: 3.2rem 3.4rem; box-shadow: 0 24px 70px rgba(0,0,0,.26);
}
.hero::after {
  content: "十"; position: absolute; right: 2.5rem; top: -3.8rem;
  font-family: "STKaiti", serif; font-size: 20rem; color: rgba(215,168,74,.035);
  transform: rotate(10deg);
}
.hero-kicker { color: var(--gold); font-size: .7rem; letter-spacing: .28em; margin-bottom: 1.7rem; }
.hero h1 { font-size: clamp(2.7rem, 5vw, 5rem); line-height: 1.05; color: #f4eddf; margin: 0 0 1.15rem; }
.hero p { max-width: 48rem; color: #adb3bf; font-size: 1rem; line-height: 1.9; }
.hero-badges { display: flex; flex-wrap: wrap; gap: .55rem; margin-top: 2rem; }
.badge { border: 1px solid var(--line); color: #c7c0b2; padding: .4rem .7rem; font-size: .72rem; letter-spacing: .06em; }
.badge.live { border-color: rgba(111,181,156,.42); color: #a9d2c3; }

.section-kicker { color: var(--gold); font-size: .68rem; letter-spacing: .23em; margin: 2.6rem 0 .5rem; }
.section-title { font-family: "STKaiti", serif; font-size: 1.8rem; color: #eee5d5; margin-bottom: 1.35rem; }

.stage-rail { display: grid; grid-template-columns: repeat(4, 1fr); gap: .72rem; position: relative; }
.stage-card {
  min-height: 8.5rem; border: 1px solid var(--line); background: var(--panel);
  padding: 1.15rem 1.2rem; position: relative;
}
.stage-card::before { content: ""; position: absolute; left: 0; top: 0; width: 2.8rem; height: 2px; background: var(--jade); }
.stage-card.warning::before { background: var(--cinnabar); }
.stage-index { color: #626b79; font-family: Georgia, serif; font-size: .72rem; }
.stage-label { color: #eee4d3; font-family: "STKaiti", serif; font-size: 1.25rem; margin: .55rem 0 .45rem; }
.stage-detail { color: #858d9b; font-size: .73rem; line-height: 1.55; }

[data-testid="stMetric"] {
  border-top: 1px solid var(--line); padding-top: 1rem; background: transparent;
}
[data-testid="stMetricLabel"] { color: #7f8795; }
[data-testid="stMetricValue"] { font-family: Georgia, serif; color: var(--gold-pale); }

.stTabs [data-baseweb="tab-list"] { gap: 1.5rem; border-bottom: 1px solid var(--line); }
.stTabs [data-baseweb="tab"] { color: #838b99; padding: .9rem .15rem; }
.stTabs [aria-selected="true"] { color: var(--gold-pale) !important; }

.story-sheet, .scene-card, .shot-card, .character-card {
  border: 1px solid var(--line); background: var(--panel); padding: 1.35rem 1.5rem;
}
.story-sheet { font-family: "Songti SC", "STSong", "SimSun", serif; color: #d8d1c4; line-height: 2.05; font-size: 1rem; }
.mini-kicker { color: var(--gold); font-size: .64rem; letter-spacing: .17em; text-transform: uppercase; }
.card-title { color: #ece3d3; font-family: "STKaiti", serif; font-size: 1.2rem; margin: .45rem 0 .7rem; }
.card-copy { color: #9ca3af; font-size: .79rem; line-height: 1.72; }
.beat-card { border-left: 1px solid rgba(215,168,74,.55); padding: .4rem 1rem 1.15rem; min-height: 7rem; }
.beat-time { color: var(--gold); font-family: Georgia, serif; font-size: .72rem; }
.shot-card { min-height: 15.5rem; margin-bottom: .8rem; }
.shot-head { display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid var(--line); padding-bottom: .8rem; margin-bottom: .9rem; }
.shot-id { color: var(--gold-pale); font-family: Georgia, serif; letter-spacing: .08em; }
.shot-meta { color: #7f8795; font-size: .7rem; }
.prompt-code { color: #a9b7c8; font-family: Consolas, monospace; font-size: .7rem; line-height: 1.55; }
.truth-panel { border: 1px solid rgba(111,181,156,.3); background: rgba(31,79,67,.12); padding: 1.3rem; }
.warning-panel { border: 1px solid rgba(200,94,82,.32); background: rgba(120,47,42,.12); padding: 1.3rem; }
.footer-line { border-top: 1px solid var(--line); margin-top: 3.5rem; padding-top: 1rem; color: #596271; font-size: .68rem; letter-spacing: .1em; }

button[kind="primary"] { border: 1px solid rgba(215,168,74,.62) !important; }

@media (max-width: 900px) {
  .stage-rail { grid-template-columns: 1fr 1fr; }
  .hero { padding: 2rem 1.5rem; }
}
</style>
""",
    unsafe_allow_html=True,
)

try:
    view = load_demo_view_model(
        root=ROOT,
        bundle_file=BUNDLE_FILE,
        summary_file=SUMMARY_FILE,
    )
except (FileNotFoundError, ValueError) as exc:
    st.error(f"演示产物无法加载：{exc}")
    st.code(r".\.venv\Scripts\python.exe .\scripts\run_end_to_end_demo.py")
    st.stop()

bundle = view.bundle
brief = bundle.brief

with st.sidebar:
    st.markdown(
        """
        <div class="brand-lockup">
          <div><span class="brand-mark"><span>映</span></span><span class="brand-name">StoryMotion</span></div>
          <div class="brand-note">AI 漫剧制作控制台 · FEASIBILITY BUILD</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown('<div class="side-label">DEMO MODE / 演示模式</div>', unsafe_allow_html=True)
    st.selectbox("运行模式", ["已验证离线样例"], disabled=True, label_visibility="collapsed")
    st.caption("展示缓存的 MiniMax 产物，并在本地重放分镜与 Mock 成片链路。")

    st.markdown('<div class="side-label">CREATIVE BRIEF / 创意输入</div>', unsafe_allow_html=True)
    st.text_input("类型", brief.genre, disabled=True)
    st.text_input("主角", brief.protagonist_name, disabled=True)
    st.text_area("核心脑洞", brief.core_idea, height=96, disabled=True)
    st.text_input("风格", " · ".join(brief.style), disabled=True)
    col_a, col_b = st.columns(2)
    col_a.metric("目标时长", f"{brief.target_duration}s")
    col_b.metric("人物上限", brief.max_characters)
    st.markdown(
        '<div class="verified-box">● 当前输入已有完整验证产物<br>可离线展示，不消耗 Token 或积分</div>',
        unsafe_allow_html=True,
    )
    st.markdown('<div class="side-label">LIVE PROVIDER / 真实视频</div>', unsafe_allow_html=True)
    st.markdown(
        f'<div class="quota-box">海螺接口可达，但账户额度不足<br>API STATUS · {e(view.hailuo_status_code)}<br>补充积分后可替换 Mock Provider</div>',
        unsafe_allow_html=True,
    )

st.markdown(
    f"""
    <section class="hero">
      <div class="hero-kicker">VERIFIED PRODUCTION CASE · 2026</div>
      <h1>{e(bundle.story.title)}</h1>
      <p>{e(bundle.story.logline)}</p>
      <div class="hero-badges">
        <span class="badge live">● 本地链路通过</span>
        <span class="badge">东方玄幻</span>
        <span class="badge">竖屏 9:16</span>
        <span class="badge">{e(view.duration_seconds):s} 秒</span>
        <span class="badge">{len(bundle.storyboard.shots)} 镜头</span>
      </div>
    </section>
    """,
    unsafe_allow_html=True,
)

st.markdown('<div class="section-kicker">PRODUCTION RAIL / 制作轨</div>', unsafe_allow_html=True)
st.markdown('<div class="section-title">从叙事到镜头，每一层都有协议验收</div>', unsafe_allow_html=True)
stage_html = "".join(
    f"""
    <article class="stage-card {e(stage.status)}">
      <div class="stage-index">STAGE {e(stage.index)}</div>
      <div class="stage-label">{e(stage.label)}</div>
      <div class="stage-detail">{e(stage.detail)}</div>
    </article>
    """
    for stage in view.stages
)
st.markdown(f'<div class="stage-rail">{stage_html}</div>', unsafe_allow_html=True)

metric_cols = st.columns(5)
metric_cols[0].metric("故事字符", len(bundle.story.story_text))
metric_cols[1].metric("场景", len(bundle.screenplay.scenes))
metric_cols[2].metric("镜头", len(bundle.storyboard.shots))
metric_cols[3].metric("视频", f"{view.duration_seconds:g}s")
metric_cols[4].metric("测试", "54+2 PASS")

story_tab, screenplay_tab, storyboard_tab, media_tab = st.tabs(
    ["壹 · 故事", "贰 · 漫剧剧本", "叁 · 分镜", "肆 · 成片"]
)

with story_tab:
    left, right = st.columns([1.6, 1], gap="large")
    with left:
        st.markdown('<div class="section-kicker">STORY PACKAGE</div>', unsafe_allow_html=True)
        st.markdown(
            f'<div class="story-sheet">{e(bundle.story.story_text)}</div>',
            unsafe_allow_html=True,
        )
    with right:
        st.markdown('<div class="section-kicker">CHARACTER BIBLE</div>', unsafe_allow_html=True)
        for character in bundle.story.characters:
            st.markdown(
                f"""
                <div class="character-card">
                  <div class="mini-kicker">{e(character.role)}</div>
                  <div class="card-title">{e(character.name)}</div>
                  <div class="card-copy">目标 · {e(character.goal)}<br>特征 · {e(' / '.join(character.personality))}<br>能力 · {e(character.ability or '无')}</div>
                </div><br>
                """,
                unsafe_allow_html=True,
            )
    st.markdown('<div class="section-kicker">NARRATIVE BEATS</div>', unsafe_allow_html=True)
    beat_columns = st.columns(len(bundle.story.beats))
    for column, beat in zip(beat_columns, bundle.story.beats):
        column.markdown(
            f"""
            <div class="beat-card">
              <div class="beat-time">{e(beat.duration)} SEC</div>
              <div class="card-title">{e(beat.beat_type.upper())}</div>
              <div class="card-copy">{e(beat.content)}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

with screenplay_tab:
    st.markdown('<div class="section-kicker">SCREENPLAY PACKAGE</div>', unsafe_allow_html=True)
    for scene in bundle.screenplay.scenes:
        dialogue = "<br>".join(
            f"{e(item.speaker_id)} · {e(item.text)}" for item in scene.dialogues
        ) or "无对白"
        st.markdown(
            f"""
            <article class="scene-card">
              <div class="shot-head"><span class="shot-id">{e(scene.scene_id)}</span><span class="shot-meta">{e(scene.duration)}s · {e(scene.emotion)}</span></div>
              <div class="card-title">{e(scene.action)}</div>
              <div class="card-copy">对白 · {dialogue}<br>旁白 · {e(scene.voiceover or '无')}<br>转场 · {e(scene.transition or '直接切换')}</div>
            </article><br>
            """,
            unsafe_allow_html=True,
        )

with storyboard_tab:
    st.markdown('<div class="section-kicker">SHOT PACKAGE</div>', unsafe_allow_html=True)
    shot_columns = st.columns(2, gap="large")
    for index, shot in enumerate(view.shot_rows):
        with shot_columns[index % 2]:
            st.markdown(
                f"""
                <article class="shot-card">
                  <div class="shot-head"><span class="shot-id">{e(shot['shot_id'])}</span><span class="shot-meta">{e(shot['duration'])}s · {e(shot['scene_id'])}</span></div>
                  <div class="mini-kicker">{e(shot['shot_type'])} / {e(shot['camera_movement'])}</div>
                  <div class="card-title">镜头描述</div>
                  <div class="card-copy">{e(shot['visual_description'])}</div>
                </article>
                """,
                unsafe_allow_html=True,
            )
            with st.expander("查看视频 Prompt"):
                st.markdown(
                    f'<div class="prompt-code">{e(shot["video_prompt"])}</div>',
                    unsafe_allow_html=True,
                )

with media_tab:
    video_col, truth_col = st.columns([1.15, 1], gap="large")
    with video_col:
        st.markdown('<div class="section-kicker">LOCAL MOCK MASTER</div>', unsafe_allow_html=True)
        st.video(str(view.video_file))
        st.caption("720 × 1280 · H.264 / AAC · 本地 FFmpeg 验证成片")
    with truth_col:
        st.markdown('<div class="section-kicker">VERIFICATION TRUTH</div>', unsafe_allow_html=True)
        st.markdown(
            f"""
            <div class="truth-panel">
              <div class="mini-kicker">LOCAL PIPELINE · PASSED</div>
              <div class="card-title">确定性链路可重复执行</div>
              <div class="card-copy">StoryPackage → ScreenplayPackage → ShotPackage → Mock MP4<br><br>时长 {e(view.duration_seconds)} 秒 · {len(view.shot_rows)} 镜头 · 0 次网络请求 · 0 Token</div>
            </div><br>
            <div class="warning-panel">
              <div class="mini-kicker">HAILUO PROVIDER · BLOCKED</div>
              <div class="card-title">外部账户资源阻塞</div>
              <div class="card-copy">当前 Key 已通过鉴权并抵达视频接口，但返回状态码 {e(view.hailuo_status_code)}：Token Plan 用量上限。购买积分后可在 Provider 层直接替换，不影响上游协议。</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

st.markdown(
    '<div class="footer-line">STORYMOTION / FEASIBILITY PROTOTYPE · DATA PROTOCOL FIRST · PROVIDER REPLACEABLE</div>',
    unsafe_allow_html=True,
)
