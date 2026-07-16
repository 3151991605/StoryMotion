# StoryMotion 四人产品交付分工方案

> **执行原则：** 四个人围绕同一条产品流水线工作，每个人只对一个明确的数据入口和出口负责。先做出一条质量可接受的 30—60 秒漫剧，再扩展功能。

## 1. 当前项目处于什么阶段

StoryMotion 已经完成“技术可行性验证”，但还没有达到可交给普通用户使用的产品质量。

已经完成并有测试证据的能力：

- MiniMax M3 可以生成并校验 `StoryPackage`、`ScreenplayPackage` 和 `ShotPackage`。
- 自研 `MiniMaxShotProvider` 可以生成 6 个、总计 60 秒的结构化分镜。
- MiniMax `image-01` 可以生成首帧。
- Hailuo 可以通过异步任务生成并下载真实 MP4。
- FFmpeg 和 Mock 视频链路可以运行。
- 当前共有 116 项自动化测试通过。

当前最主要的问题不是“能不能生成”，而是“生成结果是否稳定、好看、可控”：

- 人物外观、服装和标志容易变化。
- “金色疤痕”可能被模型误解成现代手表。
- 一个 6 秒镜头内安排的动作太多。
- 首帧内容与视频运动提示词可能冲突。
- 还没有候选图选择、人工批准、质量评分和局部返工机制。
- Streamlit 只是验证页面，正式的前后端还没有建立。

因此，下一阶段共同目标是：

> 用户输入一句创意后，可以在自研网页中逐步查看、修改和批准故事、剧本、分镜、人物参考图、首帧和视频片段，最终输出一条质量可接受的 30—60 秒竖屏漫剧。

## 2. 四个人怎样并行工作

### 2.1 不是等上游，而是使用“标准替身”

从产品数据流看，A、B、C、D 的成果前后相连；从开发过程看，四个人不能真的按 A 做完、B 再开始的方式推进。团队采用“契约驱动并行开发”：先固定数据格式，再为每个上游准备一份合法 JSON 样例和一个 Mock 服务。下游开发时先使用标准替身，真实上游完成后只替换数据来源，不重写下游逻辑。

四个人从第一天开始的实际工作关系是：

```text
成员 A：用固定 ProjectBrief 开发真实故事生成

成员 B：用固定 StoryPackage 开发剧本和分镜

成员 C：用固定 ShotPackage、现有首帧和现有 MP4 开发媒体流程

成员 D：用固定全链路 JSON 和 Mock Provider 开发 FastAPI、数据库和前端
```

所以“业务数据的前后关系”和“团队工作的先后关系”要分开理解：产品运行时依次经过 A、B、C，开发时四个人同时开始。

### 2.2 产品运行时的数据流

```text
成员 A：故事内容
用户创意 → StoryPackage
                |
                v
成员 B：漫剧与分镜
StoryPackage → ScreenplayPackage → ShotPackage
                                      |
                                      v
成员 C：视觉与视频
ShotPackage → 角色参考图 → 首帧 → 视频片段 → 最终 MP4
                                      |
                                      v
成员 D：产品与集成
网页操作 + FastAPI + 项目状态 + 人工批准 + 串起 A/B/C
```

成员 D 负责把流水线串起来，但不替其他成员修改生成逻辑。

### 2.3 开发时的并行数据流

```text
                         +--> 固定 StoryPackage --> 成员 B
                         |
标准样例与 Mock 服务 ----+--> 固定 ShotPackage  --> 成员 C
                         |
                         +--> 固定全流程状态    --> 成员 D

固定 ProjectBrief --------------------------------> 成员 A
```

各成员完成后，只执行以下替换：

```text
固定 StoryPackage  → A 的真实 StoryPackage
固定 ShotPackage   → B 的真实 ShotPackage
Mock 媒体任务       → C 的真实媒体任务
Mock 流程服务       → A/B/C 的真实服务
```

如果替换后下游必须大量改代码，说明公共协议没有真正冻结，不能把问题归咎于下游成员。

### 2.4 第一批必须固定的协议与样例

以 StoryMotion 已有 Pydantic 模型为 v1 基线，先冻结：

```text
ProjectBrief v1
StoryPackage v1
ScreenplayPackage v1
ShotPackage v1
ImageTask v1
VideoTask v1
ArtifactApproval v1
```

