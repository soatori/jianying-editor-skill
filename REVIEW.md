# jianying-editor-skill 完整审查报告

**审查方式**：只读诊断（skill-creator 结构/触发 + writing-skills SDO/词数 + ponytail-audit 可删收益）
**审查日期**：2026-04 前后（基于当前工作区快照）
**远程**：`https://github.com/soatori/jianying-editor-skill.git`
**约束**：未修改任何 skill 实现文件；本报告为新增产物。

---

## 0. 一句话判定

**这不是「一个 skill」，是「被塞进 skill 目录的半截产品仓库」。**

更准确：内核已经收敛成干净的 project-operations skill（约 **78 KB / 11 个文件**），外壳仍是完整 GitHub 产品仓（**7.09 MB / 156 个文件**）。外壳约占 **99% 体积**，且大量指向已删除模块。

| 层 | 体量 | 判定 |
|---|---|---|
| 真正的 skill 内核 | ~78 KB，11 文件 | 合格，可独立存活 |
| 旧产品外壳 / 死重量 | ~7.0 MB，其余 | 应剥离或大删 |
| `__pycache__`（含孤儿 pyc） | 1.43 MB，66 个 | 不应入库 |

**总评**：仓库身份分裂——`SKILL.md` / `jianying_project.py` 已经是三 skill 工作流中的「草稿访问与安全写回」层；`index.html` / `CHANGELOG` / `data/*.csv` / `assets/` / CI 仍假装自己是「剪映全能生成工具」产品。

---

## 1. skill-creator：结构与触发诊断

### 1.1 目录结构对照

skill-creator 期望：

```
skill-name/
├── SKILL.md
├── scripts/
├── references/
└── assets/   # 模板/字体/图标，供输出使用
```

实际：

```
jianying-editor-skill/          # 仓库名，非 skill 目录名规范
├── SKILL.md                    # name: jianying-editor  ← 与目录名不一致
├── scripts/
│   ├── jianying_project.py     # 933 行，唯一规范运行时 ✓
│   ├── jy_draft_crypto.py      # 唯一加密后端 ✓
│   ├── jy_wrapper.py           # 21 行 re-export 壳
│   ├── draft_inspector.py      # 7 行兼容 CLI
│   ├── __pycache__/            # 含已删模块的孤儿 pyc ✗
│   ├── core/ utils/            # 仅剩孤儿 pyc，无源码 ✗
│   └── vendor/pyJianYingDraft/ # 仅剩孤儿 pyc，无源码 ✗
├── references/                 # 8 个 md，其中 2 个未从 SKILL.md 链接
├── tests/                      # test_jianying_project.py（9 tests OK）
│   └── __pycache__/
├── examples/                   # inspect_and_apply_plan.py ✓
├── assets/                     # 5.04 MB：视频/封面/artistEffect/演示媒体 ✗
├── data/                       # 0.27 MB：12 个素材库 CSV ✗
├── docs/images/donate/         # 打赏图 ✗
├── agents/openai.yaml          # 非 skill 结构 ✗
├── index.html                  # 30.6 KB 落地页/开发者指南 ✗
├── pyproject.toml              # black/ruff 配置
├── requirements.txt            # 仅注释：stdlib only
├── VERSION                     # 3.0.0
├── CHANGELOG.md                # 只写到 v1.6.0，且描述已删功能
├── CONTRIBUTING.md SECURITY.md LICENSE
├── .pre-commit-config.yaml     # 指向不存在的 tests/test_wrapper.py
└── .github/workflows/ci.yml    # lint 不存在的脚本与 tools/*
```

### 1.2 validate_skill.py

```
WARNING: name 'jianying-editor' does not match folder name 'jianying-editor-skill'
PASS: 0 error(s), 1 warning(s)
```

- **WARNING 值得修**：目录名是 GitHub 仓库名，skill `name` 是 `jianying-editor`。安装/加载时以 frontmatter 为准可以工作，但命名不一致会干扰人工检索与目录约定。
- 无 ERROR：frontmatter 格式、`description` 长度、禁止字符、主文件命名均合规。

### 1.3 触发诊断（会不会加载 / 会不会误用）

**会加载吗？——偏弱。**

`description`（约 379 字符，&lt;1024）：

