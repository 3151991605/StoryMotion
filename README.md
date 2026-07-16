# StoryMotion

> AI 漫剧智能体平台 —— 用户输入一句创意，AI 多 Agent 自动完成 *世界观 → 人物 → 故事 → 漫剧脚本 → 分镜 → 视频 Prompt* 的完整流水线。

## 项目目标

- 输入：故事灵感（类型 / 风格 / 主角 / 脑洞 / 时长）。
- 输出：世界观、人物卡、短篇故事、漫剧剧本、分镜、视频 Prompt，以及一个生成的视频。
- 范围：两周内课程级 Demo。MVP 链路：

  ```
  灵感 → StoryPackage → ScreenplayPackage → ShotPackage → Mock Video
  ```

## 技术栈

- Python 3.11
- FastAPI / LangGraph / LangChain / Pydantic
- Streamlit（Demo UI）
- PenShot（Screenplay → Storyboard，通过 Adapter 接入）
- FFmpeg（视频合成）

## 目录结构

```
StoryMotion/
├── src/storymotion/        # 主项目代码
│   ├── adapters/           # 第三方适配器（如 penshot_adapter）
│   ├── models/             # Pydantic 数据协议
│   ├── providers/          # LLM / 视频 Provider（mock + minimax + penshot sidecar + rule）
│   ├── services/           # 业务装配层（screenplay_assembler / story_assembler / demo_pipeline）
│   └── ui/                 # Streamlit ViewModel
├── scripts/                # 一次性验证脚本（verify_*.py / render_mock_video.py）
├── tests/                  # pytest 单元 / 探针测试
├── docs/
│   ├── adr/                # 架构决策记录
│   ├── plans/              # 设计 / 实施方案
│   └── research/           # 开源参考评审
├── external/
│   ├── novelwriter/        # 第三方源码（参考用）
│   └── penshot/            # 第三方源码（参考用）
├── data/                   # 探针 / 临时输出
├── logs/                   # 运行时日志
├── .streamlit/             # Streamlit 配置
├── pyproject.toml          # 项目元数据
├── streamlit_app.py        # Streamlit Demo 入口
├── 交接手册.md              # Codex 工作交接手册
└── 方案确定.md              # 项目方案与决策记录
```

## 快速开始

```bash
# 安装依赖
pip install -e .

# 启动 Streamlit Demo
streamlit run streamlit_app.py

# 运行测试
pytest -q
```

环境变量：复制 `.env.example` 为 `.env` 并填入对应 Provider 的 API Key（见 `docs/plans/` 中各 Provider 方案）。

## 架构概览

```
用户创意
   ↓
Requirement Agent → World Builder → Character → Plot → Writer → Reviewer
   ↓
StoryPackage
   ↓
Screenplay Adapter
   ↓
ScreenplayPackage
   ↓
PenShot Adapter (penshot_sidecar / rule_shot_provider)
   ↓
ShotPackage
   ↓
Video Provider (mock / minimax)
   ↓
MP4
```

详细架构与决策见 [`docs/adr/`](docs/adr/) 与 [`docs/plans/`](docs/plans/)。

## 参考开源项目

- [NovelWriter](https://github.com/EdwardAThomson/NovelWriter) —— 故事生成与 Agent 组织参考
- [PenShot](https://github.com/neopen/story-shot-agent) —— Screenplay → Storyboard 模块参考

两者均以 `external/` 下源码形式本地保存，便于离线查阅与版本固定。

## 许可证

本仓库主项目代码待定。`external/penshot/` 与 `external/novelwriter/` 子目录保留各自上游许可证（参见各子目录 LICENSE / README）。