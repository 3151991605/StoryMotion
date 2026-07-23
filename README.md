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
# 安装应用与开发依赖
pip install -e ".[ui,dev]"

# 配置文本模型（任意兼容 OpenAI Chat Completions 的服务）
copy .env.example .env
# 编辑 .env：至少填入 LLM_API_KEY 和 LLM_MODEL

# 启动 Streamlit Demo
streamlit run streamlit_app.py

# 运行测试
pytest -q
```

环境变量：复制 `.env.example` 为 `.env` 并填入对应 Provider 的 API Key（见 `docs/plans/` 中各 Provider 方案）。

### 交互式创作

启动页面后，填写“一句需求”、题材、主角和时长，StoryMotion 会调用配置的文本模型生成小说和漫剧剧本；每一层会经过 Pydantic 协议校验，再由内置规则分镜器生成逐镜图像/视频 Prompt。完整制作包可直接下载为 JSON。

文本生成环境变量：

```dotenv
LLM_API_KEY=你的文本模型密钥
LLM_API_BASE=https://api.openai.com/v1
LLM_MODEL=gpt-4o-mini
```

如果仅填写 `MINIMAX_API_KEY`，页面会自动使用 `https://api.minimaxi.com/v1` 与 `MiniMax-M2.7` 作为文本模型，无需重复填写 `LLM_*`。已有的 MiniMax / Hailuo 变量继续用于图片和真实视频任务。真实视频仍需要视频账户的单独额度；没有额度时可以先完成文本、剧本和分镜生成并下载交付包。

### 图生视频一致性

生成 Hailuo 视频前，StoryMotion 会先生成白底正脸身份锚点、白底多角度角色转面图、场景参考图和每一个分镜的首帧关键图；每个含人物的镜头直接引用其身份锚点，每个视频任务均以对应关键图作为首帧。该过程会额外消耗图片生成额度，但可显著降低角色外观、服装、画风和场景漂移。生成产物保存在 `outputs/generated/<job-id>/visual_references/`，恢复同一任务时会复用已生成的图片。

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