> Reliably inspect, decrypt, normalize, modify, validate, and recover existing Jianying Pro draft projects across legacy single-draft and newer multi-timeline layouts. Use for project structure, timelines, tracks, segments, materials, time-range mapping, safe write-back, and rollback; do not use it to decide what spoken content should be cut.

| 维度 | 现状 | 问题 |
|---|---|---|
| WHAT | 有（inspect/decrypt/modify…） | 过多动词像流程摘要 |
| WHEN / 触发短语 | 弱（“project structure, timelines…”） | 缺用户会说的字面短语 |
| 负向触发 | 有（“do not use … spoken content”） | 好，但可更具体 |
| 语言 | 全英文 | **剪映是中文产品；中文触发词为 0，中文任务几乎扫不到** |
| 与正文一致性 | 三分工写在 body | description 未点出 “existing draft / 回滚 / apply-plan” 等入口 |

**会误触发吗？——中等。**

- 正向：明确 “existing Jianying Pro draft” + 负向 “not decide spoken content”，生成新草稿/内容裁剪误触可控。
- 缺口：未负向排除「从零生成草稿 / TTS / 录屏 / 素材库检索」等旧产品能力；若用户说「剪映」但其实是 packaging/生成，仍可能误进。

**加载后指令会被执行吗？——内核表现好。**

`SKILL.md` 正文把「必做顺序」和「不可协商不变量」放在前面，命令可直接复制，progressive disclosure 到 6 个 linked references。这是当前仓库最像 skill 的部分。

### 1.4 结构层「项目壳」证据（为何判为小项目）

1. **CI / CONTRIBUTING / pre-commit / PR template 全部指向不存在文件**：
   - `scripts/api_validator.py`, `asset_search.py`, `auto_exporter.py`, `build_cloud_music_library.py`, `cloud_manager.py`, `universal_tts.py`
   - `scripts/utils/*.py`（仅剩 pyc）
   - `tests/test_wrapper.py`（不存在；现测试是 `test_jianying_project.py`）
   - `tools/check_repo_hygiene.py`, `tools/validate_data_schema.py`
2. **孤儿 pyc 证明源码曾存在后被删、缓存未清**：`scripts/core/*`、`scripts/utils/*`、`scripts/vendor/pyJianYingDraft/*` 共 66 个 `.pyc`，约 1.43 MB。
3. **产品化外壳**：`index.html`（“官方开发者指南 / Antigravity Skill v1.3”）、`docs/images/donate/`、`assets/video.mp4` 3 MB、`assets/cover.png` 1.1 MB、`agents/openai.yaml`。
4. **版本号三套并存**：`VERSION=3.0.0`，`CHANGELOG` 止于 `v1.6.0`，`index.html` 写 `v1.3`。
5. **git 历史**：最近提交 `refactor: restructure into project-operations layer for three-skill workflow`，说明作者已在做 skill 化收敛，但外壳未清干净。

---

## 2. writing-skills：SDO 与词数

### 2.1 词数

| 文件 | 词数 | 目标 | 判定 |
|---|---:|---|---|
| `SKILL.md` | **919** | writing-skills：其他 skill &lt;500；skill-creator：&lt;~5000 | **超 writing-skills 约 2×**，未爆 skill-creator 上限 |
| references 合计 | 1673 | 可接受（heavy reference 模式） | 合理外置 |
| 单篇最大 reference | safe-mutation 321 | — | 正常 |

**结论**：词数问题主要在 `SKILL.md` 本体偏长；references 外置是正确做法，不必为词数再砍内容深度。

### 2.2 SDO（Skill Discovery Optimization）问题

writing-skills 的硬规则：**description = When to Use，不要总结 skill 流程**。

当前 description 以动词串「inspect, decrypt, normalize, modify, validate, recover」总结了完整流水线，属于 **流程摘要型 description**。风险（该 skill 自己也写过）：代理可能读 description 就「以为已经会做」，跳过正文里的不变量与 dry-run/`--apply` 纪律。

**建议方向（诊断，不落地改文件）**：

- description 改为纯触发条件 + 字面短语，例如覆盖：
  - 英文：`Jianying draft`, `draft_content.json`, `apply-plan`, `clone timeline`, `rollback`, `encrypted draft`, `multi-timeline`
  - 中文（强烈建议加入）：`剪映`、`草稿`、`时间线`、`字幕对齐计划`、`安全写回`、`回滚`、`多轨道`、`draft_info`