团队应把现有 `tests/fixtures/valid_storymotion_bundle.json` 和验证产物整理成以下独立样例：

```text
tests/fixtures/project_brief_v1.json
tests/fixtures/story_package_v1.json
tests/fixtures/screenplay_package_v1.json
tests/fixtures/shot_package_v1.json
tests/fixtures/media_tasks_v1.json
tests/fixtures/artifact_approvals_v1.json
```

这些文件不是临时演示垃圾，而是四个人共同遵守的“交接合同”。每份样例都必须能通过对应 Pydantic 模型校验。

现有材料可以立即作为尚未拆分前的启动数据：

- `tests/fixtures/valid_storymotion_bundle.json`
- `outputs/verification/minimax_shot_provider_package.json`
- `outputs/verification/hailuo_single_shot/shot_001_first_frame.jpg`
- `outputs/verification/hailuo_single_shot/shot_001.mp4`

因此，整理独立 fixture 的工作不会阻塞 A、B、C、D 第一天开工。

### 2.5 Mock 服务必须与真实服务同接口

成员 D 先让页面调用 Mock 实现，但接口名称、请求和响应必须与未来真实实现一致。第一版至少约定：

```text
POST /projects
POST /projects/{project_id}/story
POST /projects/{project_id}/screenplay
POST /projects/{project_id}/shots
POST /shots/{shot_id}/images
POST /shots/{shot_id}/videos
GET  /tasks/{task_id}
POST /artifacts/{artifact_id}/approve
```

Mock 可以返回固定 JSON、现有首帧和现有 MP4，但必须明确标记 `provider=mock`，前端不能把它显示成真实生成结果。

### 2.6 独立分支和文件所有权

四个人不能同时直接修改同一个工作目录或同一条分支。每个人在自己的电脑上使用独立分支；如果共用一台电脑，则使用 Git worktree：

```text
feature/story-system       成员 A
feature/screenplay-shots   成员 B
feature/media-pipeline     成员 C
feature/product-shell      成员 D
```

主要文件所有权：

| 成员 | 主要负责的目录或文件 |
| --- | --- |
| A | `models/story*`、`models/intermediate.py`、`services/story_*` |
| B | `models/screenplay.py`、`models/shot.py`、分镜服务与 Provider |
| C | `models/media.py`、`providers/minimax_media.py`、媒体与合成服务 |
| D | `api/`、`orchestration/`、`repositories/`、`db/`、`frontend/` |

公共模型冻结后，任何成员包括 D 都不能静默修改。确需变更时，必须先更新协议说明、fixture 和契约测试，再通知另外三人。

## 3. 成员 A：故事内容负责人

### 角色名称

故事策划与文本智能体负责人。

### 用大白话解释

成员 A 负责把用户的一句话变成一个结构完整、人物和世界观不打架的短故事。A 不负责画图，也不负责生成视频。

### 输入和输出

```text
输入：用户创意、题材、风格、目标时长、人物数量限制
输出：通过严格校验的 StoryPackage JSON
```

并行启动方式：第一天直接读取固定 `ProjectBrief`，不等待 D 的网页和数据库完成。A 的服务完成前，B 和 D 继续使用固定 `StoryPackage`。

### 主要工作

1. 整理用户需求：题材、主角、核心能力、冲突、结尾悬念、时长。
2. 维护世界观、人物卡、剧情节拍和故事正文的生成提示词。
3. 把大任务拆成有边界的小步骤：世界观、人物、剧情、正文分别生成。
4. 增加故事审核器，独立检查人物动机、设定冲突、剧情完整性和是否适合改成 30—60 秒漫剧。
5. 审核不通过时只修改有问题的字段，最多返工两轮，不能无限调用模型。
6. 建立项目记忆，保存已经确认的角色设定、世界规则和失败经验。
7. 为成员 B 提供稳定、版本明确的 `StoryPackage` 样例。

### 主要修改范围

- `src/storymotion/models/project.py`
- `src/storymotion/models/intermediate.py`
- `src/storymotion/models/story.py`
- `src/storymotion/services/story_assembler.py`
- 新建 `src/storymotion/services/story_review.py`
- 新建 `src/storymotion/services/story_revision.py`
- 与故事相关的 `scripts/verify_*.py`
- 与故事相关的 `tests/test_*.py`

### 参考哪些开源项目

