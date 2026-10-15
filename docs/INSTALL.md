# 视频双封面 Skill 安装指南

## 1. 下载与放置

从 https://github.com/JohnsonZhangCN/video-cover-skill/releases/latest 下载版本安装包并解压。

- **版本安装包**：使用解压后的 `video-cover` 文件夹。
- **GitHub 源码 ZIP / Git 克隆**：使用仓库中的 `skills/video-cover` 文件夹。

复制整个文件夹到自己的项目，不能只复制 `SKILL.md`：

| 工具 | 安装后的文件位置 |
| --- | --- |
| Claude Code | `你的项目/.claude/skills/video-cover/SKILL.md` |
| Codex | `你的项目/.agents/skills/video-cover/SKILL.md` |

从该项目打开 AI 助手。已有会话未发现新技能时，重新打开会话。Claude Code 使用 `/video-cover`，Codex 使用 `$video-cover`。

## 2. 准备运行环境

需要 Python 3.10+、Pillow 10+、FFmpeg 和 ffprobe。已有环境可直接复用，不必为每次做封面重新安装。中文字体已在技能中附带。

检查命令：

```text
python --version
ffmpeg -version
ffprobe -version
python -c "from PIL import Image; print(Image.__version__)"
```

Python 官方下载：https://www.python.org/downloads/

FFmpeg 官方下载与各系统构建入口：https://ffmpeg.org/download.html

在 Windows 中将解压后的 FFmpeg `bin` 目录加入当前环境的 PATH，重新打开终端，确认上面的两个程序可用。也可以直接告诉 AI `ffmpeg.exe` 和 `ffprobe.exe` 的绝对路径，无需修改全局 PATH。

如果只缺少 Pillow，可在项目内创建虚拟环境。Windows PowerShell：

```powershell
python -m venv .venv-video-cover
$env:PIP_CACHE_DIR = "$PWD/.cache/pip-video-cover"
.venv-video-cover/Scripts/python.exe -m pip install "Pillow>=10,<13"
```

macOS / Linux 对应解释器是 `.venv-video-cover/bin/python`。告诉 AI 使用这个环境即可；不需要激活环境，也不需要安装其他图像生成服务。

## 3. 调用

```text
/video-cover 标题="爱你" 视频="D:/videos/爱你.mp4"
```

可选：

```text
/video-cover 标题="我的第一支AI动画" 视频="D:/my videos/clip.mp4" 横比例="16:9" 竖比例="9:16" 输出="D:/covers/episode-01"
```

默认横版 4:3 / 1440×1080、竖版 3:4 / 1080×1440，只放主标题。AI 会内部检查候选帧和排版，连续交付两张成品。出现真实报错、缺少权限或标题确实无法清楚呈现时，会说明原因。

## 常见问题

**没有 `/video-cover`？** 确认从安装所在项目打开 Claude Code，且目录没有多嵌套一层。文件应直接位于 `.claude/skills/video-cover/SKILL.md`。

**脚本生成的封面和预期风格不同？** 本地排版保留视频原画。风格参数指导标题、颜色和构图，不会自动把视频变成另一种画风。可要求 AI 换帧、调整字体或重新排版。

**能只给视频，不给标题吗？** 这版以你提供的标题为准，避免 AI 擅自拟题。标题和视频路径是两个必填项。

**会把视频发到图像服务吗？** 随附脚本只在本地读视频、抽帧和排版，不调用外部图像 API。AI 助手查看图片时仍遵循你选择的模型服务与配置，这不等于完全离线。

**能补出原片被切掉的手脚吗？** 不能。AI 会先选择更完整的帧，无法保留时说明素材限制。
