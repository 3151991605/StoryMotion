# NovelWriter 与 PenShot 开源参考审查

日期：2026-07-15

## 结论

两个项目均已获取到 `external/`，仅作为只读研究材料。本轮没有安装依赖、导入包或执行任何外部源码。

- NovelWriter：适合参考多智能体编排、阶段依赖、检查点、质量审查、一致性审查和人工批准；仓库根目录未发现许可证文件，因此不得复制、修改或分发其源码，除非后续取得明确授权。
- PenShot：适合参考剧本拆解、分镜工作流、任务生命周期和同步/异步接口；采用 MIT 许可证，可以在保留版权与许可声明的前提下复用，但当前 `main` 分支不应直接作为 StoryMotion 的进程内依赖。
- StoryMotion 应继续维护自己的前端、后端、领域协议和供应商适配器。两个项目都不是我们的应用骨架。

## 本地来源

| 项目 | 本地路径 | 上游地址 | 许可状态 |
| --- | --- | --- | --- |
| NovelWriter | `external/novelwriter/` | https://github.com/EdwardAThomson/NovelWriter | 未发现 LICENSE，思想参考限定 |
| PenShot | `external/penshot/` | https://github.com/neopen/story-shot-agent | MIT，需保留版权与许可声明 |

由于常规 GitHub Git 连接超时，本地材料通过 GitHub 官方 codeload 获取，是 2026-07-15 当日 `main` 分支快照，不包含 Git 历史。进入正式依赖评估前必须补充精确提交 SHA 或正式发布版本。

## NovelWriter 可借鉴的设计

NovelWriter 的价值主要在工作流思想，而不是代码：

1. 用统一的 Agent 输入、结果与错误信封隔离每个步骤。
2. 显式声明故事生成步骤及其依赖，避免绕过前置阶段。
3. 在长流程中保存检查点，允许失败恢复和人工继续。
4. 将质量审查与一致性审查设为独立角色，而不是让生成器自己打分。
5. 设定质量阈值、有限重试次数和最小改进幅度，防止无限循环。
6. 在关键产物处等待用户批准，再进入费用更高或不可逆的阶段。

对 StoryMotion 的落地建议：把这些思想实现为我们自己的后端编排服务，复用现有严格数据协议，不复制 NovelWriter 源码。

## PenShot 接口与工程风险

### 可用接口形态

当前源码提供 `PenshotFunction`，核心契约包括：

- 同步 `breakdown_script(...) -> PenshotResult`
- 异步 `breakdown_script_async(...) -> task_id`
- 结果包含 `task_id`、`success`、`status`、`data`、`error` 和处理时长
- 内部包含队列、并发控制、任务状态与后台事件循环

这与 StoryMotion 已有 `src/storymotion/adapters/penshot_adapter.py` 的边界设计相符：外部返回结构必须先转换成我们的 `ShotPackage`，不得泄漏到业务层。

### 不宜直接进程内导入的原因

1. `dotenv_loader.py` 会从当前目录、最多两级父目录、用户配置目录和包目录查找并加载 `.env`。若在 StoryMotion 后端进程中导入，可能读取或影响主应用密钥环境。
2. 部分 LLM 客户端会把配置写入进程级环境变量，如 `OPENAI_API_KEY`、`DEEPSEEK_API_KEY`、`DASHSCOPE_API_KEY`。
3. `PenshotFunction` 初始化时创建后台线程和事件循环，生命周期需要独立管理。
4. 依赖面较大，包含 LangChain、LangGraph、向量存储、Redis 等，容易与主后端依赖发生冲突。
5. 版本元数据不一致：`pyproject.toml` 声明 `0.3.5`，包内 `penshot.__version__` 仍为 `0.1.0`。当前 `main` 分支不能视为稳定、可重复安装的 SDK 版本。
6. 网络辅助方法可访问配置的 `base_url + /models`；任何可配置地址进入正式服务前都应做域名白名单和内网地址拦截。

静态关键词扫描未发现明显的“忽略上文指令”、已知数据外传域名或云元数据地址，但这不等同于完整安全审计。

## 推荐接入方式