- `external/novelwriter/`：只参考阶段依赖、故事规划、质量审核、一致性审核和人工批准思想。该仓库没有确认到许可证，不复制、不修改、不分发源码。
- VictorTaelin/AI-scripts：只参考 `Long` 的长期记忆和 `Board` 的“生成器与审核器分离”思想。不需要拉入主工程，也不需要使用其中的 TypeScript 代码。

### 不做什么

- 不修改 Hailuo、图片和 FFmpeg 代码。
- 不把 NovelWriter 直接安装进 StoryMotion。
- 不追求长篇小说、多集连续剧和几十个人物。
- 不自行改变 `StoryPackage` 公共字段；确有需要时先和成员 D 评审协议。

### 验收标准

- 固定案例可以稳定生成合法 `StoryPackage`。
- 人物、地点和剧情引用没有悬空。
- 故事可以在目标时长内改编，不能塞入明显过多情节。
- 审核报告能指出具体字段和修改建议，而不是只给一个笼统分数。
- 失败不会覆盖最后一次成功产物，不会无限重试。

## 4. 成员 B：漫剧改编与分镜负责人

### 角色名称

编剧、分镜与可视化质量负责人。

### 用大白话解释

成员 B 负责把故事变成“摄像机真的能拍出来”的剧本和镜头清单。B 要决定每个镜头出现谁、在哪里、做一个什么动作、镜头怎么运动，以及提示词里不能出现哪些错误元素。

### 输入和输出

```text
输入：StoryPackage
中间产物：ScreenplayPackage
输出：通过可视化审核的 ShotPackage
```

并行启动方式：第一天直接读取 `story_package_v1.json` 或现有完整 bundle，不等待 A 的真实故事生成器。A 完成后只替换输入来源。

### 主要工作

1. 把故事压缩成 3—6 个场景，控制对白、旁白和总时长。
2. 把复杂场景拆成简单镜头，原则是“一个短视频片段只表达一个核心动作”。
3. 维护镜头景别、机位、构图、动作、镜头运动和负面提示词。
4. 解决语义歧义，例如明确写成“皮肤上的发光金色疤痕，不是手表、首饰或机械装置”。
5. 检查首帧描述和视频运动提示词是否冲突。
6. 建立分镜质量审核规则：人物引用、地点引用、时长闭合、动作复杂度、现代元素误入、风格一致性、可生成性。
7. 支持只修改某一个镜头或某一个字段，不重新生成全部分镜。
8. 维护 `RuleShotProvider` 作为免费、稳定的回退方案。

### 主要修改范围

- `src/storymotion/models/screenplay.py`
- `src/storymotion/models/shot.py`
- `src/storymotion/services/screenplay_assembler.py`
- `src/storymotion/providers/minimax_shot_provider.py`
- `src/storymotion/providers/rule_shot_provider.py`
- 新建 `src/storymotion/services/shot_review.py`
- 新建 `src/storymotion/services/shot_revision.py`
- 分镜相关测试和验证脚本

### 参考哪些开源项目

- `external/penshot/`：只参考剧本拆解、分镜字段、任务生命周期和提示词组织方式。
- VictorTaelin/AI-scripts：参考“局部精确修改”和独立审核思想。
- StoryMotion 已有 `penshot_adapter.py` 和 Sidecar 契约可以保留，用于未来兼容性研究。

### 对 PenShot 的明确处理

- 不继续修补 PenShot 0.3.4。
- 不把 PenShot 作为产品主链依赖。
- 不让前端接触 PenShot 原始数据。
- 主链使用 StoryMotion 自研 `MiniMaxShotProvider`，失败时回退 `RuleShotProvider`。

### 不做什么

- 不负责真实调用图片或视频 API。
- 不负责 React 页面。
- 不为一次镜头失败重新生成整个故事。
- 不在未沟通的情况下改变成员 C 已依赖的 `ShotPackage` 字段。

### 验收标准

- 总时长严格等于项目目标时长。
- 每个镜头人物、地点和参考资料都有合法 ID。
- 一个 5—6 秒镜头原则上只有一个主要动作。
- 每个镜头同时具备首帧描述、视频运动描述和负面提示词。
- 固定案例中不再把金色疤痕描述成手表。
- 用户可以单独修改 `shot_001`，其他镜头内容和 ID 保持不变。

## 5. 成员 C：视觉资产与视频负责人

### 角色名称

