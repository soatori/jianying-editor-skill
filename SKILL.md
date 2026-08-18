---
name: jianying-editor
description: 剪映 (JianYing) AI自动化剪辑的高级封装 API (JyWrapper)，提供开箱即用的 Python 接口，支持录屏、素材导入、字幕生成、Web 动效合成及项目导出。全面适配 MacOS (Apple Silicon/Intel) 与 Windows，支持 v5.9+ (draft_info.json) 架构、v6+/v11.x 草稿解密/加密、字幕位置/样式/动画深度修改、工程自修复、智能配音字幕及录屏变焦。
---

# JianYing Editor Skill

Use this skill when the user wants to automate video editing, generate drafts, or manipulate media assets in JianYing Pro.

Agent execution playbook: [docs/agent-playbook.md](docs/agent-playbook.md)
Minimal command SOP: [docs/minimal-command-sop.md](docs/minimal-command-sop.md)
Natural language usage guide: [usage.md](usage.md)
Draft inspector CLI:
`python <SKILL_ROOT>/scripts/draft_inspector.py list --limit 20`
`python <SKILL_ROOT>/scripts/draft_inspector.py summary --name "DraftName"`
`python <SKILL_ROOT>/scripts/draft_inspector.py show --name "DraftName" --kind content --json`
For generic editing requests, always follow the "Quick Edit Runtime Template" and "Acceptance Checklist" in that playbook.

## 🚨 重要开发原则 (CRITICAL DEVELOPER RULES)
1.  **脚本位置**：**禁止在 Skill 内部目录创建剪辑脚本**。所有的剪辑逻辑实现代码（`.py` 脚本）必须存放在用户当前项目的**根目录**（或子目录，如 `scripts/`），以保持 Skill 库的纯净和可移植性。
2.  **版本与架构**：
    - **双平台适配**：已全面支持 MacOS (路径探测/录屏) 与 Windows。
    - **Auto-healing**：支持 v5.9+ (`draft_info.json`)。若草稿损坏或版本冲突，使用 `overwrite=True` 初始化 `JyProject` 可触发自动修复。
3.  **配乐选择**：
    - **简单演示使用默认音乐**。实际项目，应优先检索并推荐 `data/cloud_music_library.csv` 中的相关曲目，或根据视频主题（如“科技”、“温暖”）进行关键词过滤。
    - 询问用户：“我发现了几首符合主题的云端音乐，要不要试试？（如：`Illuminate` - 科技感）”。

## 📦 v6+/v11.x 草稿解密与字幕深度修改 (Draft Crypto & Subtitle Editing)

剪映 6.0+ 对草稿主文件做了加密（`jianying_draft_encrypt_v2`），本 skill 提供完整解密/加密能力，支持**读取、修改、回写**现有草稿。

### 工具：jy_draft_crypto.py

位置：`<SKILL_ROOT>/scripts/jy_draft_crypto.py`

**CLI 用法**：
```bash
# 解密草稿文件到明文 JSON
python jy_draft_crypto.py -d encrypted_draft_content.json -o decrypted.json

# 加密回写（自动 roundtrip 校验）
python jy_draft_crypto.py -e decrypted.json -o encrypted_output.json

# 自动探测剪映安装路径（支持多版本共存）
python jy_draft_crypto.py -d draft_content.json  # 默认输出到同目录 .decrypted.json
```

**Python 库 API**（推荐）：
```python
import sys
sys.path.insert(0, "<SKILL_ROOT>/scripts")
from jy_draft_crypto import decrypt_json, encrypt_json, modify_draft

# 解密为 Python 对象
data = decrypt_json("D:/JianyingPro/Drafts/MyDraft/draft_content.json")

# 直接修改内容（如字幕文本）
data['materials']['texts'][0]['content'] = '{"text":"新内容"}'

# 加密回写（自动 roundtrip 校验）
encrypt_json(data, "D:/JianyingPro/Drafts/MyDraft/draft_content.json")

# 或用 modify_draft 上下文管理器（自动解密→修改→加密）
with modify_draft("draft_content.json") as data:
    data['materials']['texts'][0]['content'] = '{"text":"新内容"}'
# 退出时自动加密回写 + roundtrip 校验
```

**技术细节**：
- 自动探测剪映安装路径（`D:\Program Files\JianyingPro\<版本>\videoeditor.dll`）
- 使用剪映自带 `EncryptUtils::decrypt/encrypt/enable`（复用官方逻辑，不猜算法）
- 加密前必须调用 `enable(true)`
- 每次加密后自动做 roundtrip 校验（解密比对）
- 支持 v11.2.0.14339（实测验证通过）