```text
StoryMotion Web/API
        |
        v
StoryMotion 编排与领域模型
        |
        +--> RuleShotProvider（可靠回退）
        |
        +--> PenShotProviderAdapter
                    |
                    v
          隔离的 PenShot Sidecar
          独立工作目录 / 独立环境变量 / 超时 / 资源限额
```

边界要求：

- Sidecar 只接收剧本文本、项目 ID、语言和有限的风格参数。
- Sidecar 只返回任务状态和未经信任的原始分镜 JSON。
- StoryMotion 负责 schema 校验、场景与角色引用校验、总时长闭合、提示词清洗和错误归一化。
- 所有调用设置提交超时、轮询超时、取消机制和并发上限。
- PenShot 不可用时回退到现有规则分镜，不能阻断其余可行性验证。
- MiniMax 文本模型与海螺视频模型仍通过 StoryMotion 自己的供应商接口调用，不把供应商密钥交给前端。

## 下一步验证顺序

1. 定义 StoryMotion 到 PenShot Sidecar 的最小 HTTP 协议，并用假服务完成契约测试。
2. 在独立虚拟环境中锁定一个 PenShot 快照，验证启动、健康检查和中文剧本拆分，不接触主项目 `.env`。
3. 将真实返回样本送入现有适配器，补齐与当前 `instructions.fragments` 结构的映射测试。
4. 验证超时、失败、取消、非法 JSON、时长不闭合和 PenShot 不可用时的回退路径。
5. 通过后再决定是否长期维护 Sidecar；若维护成本过高，继续使用自研规则/模型分镜服务。

## 决策

当前可行性判断为“有条件可用”：NovelWriter 可以立即作为架构思想参考；PenShot 可以作为可替换的外部分镜引擎继续验证，但不能成为 StoryMotion 核心模型或主后端的强耦合依赖。

## 2026-07-15 契约验证进展

已实现 StoryMotion 侧的依赖无关 Sidecar 边界：

- 最小协议：`POST /v1/storyboards`、`GET /v1/tasks/{task_id}`、`DELETE /v1/tasks/{task_id}`。
- 标准库 HTTP JSON 传输、响应大小限制、请求超时、总体截止时间和超时取消。
- PenShot 原始结果继续经过现有严格适配器转换成 `ShotPackage`。
- Sidecar 不可用、任务失败、超时、协议错误或分镜结构非法时，可回退到 `RuleShotProvider`。
- 非 Sidecar 类程序错误不会被回退层吞掉。
- 本机回环假服务验证了真实 POST、GET、DELETE、中文 UTF-8 JSON、非 2xx 和非法 JSON。

验证结果：Sidecar/适配器聚焦测试 16 项通过；StoryMotion 完整测试 68 项通过。当前尚未启动真实 PenShot Sidecar，也未产生外部模型调用或费用。

## 2026-07-15 真实 PenShot 运行时结论

在独立 Python 3.11 环境中安装 PenShot 0.3.4 后，只有对实验副本应用以下兼容修复才能完成导入：dataclass `default_factory`、MiniMax 域名识别、两处 Redis 导入副作用，以及补装官方 API extra。通过 PenShot 构造的 `ChatOpenAI` 客户端成功调用了一次 MiniMax-M3：`finish_reason=stop`，总计 219 tokens，证明底层 OpenAI 兼容通道可用。

完整工作流验证失败。原本设置的 `enable_llm=False` 被 `ScriptParserAgent` 忽略，实际发生了 3 次额外 M3 剧本解析尝试；这是验证过程中发现的非预期调用。三个返回均未形成 PenShot 可接受的 JSON，随后工作流又因 `WorkflowState` 无法被当前 LangGraph msgpack 序列化而失败。任务耗时 48.827 秒，状态 `failed`，生成 0 个分镜。

因此结论从“PenShot 有条件可用”收紧为：**PenShot 0.3.4 的底层 MiniMax 客户端可连通，但完整分镜工作流当前不可用，不应进入产品或继续消耗配额调试。** StoryMotion 保留已验证的 Sidecar/Provider 边界和 `RuleShotProvider` 回退；下一步应实现我们自己的、有界 MiniMax 分镜生成节点，而不是继续修补 PenShot 内部工作流。