角色一致性、图片、视频与成片负责人。

### 用大白话解释

成员 C 负责真正“出画面”：先确定人物应该长什么样，再为每个镜头做首帧，之后调用海螺让画面动起来，最后用 FFmpeg 拼成 MP4。

### 输入和输出

```text
输入：通过审核的 ShotPackage
中间产物：角色参考图、场景参考图、每镜头候选首帧、视频任务
输出：选中的视频片段和最终 MP4
```

并行启动方式：第一天直接读取已验证的 `minimax_shot_provider_package.json`，使用现有首帧、真实 MP4 和 Mock Provider，不等待 A、B 完成。

### 主要工作

1. 定义统一美术风格，例如“东方玄幻二维漫画、竖屏、电影光影”，防止照片风和动漫风混在一起。
2. 为主角制作标准参考图：正面、半身、服装、发型、年龄、标志性疤痕。
3. 角色参考图必须先人工批准，之后才允许批量生成镜头首帧。
4. 每个镜头生成 2—3 张低成本候选首帧，保留提示词、模型参数和生成记录。
5. 对首帧进行人物、风格、构图、场景和错误元素检查。
6. 只有用户选中的首帧才能提交 Hailuo 视频任务。
7. 管理 Hailuo 的提交、轮询、恢复、下载和失败状态；不自动创建新的付费任务。
8. 用 FFmpeg 统一分辨率、帧率和音视频格式，拼接视频片段，按需要增加字幕、旁白和背景音乐。
9. 保存每次调用的安全追踪信息，但绝不记录 API Key 或完整签名下载地址。

### 主要修改范围

- `src/storymotion/models/media.py`
- `src/storymotion/providers/media.py`
- `src/storymotion/providers/minimax_media.py`
- `src/storymotion/providers/mock_video_provider.py`
- 新建 `src/storymotion/services/visual_reference_service.py`
- 新建 `src/storymotion/services/media_pipeline.py`
- 新建 `src/storymotion/services/video_assembly.py`
- `scripts/verify_hailuo_single_shot.py`
- 媒体、下载安全和 FFmpeg 相关测试

### 参考和依赖

- MiniMax/Hailuo 官方 API 文档：作为接口和模型参数的唯一事实来源。
- FFmpeg：直接作为系统工具使用，不修改其源码。
- PenShot：最多参考提示词字段，不使用其运行时。
- 不需要 NovelWriter。

### API Key 规则

- 文本/图片使用 `MINIMAX_API_KEY`。
- 视频使用 `MINIMAX_VIDEO_API_KEY`。
- Key 只保存在后端环境变量，不能传给网页。
- 所有真实付费生成都必须经过明确的用户批准。

### 不做什么

- 不自己训练图片或视频模型。
- 不同时接入多家视频厂商。
- 不做完整时间线剪辑器。
- 不因为下载失败就重新创建视频任务，应先恢复已有任务。

### 验收标准

- 有一套经过人工确认的林尘角色标准参考图。
- 三个简单镜头的首帧在人物、服装和画风上基本一致。
- 用户选中首帧后才能产生付费视频任务。
- 视频任务可在程序重启后继续查询，不重复扣费。
- 最终 MP4 可以正常播放，技术规格统一，失败镜头可单独替换。

## 6. 成员 D：产品、前后端与总集成负责人

### 角色名称

产品集成、FastAPI 与自研网页负责人。

### 用大白话解释

成员 D 负责让普通用户能在网页里完成整个流程，同时像项目经理一样看住四个人的接口。D 不负责替 A 写故事，也不负责替 C 调视频提示词。

### 输入和输出

```text
输入：A/B/C 提供的服务和数据模型
输出：用户可操作的完整 StoryMotion 产品
```

并行启动方式：第一天用固定全链路 JSON、Mock Provider 和现有媒体文件开发页面与接口，不等待 A、B、C 的真实服务。

### 主要工作