- 负向补全：`Do NOT use for creating drafts from scratch, TTS, screen recording, asset search, or packaging decisions.`
- 保留现有「不决定口播内容」负向。

### 2.3 其他 writing-skills 观察

| 项 | 现状 |
|---|---|
| 命名 | `jianying-editor` 非 gerund，但领域专名可接受 |
| 交叉引用 | body 正确链到 references；未用 `@` 强载，好 |
| 边界冲突 | `references/huazi-combination-import.md`、`audio-track-and-sfx.md` **未被 SKILL.md 链接**，且后者写 “packaging decision **executed by this skill**”，与 SKILL.md「packaging 归 `jianying-packaging`」直接冲突 → **SDO/边界漂移** |
| 示例 | CLI 示例具体可复制，好 |
| 叙事反模式 | 无 session war-story，好 |
| 测试痕迹 | `tests/test_jianying_project.py` 9 tests **通过**；证明 skill 有可执行验证，不是纯文档 |

---

## 3. ponytail-audit：按最大可删收益排序

范围：仅过度工程与复杂度/死重量，不含正确性与安全漏洞修复。

**核心存活集（建议保留）**

```
SKILL.md
scripts/jianying_project.py      # 933 行，stdlib + jy_draft_crypto
scripts/jy_draft_crypto.py
references/architecture-and-versioning.md
references/safe-mutation.md
references/operation-contract.md
references/segment-location-and-timebase.md
references/replica-manifest-and-transactions.md
references/normalized-model.md
tests/test_jianying_project.py
examples/inspect_and_apply_plan.py   # 可选，但小且有用
```

**Findings（最大收益优先）**

| # | Tag | 切什么 | 替代 | 路径 / 估算 |
|---:|---|---|---|---|
| 1 | `delete:` | 演示/营销媒体与 artistEffect 资源 | 无；skill 不引用 | `assets/**` ≈ **5.04 MB**（`video.mp4` 3 MB、`cover.png` 1.1 MB、shaders/演示图） |
| 2 | `delete:` | 全部已提交 `__pycache__`（含孤儿模块字节码） | 无；`.gitignore` 已写却仍入库 | `**/__pycache__/**` ≈ **1.43 MB / 66 files** |
| 3 | `delete:` | 旧产品素材库 CSV | 无；`scripts/*.py` 零引用 | `data/*.csv` ≈ **0.27 MB / 12 files**（filters/transitions/tts/scene…） |
| 4 | `delete:` | 产品落地页 | 无 | `index.html` **30.6 KB**（还带 CDN Tailwind，非 skill 职责） |
| 5 | `delete:` | 打赏图 | 无 | `docs/images/donate/**` ≈ **0.24 MB** |
| 6 | `delete:` | 旧 CI / 贡献流水线（指向不存在文件，必挂） | 若需 CI：只 lint/test 现存 `jianying_project`+`jy_draft_crypto`+`tests` | `.github/workflows/ci.yml`, `CONTRIBUTING.md` 检查段, `.pre-commit-config.yaml`, `.github/pull_request_template.md` 检查清单 |
| 7 | `delete:` | 失真变更日志与版本碎片 | 单一 VERSION；或 CHANGELOG 重写为 v3 project-ops 叙事 | `CHANGELOG.md`（止于 v1.6、描述 TTS/录制等已删能力）↔ `VERSION` 3.0.0 ↔ `index.html` v1.3 |
| 8 | `delete:` | 未链接且与边界冲突的 packaging 遗留文档 | 并入真正的 `jianying-packaging`，或删除 | `references/huazi-combination-import.md`, `references/audio-track-and-sfx.md` ≈ 276 词 |
| 9 | `delete:` | 非 skill / 非本运行时的 agent 包装 | 无 | `agents/openai.yaml` |
| 10 | `yagni:` | 兼容 re-export 壳 | 直接 `from jianying_project import ...`；SKILL.md 已指定 canonical | `scripts/jy_wrapper.py`（21 行） |
| 11 | `yagni:` | 兼容 CLI 别名 | `python scripts/jianying_project.py ...` | `scripts/draft_inspector.py`（7 行；SKILL.md 仍提及，删则同步改 SKILL.md） |
| 12 | `yagni:` | 空壳目录 | 删除目录 | `scripts/core/`, `scripts/utils/`, `scripts/vendor/`（无 `.py` 源码） |
| 13 | `native:` / 文档债 | GitHub 安全策略对 skill 安装场景价值低 | 仓库若继续当公开 GitHub 项目可保留 | `SECURITY.md`（非优先） |