---

### ⚠️ v11.x 多时间线副本回滚机制（关键！）

剪映 v11+ 的多时间线模式下，草稿存在 **5 处内容副本**，修改草稿必须同步所有位置，否则会被剪映覆盖回滚：

```
草稿根目录/
├── draft_content.json              ← ① 根目录主文件
├── draft_meta_info.json            ← meta（id 不能动，须与索引一致）
├── Timelines/
│   └── <timeline_id>/              ← ② 时间线副本（剪映实际读取源）
│       ├── draft_content.json
│       ├── .bak                   ← ③ 备份快照
│       └── template-2.tmp         ← ④ 临时副本
├── .backup/                        ← ⑤ .bak 快照目录（必须禁用）
│   ├── *.restore.bak
│   └── template.bak
├── project.json                    ← 辅助文件（含 main_timeline_id）
├── timeline_layout.json            ← 辅助文件（含 activeTimeline）
└── draft_biz_config.json           ← 辅助文件（含 timeline 引用）
```

**修改草稿 5 步法（已实测验证）**：
1. **剪映完全退出**（含托盘 `JianyingProTray.exe`）后操作
2. 读取并修改根 `draft_content.json`
3. **content.id 换新 UUID**（复制来的草稿 id 与源相同会导致冲突）
4. **同步写入 5 处**：根文件 + `.bak` + `template-2.tmp` + `Timelines/<新id>/draft_content.json`（目录重命名）+ 副本内 `.bak`/`template-2.tmp`
5. **禁用 `.backup` 目录**：改名为 `.backup.disabled_by_agent`（防止快照回滚）

同步辅助文件：`project.json`（main_timeline_id）、`timeline_layout.json`（activeTimeline）、`draft_biz_config.json`（残留旧 id 清理）。

---

### 🎨 v11.2 字幕属性修改 Schema（实测确认）

**位置/变换**：
- `segment.clip.transform{x, y}` — 归一化坐标，单位 = 半个画布宽/高，y 负值 = 上方
- `segment.clip.rotation` — 旋转角度（度，顺时针）
- `segment.clip.scale{x, y}` — 缩放

**样式（双层，必须同步改）**：
- 素材级：`text_color`、`has_shadow`、`shadow_color/alpha/distance`、`border_width`、`font_path`
- `content.styles[0]`（JSON 字符串）：`fill.content.solid.color`（[r,g,b] 归一化）、`size`、`shadows[0]`、`strokes[]`、`font.path/id`
- `content` 和 `base_content` 为 JSON 字符串，改后需 `json.dumps` 回写且保持一致

**描边 strokes**：
```json
[{
  "content": {
    "solid": {
      "alpha": 1.0,
      "color": [r, g, b]  // 归一化 0-1
    }
  },
  "width": 0.08  // 描边宽度
}]
```

**动画注入**：
- 通过 `segment.extra_material_refs` 引用 `materials.material_animations` 条目 id
- 动画条目格式（v11.2 实际格式）：
```json
{
  "id": "uuid",
  "type": "sticker_animation",
  "animations": [{
    "id": "resource_id",
    "type": "in|out",
    "duration": 微秒,
    "path": "Cache/effect/<resource_id>/<hash>",
    "resource_id": "...",
    "third_resource_id": "0",
    "source_platform": 1,
    "name": "动画名",
    "category_id": "ruchang|3341",
    "category_name": "入场|出场",
    "material_type": "sticker",
    "request_id": "..."
  }]
}
```
- **path 必须指向本地已缓存资源**（`Cache\effect\<resource_id>\<hash>`），否则不渲染
- pyJianYingDraft 的 animation.py 导出格式（带 `multi_language_current`/`platform`/`anim_adjust_params`、无 `path`）与 v11.2 实际格式**不同**，注入时须按真实格式改写

**已验证可用文本动画资源**：
| 动画名 | resource_id |
|---|---|
| 打字机I | 6724920249654710791 |
| 渐显 | 6724916044072227332 |
| 放大 | 6724919499042066958 |
| 弹入 | 6887482184844710413 |
| 缩小 | 6724921217721045515 |
| 向上翻转 | 7194703971498332727 |
| 渐隐（出场） | 6798320902548230669 |

---

##  规则指南 (Rules)

Read the individual rule files for specific tasks and constraints:

- [rules/setup.md](rules/setup.md) - **Mandatory** initialization code for all scripts.
- [rules/core.md](rules/core.md) - Core operations: Saving, Exporting, and Draft management.
- [rules/cli.md](rules/cli.md) - CLI contracts and machine-readable output conventions.
- [rules/media.md](rules/media.md) - Importing assets & **AI Video Analysis Optimization (30m/360p)**.
- [rules/text.md](rules/text.md) - Adding Subtitles, Text, and Captions.
- [rules/keyframes.md](rules/keyframes.md) - **Advanced**: Adding Keyframe animations.
- [rules/effects.md](rules/effects.md) - Searching for and applying Filters, Effects, and Transitions.
- [rules/recording.md](rules/recording.md) - **New**: Screen Recording & Smart Zoom automation.
- [rules/web-vfx.md](rules/web-vfx.md) - Advanced: Web-to-Video generation.
- [rules/generative.md](rules/generative.md) - Chain of Thought for generative editing.
- [rules/audio-voice.md](rules/audio-voice.md) - **New**: TTS Voiceover & BGM sourcing.

## 🎯 Agent Quick Routing

- 云端视频 + 云端音乐：`rules/media.md` + `rules/audio-voice.md` -> `examples/cloud_video_music_tts_demo.py`
- 智能配音与字幕 (Script-to-Video)：`rules/text.md` + `rules/audio-voice.md` -> 核心 API `add_narrated_subtitles`
- 旁白与字幕对齐：`rules/text.md` + `rules/audio-voice.md` -> `examples/cloud_video_music_tts_demo.py`
- 录屏与智能变焦：`rules/recording.md` -> `tools/recording/recorder.py`
- 批量导出/无头导出：`rules/core.md` + `rules/cli.md` -> `examples/robust_auto_export.py`
- 影视解说生成：`rules/generative.md` -> `scripts/movie_commentary_builder.py`

## 📖 经典示例 (Examples)

Refer to these for complete workflows:
- [examples/my_first_vlog.py](examples/my_first_vlog.py) - A complete vlog creation demo with background music and animated text.
- [examples/simple_clip_demo.py](examples/simple_clip_demo.py) - Quick-start tutorial for basic cutting and track management.
- [examples/compound_clip_demo.py](examples/compound_clip_demo.py) - **New**: Professional nested project (Compound Clip) automation.
- [examples/cloud_video_music_tts_demo.py](examples/cloud_video_music_tts_demo.py) - Cloud video + cloud BGM + TTS/subtitle alignment.
- [examples/web_to_video_intro_demo.py](examples/web_to_video_intro_demo.py) - Web-to-Video intro demo (HTML animation -> timeline clip).
- [examples/robust_auto_export.py](examples/robust_auto_export.py) - Stable export workflow and failure handling.
- [examples/auto_exposure_align_demo.py](examples/auto_exposure_align_demo.py) - CV-assisted exposure alignment workflow.
- [examples/video_transcribe_and_match.py](examples/video_transcribe_and_match.py) - **Advanced**: AI-driven workflow (Transcribe Video -> Match B-Roll via AI semantics -> Assemble Draft).

## 🧠 提示词与集成工具 (Prompts & Integrated Tools)

Use these templates and scripts for complex tasks:
- **Asset Search**: Find filters, transitions, and animations by Chinese/English name:
  ```bash
  python <SKILL_ROOT>/scripts/asset_search.py "复古" -c filters
  ```
- **Movie Commentary Builder**: Generate 60s commentary videos from a storyboard JSON:
  ```bash
  python <SKILL_ROOT>/scripts/movie_commentary_builder.py --video "video.mp4" --json "storyboard.json"
  ```
- **Sync Native Assets**: Import your favorited/played BGM/Styles from JianYing App to the Skill:
  ```bash
  python <SKILL_ROOT>/scripts/sync_jy_assets.py
  # Index cloud materials from your existing drafts
  python <SKILL_ROOT>/scripts/build_cloud_music_library.py
  python <SKILL_ROOT>/scripts/build_cloud_text_styles_library.py
  ```
- **README to Tutorial**: Convert a project's README.md into a full installation tutorial video script:
  - Read prompt: `prompts/readme_to_tutorial.md`
  - Inject content into `{{README_CONTENT}}` variable
- **Screen Recorder & Smart Zoom**: Record your screen and auto-apply zoom keyframes:
  ```bash
  python <SKILL_ROOT>/tools/recording/recorder.py
  # Web preview capture (high performance)
  python <SKILL_ROOT>/scripts/web_recorder.py --url "http://localhost:3000" --duration 5
  # Or apply zoom to existing video:
  python <SKILL_ROOT>/scripts/jy_wrapper.py apply-zoom --name "Project" --video "v.mp4" --json "e.json"
  ```