1. 建立 FastAPI 后端，把 A/B/C 的能力包装成稳定接口。
2. 建立 React + TypeScript 自研前端；Streamlit 只保留为内部验证工具。
3. 设计项目页面：创建项目、故事、剧本、分镜、角色参考图、首帧选择、视频任务、成片。
4. 建立项目状态和产物版本记录，保存“草稿、待审核、已批准、生成中、成功、失败”等状态。
5. 在高费用节点加入人工批准：批准角色图、批准首帧、批准视频生成。
6. 用 LangGraph 或等价的轻量状态机串起流程，但不能把厂商原始响应传到前端。
7. 建立 SQLite 数据库，第一版保存项目、产物、任务和审核决定；媒体文件仍放在本地目录。
8. 提供错误提示、任务恢复、日志查看和单镜头重试入口。
9. 维护接口文档、启动脚本、演示数据、README 和最终答辩材料。
10. 作为协议负责人，组织 `StoryPackage`、`ScreenplayPackage`、`ShotPackage` 和媒体任务模型的变更评审。

### 计划新建和修改范围

- 新建 `src/storymotion/api/`
- 新建 `src/storymotion/orchestration/`
- 新建 `src/storymotion/repositories/`
- 新建 `src/storymotion/db/`
- 新建 `frontend/`
- 修改 `src/storymotion/services/demo_pipeline.py`，逐步升级为正式编排服务
- 保留 `streamlit_app.py`，但不继续把它扩展成正式前端
- 增加 API、数据库、状态流转和前端测试

### 参考哪些开源项目

- NovelWriter：参考检查点、阶段依赖和人工批准，不复用界面或源码。
- AI-scripts：参考项目记忆、待回答问题、审核意见进入下一轮的机制。
- LangGraph：使用官方 Python 包实现状态编排，不需要拉取整个源码仓库。
- FastAPI、React、Vite：使用官方脚手架和依赖，不需要复制第三方完整项目。

### 不做什么

- 第一版不做登录、支付、多人实时协作和云端部署。
- 不把前端直接连接 MiniMax/Hailuo。
- 不允许前端绕过批准直接批量生成付费视频。
- 不把所有业务逻辑写进 FastAPI 路由函数。

### 验收标准

- 用户可以从网页创建项目并看到每阶段真实状态。
- 可以查看、修改和批准故事、剧本、分镜和图片候选。
- 页面刷新或后端重启后，视频任务仍能继续查询。
- 失败显示真实原因，不把 Mock 结果显示成真实生成结果。
- 能用一个固定案例完整演示到最终 MP4。

## 7. 哪些项目需要下载，哪些需要修改

| 项目或工具 | 当前状态 | 谁使用 | 是否修改源码 | 正确用法 |
| --- | --- | --- | --- | --- |
| StoryMotion | 当前主项目 | 全员 | 是 | 所有正式代码都写在这里 |
| NovelWriter | 已在 `external/novelwriter/` | A、D | 否 | 只读研究工作流与审核思想 |
| PenShot | 已在 `external/penshot/` | B | 当前不修改 | 只读研究分镜结构；保留适配器，退出主链 |
| VictorTaelin/AI-scripts | 尚不需要放入主工程 | A、B、D | 否 | 浏览 `Long`、`Board`、`HoleFill` 的思想即可；若下载，只放 `external/ai-scripts/` 并标记只读 |
| LangGraph | Python 依赖 | D，A/B 配合 | 不改源码 | 用于状态、检查点、审核循环和人工批准 |
| FastAPI | Python 依赖 | D | 不改源码 | 自研后端接口 |
| React + TypeScript + Vite | 前端脚手架 | D | 修改自己的前端代码 | 自研正式网页 |
| FFmpeg | 工具依赖 | C | 不改源码 | 视频标准化、拼接和字幕 |
| MiniMax/Hailuo SDK/API | 外部服务 | A、B、C | 不改服务源码 | 通过 StoryMotion Provider 调用 |

禁止把 `external/` 中任何项目直接复制进 `src/storymotion/`。如果确实需要借鉴一段 MIT 代码，必须先记录来源、许可证、固定版本和修改说明，再经过成员 D 评审。

## 8. 两周执行安排

### 第 1—2 天：四条工作线同时启动

- A：读取固定 `ProjectBrief`，开发故事审核与局部返工；同时整理固定 `StoryPackage`。
- B：读取固定 `StoryPackage`，把原 `shot_001` 拆成 3 个简单镜头，制定分镜审核表。
- C：读取固定 `ShotPackage`，确定一种画风，设计角色标准参考图提示词和媒体产物目录。
- D：读取固定全流程 bundle，搭建 FastAPI、React、SQLite 和 Mock 接口空壳。
- 全员：确认 v1 公共协议；D 负责汇总 fixture，A/B/C 各自校验自己负责的数据类型。