**净效果（量级）**

```
net: 约 -7.0 MB / 约 -130+ files 可能；运行时 deps 本来就是 0（stdlib only）。
真正 skill 核心从 ~7.09 MB → ~78 KB（约 90× 体积缩减）。
```

**不要砍（易误伤）**

- `scripts/jianying_project.py`：大但单一职责，且是唯一规范实现。
- 6 个已链接 references：progressive disclosure 正确用法。
- `tests/`：已证明可跑通（9 OK），是 skill 的 RED/GREEN 证据。
- `requirements.txt` 空依赖：不是 bloat，是正确声明。

---

## 4. 内核健康度（与外壳对比）

| 检查 | 结果 |
|---|---|
| `jianying_project.py` 依赖 | 仅 stdlib + `jy_draft_crypto`；**不 import** vendor/core/utils/data/assets |
| 单测 | `unittest discover` → **Ran 9 tests … OK** |
| pytest | 本环境无 pytest（CONTRIBUTING/pre-commit 仍写 pytest → 又一处文档漂移） |
| SKILL.md 链接完整性 | 6/6 已链 references 存在；另有 2 个未链遗留 |
| 插件式超能力 | 无 MCP 强依赖；Windows DLL 加密后端有明确能力探测，合理 |

**内核质量高于外壳质量一个数量级。** skill 化重构方向正确，问题是「删源码没删壳」。

---

## 5. 建议处置路线（仅建议，未执行）

### 阶段 A — 立刻止损（无行为变化）

1. 删除全部 `__pycache__` 与孤儿 vendor/core/utils 空壳。
2. 从版本库移除 `assets/` 媒体、`docs/images/donate/`、`index.html`、`data/`（若确认无外部消费方；git 历史仍在）。
3. 删除或重写 `ci.yml` / pre-commit / CONTRIBUTING 检查清单，只指向现存文件。
4. 统一版本叙事：`VERSION`、CHANGELOG、对外页面三选一真相源。

### 阶段 B — 收敛为真 skill

5. 评估删除 `jy_wrapper.py` / `draft_inspector.py`（或明确保留兼容并写进 SKILL.md 的唯一理由）。
6. 把 `huazi-*` / `audio-track-and-sfx` 移出本 skill（与 packaging 边界冲突）。
7. 重写 `description`：纯触发 + 中英字面短语 + 完整负向；词数上把 SKILL.md 从 ~919 压向 ~500–650（细则继续走 references）。
8. 目录名与 `name` 对齐策略二选一：改文件夹为 `jianying-editor`，或接受仓库名并文档说明。

### 阶段 C — 产品化（若仍要当 GitHub 产品）

9. 落地页/捐赠/CHANGELOG/多 IDE 安装文档 **拆出独立 repo 或 `/docs-site`**，不要与 skill 同树。
10. 若需要素材库/TTS/录制能力：拆成独立 skill，而不是把 CSV 和媒体塞回 editor skill。

---

## 6. 最终结论

| 问题 | 答案 |
|---|---|
| 是一个 skill 吗？ | **内核是；仓库整体不是。** |
| 是塞进 skill 目录的小项目吗？ | **是，而且是「产品仓库半截 skill 化」：内核已重构，外壳未剥离。** |
| 最大问题 | 99% 体积与全部工程化外壳服务的是**已删除的旧产品**；CI/文档还指向不存在的模块。 |
| 最大优点 | `jianying_project.py` + 6 references + 测试构成的 project-ops 层清晰、可测、边界意识强。 |
| 优先动作 | **按可删收益先砍 assets + pycache + data + 落地页/捐赠 + 失真 CI/文档**，再修 SDO/触发词，再处理兼容壳。 |

**Bottom line：** 当成「一个 skill」来装可以工作（validator PASS、单测 OK、主路径自洽）；当成「一个仓库」来维护会持续踩空文档与 CI。先做减法，再谈 polish。