- **Draft Inspector**: Examine draft structure and metadata (v5.9+ support):
  ```bash
  python <SKILL_ROOT>/scripts/draft_inspector.py list --limit 20
  python <SKILL_ROOT>/scripts/draft_inspector.py summary --name "DraftName"
  ```
- **Auto Exporter**: Headless export of a draft to MP4/SRT:
  ```bash
  python <SKILL_ROOT>/scripts/auto_exporter.py "DraftName" "output.mp4" --res 1080 --fps 60
  # For SRT only:
  python <SKILL_ROOT>/scripts/jy_wrapper.py export-srt --name "DraftName"
  ```
- **Draft Crypto (v6+/v11.x)**: 解密/加密/修改剪映加密草稿：
  ```bash
  # 解密草稿到明文 JSON
  python <SKILL_ROOT>/scripts/jy_draft_crypto.py -d "D:/JianyingPro/Drafts/MyDraft/draft_content.json" -o decrypted.json
  
  # 加密回写（自动 roundtrip 校验）
  python <SKILL_ROOT>/scripts/jy_draft_crypto.py -e decrypted.json -o encrypted.json
  ```
- **Template Clone & Replacer**: 安全克隆模板并批量替换物料 (防止损坏原模板):
  ```bash
  # 克隆模板生成新项目
  python <SKILL_ROOT>/scripts/jy_wrapper.py clone --template "酒店模板" --name "客户A_副本"
  ```
- **API Validator**: Run a quick diagnostic of your environment:
  ```bash
  python <SKILL_ROOT>/scripts/api_validator.py
  ```

## 🚀 快速开始示例

```python
import os
import sys

# 1. 环境初始化 (必须同步到脚本开头，支持 Win/Mac)
current_dir = os.path.dirname(os.path.abspath(__file__))
env_root = os.getenv("JY_SKILL_ROOT", "").strip()
# 探测 Skill 路径 (支持 Antigravity, Trae, Claude 等)
skill_root = next((p for p in [
    env_root,
    os.path.join(current_dir, ".agent", "skills", "jianying-editor"),
    os.path.join(current_dir, ".trae", "skills", "jianying-editor"),
    os.path.join(current_dir, ".claude", "skills", "jianying-editor"),
    os.path.join(current_dir, "skills", "jianying-editor"),
    os.path.abspath(".agent/skills/jianying-editor"),
    os.path.abspath(".trae/skills/jianying-editor"),
    os.path.abspath(".claude/skills/jianying-editor"),
    os.path.abspath("skills/jianying-editor"),
    os.path.dirname(current_dir)
] if p and os.path.exists(os.path.join(p, "scripts", "jy_wrapper.py"))), None)

if not skill_root: raise ImportError("Could not find jianying-editor skill root.")
sys.path.insert(0, os.path.join(skill_root, "scripts"))
from jy_wrapper import JyProject

if __name__ == "__main__":
    # 2. 初始化工程 (支持 v5.9+ 及自修复)
    project = JyProject("New AI Video", overwrite=True)
    assets_dir = os.path.join(skill_root, "assets")

    # 3. 智能配音与字幕 (One-click Script-to-Video)
    project.add_narrated_subtitles(
        text="欢迎使用剪映自动化 Skill。这是一个全面适配 MacOS 的进阶版本。",
        speaker="zh_female_xiaopengyou"
    )

    # 4. 导入额外素材
    project.add_media_safe(os.path.join(assets_dir, "video.mp4"), "0s")
    project.add_media_safe(os.path.join(assets_dir, "audio.mp3"), "0s", track_name="Audio")

    # 5. 添加带动画的标题
    project.add_text_simple("剪映自动化开启", start_time="1s", duration="3s", anim_in="复古打字机")

    project.save()
```

## 🛠️ 初始化与项目规范 (Initialization & Project Rules)

在初始化 `JyProject` 时，请务必根据主视频素材的比例设置分辨率。**默认值为横屏 (1920x1080)**。

### 🚨 脚本存放位置规范
**禁止在 Skill 安装目录下创建你的业务剪辑脚本**。
- **正确做法**：将你的剪辑 Python 脚本放在项目的根目录。
- **原因**：Skill 目录应该只包含工具集源码，便于后续 `git pull` 升级。业务代码混入会导致版本管理混乱。