共同验收：四条分支都有独立可运行的最小结果；任何成员都没有因为等待上游而停工；全部固定 JSON 能通过契约测试。

### 第 3—4 天：建立视觉基线

- A：完成故事审核与局部返工最小版本。
- B：完成镜头拆分、语义消歧和首帧/运动冲突检查。
- C：生成林尘角色参考图候选，组织人工批准；用 Mock 数据测试候选管理。
- D：继续使用 Mock 服务，完成项目、故事、剧本、分镜的查看和批准接口。

共同验收：角色设定、故事和三个实验镜头全部得到人工批准。

### 第 5—6 天：首帧与视频质量对比

- A：为固定案例封版，不随意重新生成。
- B：根据首帧结果只修正失败镜头提示词。
- C：每镜头生成候选首帧，经批准后各生成一个视频；记录效果、费用、耗时和失败原因。
- D：完成首帧候选选择和视频任务状态页面。

共同验收：三个镜头中至少两个达到人物和画风基本一致，且没有“疤痕变手表”等明显错误。

### 第 7—8 天：正式串联

- A/B/C：把各自能力封装成与 Mock 相同契约的真实服务，不在路由中写业务逻辑。
- D：逐个用真实服务替换 Mock；每替换一个就执行契约测试和回归测试，不一次性全换。
- 串联顺序只影响集成测试，不影响四个人继续开发各自功能。

共同验收：从网页输入到生成视频片段全链路跑通；刷新页面不丢任务。

### 第 9 天：成片与失败演练

- C：完成 FFmpeg 拼接、字幕和基础音轨。
- A/B：检查最终内容表达和镜头顺序。
- D：演练模型失败、视频超时、程序重启、单镜头替换和 Mock 回退。

共同验收：失败时不会重复扣费，已成功产物不会丢失。

### 第 10 天：演示封版

- 固定一个已成功案例和一份离线演示数据。
- 录制真实调用与离线回退两套演示。
- 完成架构图、数据流图、成本和耗时记录、已知限制与下一步计划。

## 9. 团队协作规则

1. 每天开始前，每人只报三件事：昨天产物、今天目标、当前阻塞。
2. 公共模型变更必须四人知晓，由 D 汇总；任何人不得静默改字段。
3. A、B、C 各自维护至少一个固定输入 fixture，保证上游没完成时也能开发。
4. 真实媒体调用由 C 统一执行；其他成员不得为了调试随意消耗视频额度。
5. 每个功能必须有自动化测试；真实 API 只做少量验收，日常使用 Mock。
6. 每次生成保存输入、输出、模型、耗时、任务 ID 和脱敏错误，不保存密钥。
7. 已获人工批准的产物必须版本化，后续返工不能直接覆盖。
8. 一次只解决一个质量问题，优先局部返工，禁止无理由整链重跑。
9. 四个人使用独立分支或 worktree，不能把未通过测试的半成品直接放进共同工作目录。
10. 每天至少运行一次公共契约测试；集成失败时先判断是协议不一致还是实现错误。
11. 公共协议需要变更时，按“提出原因 → 更新版本 → 更新 fixture → 更新测试 → 通知全员 → 合并”的顺序处理。
12. Mock 和真实 Provider 必须实现同一接口；前端只依赖接口，不依赖具体厂商。

## 10. 产品经理最终判断

这四个人在产品运行时是四个连续工位，在项目开发时是四条同时推进的工作线：

- A 保证“故事讲得通”。
- B 保证“故事拍得出来”。
- C 保证“画面生成得出并且能成片”。
- D 保证“普通用户能操作、能恢复、能看懂结果”。

当前最优先的不是继续扩展模型数量，也不是马上完善全部前端，而是由 B 和 C 先建立一个可接受的视觉质量基线，同时 A 完成有限审核循环、D 搭建最小产品骨架。只要角色参考图、三个简单镜头和人工批准流程跑稳，后续扩展到完整 30—60 秒作品才有意义。

并行开发是否成功，不看四个人是否同时敲代码，而看以下三个结果：

1. 任意成员都能在没有真实上游的情况下运行和测试自己的模块。
2. 真实上游完成后，下游只替换实现或数据来源，不推翻重写。
3. 四条分支每天都能产生可独立验收的进展，并在第 7—8 天低成本接合。
