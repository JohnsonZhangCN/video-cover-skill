# video-cover-skill

[![Tests](https://github.com/JohnsonZhangCN/video-cover-skill/actions/workflows/tests.yml/badge.svg)](https://github.com/JohnsonZhangCN/video-cover-skill/actions/workflows/tests.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](requirements.txt)

**给 Claude Code / Codex 一个视频标题和本地视频，一起做完横竖两张封面。**

做完视频，还要来回找画面、裁比例、排标题。我把这一步也整理成了一个 Skill：AI 看原片、选画面，再调用本地脚本排版。默认只放主标题，保留视频原来的角色和画风。

```text
/video-cover 标题="爱你" 视频="D:/videos/爱你.mp4"
```

<table>
  <tr><th>横版 4:3</th><th>竖版 3:4</th></tr>
  <tr>
    <td align="center"><img src="docs/images/aini-landscape-4x3.jpg" width="440" alt="爱你横版封面：粉橙方块角色与水彩小镇"></td>
    <td align="center"><img src="docs/images/aini-portrait-3x4.jpg" width="330" alt="爱你竖版封面：完整保留角色、小花和四肢"></td>
  </tr>
</table>

上图为真实生成结果，素材来自我用 [music-mv-skill](https://github.com/JohnsonZhangCN/music-mv-skill) 制作的《爱你》动画。封面使用原片画面排版，没有重画角色。仓库不包含歌曲、歌词或原视频。

[下载安装包](https://github.com/JohnsonZhangCN/video-cover-skill/releases/latest) · [安装指南](docs/INSTALL.md) · [底层参数](skills/video-cover/references/production.md)

## 会做什么

- 从视频抽取候选画面，交给 AI 查看，避开黑场、模糊转场、片尾和原有字幕。
- 为横竖比例分别构图，保留主体的脸、标志物与重要手脚，不简单地从横图正中硬裁一张竖图。
- 优先将标题融入原画留白；空间不足时使用独立标题区，保护主体完整。
- 只放主标题，自动拆行，检查小屏可读性，不擅自添加小字副标题。
- 本地完成抽帧与排版，不覆盖原视频和已有成品，不调用外部图像生成 API。
- 直接连续制作到两张成品，内部检查使用同一批素材，不要求先确认独立 demo。

默认横版 **4:3 / 1440×1080**，竖版 **3:4 / 1080×1440**。这是项目预设，各平台实际比例以发布页要求为准。也可以指定 16:9 / 9:16 等比例。

## 安装

1. 从 [Releases](https://github.com/JohnsonZhangCN/video-cover-skill/releases/latest) 下载 `video-cover-skill-v0.1.0.zip`，解压。
2. 把其中的 **`video-cover` 整个文件夹**放到下表的位置。如果下载的是仓库源码 ZIP，对应文件夹位于 `skills/video-cover`。
3. 从自己的项目打开或重新打开 AI 助手会话，再调用技能。

| 工具 | 当前项目内的位置 | 调用 |
| --- | --- | --- |
| Claude Code | `.claude/skills/video-cover/SKILL.md` | `/video-cover` |
| Codex | `.agents/skills/video-cover/SKILL.md` | `$video-cover` |

请复制整个文件夹，脚本、参考说明、字体及字体许可都需要保留。技能安装目录与视频所在目录可以不同。

运行环境：**Python 3.10+、Pillow 10+、FFmpeg 和 ffprobe**。中文字体已附带，无需图像服务密钥。首次环境设置见 [安装指南](docs/INSTALL.md)。

## 常用写法

最少只需标题和视频路径，包含空格的路径用引号包住：

```text
/video-cover 标题="今天把小螃蟹做成了动画" 视频="D:/my videos/clip.mp4"
```

指定常见宽屏和竖屏比例：

```text
/video-cover 标题="爱你" 视频="D:/videos/爱你.mp4" 横比例="16:9" 竖比例="9:16"
```

追加风格和输出目录：

```text
/video-cover 标题="用AI做一支MV" 视频="D:/videos/clip.mp4" 风格="甜美、俏皮，沿用原片水彩墨线" 输出="D:/covers/episode-01"
```

Codex 中把开头换成 `$video-cover`。也支持自然语言说明。比例、风格和输出目录由 AI 解析，再传给脚本，不是额外的必填项。

默认输出在当前项目 `outputs/video-cover/` 下的新目录：两张 JPEG 成品，以及记录原片时间、尺寸和裁切方式的 `cover.json`。候选帧与手机缩略图保存在 `.cache/`，最终只展示两张成品。

## 它怎样工作

```text
视频标题 + 本地视频
       |
       v
FFmpeg 抽帧 -> AI 看图选帧、确定主体和排版
                           |
                           v
                  Pillow 分别制作横竖封面
                           |
                           v
                  原尺寸 + 手机缩略图检查
```

这是给 AI 助手使用的技能，AI 需要能读取本地文件并查看图片。脚本本身不理解故事，也不会从技术评分自动判断“最好看的一帧”。候选帧评分只辅助发现曝光或细节异常。

动画沿用角色和画风，真人与教程按实际内容处理。风格参数用于指导选帧、字体、配色和构图；本地排版器不能把实拍变成水彩画，也不能补出原片没有的清晰细节。

## 当前边界

- 当前实片案例为二维动画；真人、录屏等内容可沿用流程，但尚未建立大量案例验证。
- 标题过长时先拆行。仍无法清楚呈现时，会请你提供更短的封面标题，不偷偷删字。
- 主体无法完整放进指定比例时优先完整缩放入画，可能保留背景留白；不会虚构被裁掉的身体。
- 本地脚本不额外消耗图像 API 费用，Claude Code / Codex 的模型调用仍使用你自己的服务与额度。

## 开发与验证

```text
python -m pip install -r requirements.txt
python -X utf8 -m unittest discover -s tests -p test_video_cover.py
python scripts/package_skill.py
```

本地已在 Windows / Python 3.14 验证 8 项测试，并检查《爱你》实片成品。GitHub Actions 配置了 Linux / Python 3.10、3.14 测试；以页面上的实际运行结果为准。

```text
skills/video-cover/   可安装技能、排版脚本、中文字体与参数说明
docs/                安装指南与真实封面示例
examples/            底层渲染请求示例
scripts/             发布包构建
tests/               抽帧、裁切、标题边界与防覆盖检查
```

问题反馈与改进建议见 [Contributing](CONTRIBUTING.md)。版本变化见 [Changelog](CHANGELOG.md)。

## 许可与致谢

本项目的代码与文档采用 [MIT](LICENSE)。随附的站酷快乐体保留 [SIL Open Font License 1.1](skills/video-cover/assets/fonts/OFL.txt)，不适用 MIT；示例画面中的第三方权利也不由代码许可授予。详见 [第三方说明](THIRD_PARTY_NOTICES.md)。

感谢 [FFmpeg](https://ffmpeg.org/)、[Pillow](https://pillow.readthedocs.io/) 和 [ZCOOL KuaiLe](https://github.com/googlefonts/zcool-kuaile)。技能安装方式参照 [Claude Code 官方文档](https://code.claude.com/docs/en/skills) 与 [Codex 官方文档](https://learn.chatgpt.com/docs/build-skills)。
