# 视频封面制作参数

## 依赖

运行环境：Python 3.10+、Pillow 10+、可执行的 `ffmpeg` 和 `ffprobe`。中文字体随技能附带，默认不扫描系统字体目录。

已有 Python/Pillow 时直接使用，不为抽帧创建重复环境。若 Pillow 缺失，可在当前项目创建虚拟环境，保持缓存、依赖在项目允许的位置：

```powershell
python -m venv .venv-video-cover
$env:PIP_CACHE_DIR = "$PWD/.cache/pip-video-cover"
.venv-video-cover/Scripts/python.exe -m pip install "Pillow>=10,<13"
```

后续使用该环境的 Python 执行脚本。Linux/macOS 的解释器在 `.venv-video-cover/bin/python`。FFmpeg 缺失时使用系统已有安装方案；用户已提供程序路径时，`prepare` 接受 `--ffmpeg`、`--ffprobe`，渲染 JSON 可传 `ffmpeg`、`ffprobe`。不捆绑大型浏览器或视频生成模型。

## 选帧与构图

`prepare` 默认均匀抽取 12 张候选图，略过片头片尾的一小段；但仍可能采到黑场或片尾，必须看联系表。黑场不等于“极简风”。同一人物跨帧比较表情和姿态，双角色场景检查两者都在画面内。

教程优先展示真实结果或界面重点；真人优先清晰面部；动画沿用角色与线条。不要把内容相近理解成永远使用同一种配色。只在用户要求额外重绘且有合适图像工具时启用生成流程，并遵守该工具的授权和费用要求。

本地排版器默认 `auto`：优先将原画铺满画布，标题放在主体上方的空位，不添加割裂画面的色块。指定主体边界后，自动为每种比例寻找能保留整个边界且不与标题重叠的裁切；无法满足时使用独立标题区，必要时完整缩放原画，不硬切人物。几何空间足够并不代表背景适合排字，必须目视检查标题后方的画面。如果默认布局不理想，可以换帧、换配色、显式使用独立标题区，或基于原素材另行排版，仍须交付准确比例的两张图。

## 请求 JSON

```json
{
  "title": "爱你",
  "video": "D:/videos/爱你.mp4",
  "output": "D:/project/outputs/video-cover/aini-01",
  "time": 45.4,
  "source_crop": [0, 0, 1, 0.88],
  "subject_box": [0.35, 0.28, 0.70, 0.75],
  "ratios": {"landscape": "4:3", "portrait": "3:4"},
  "design": {"layout": "auto", "title_color": "#DF7093", "stroke_color": "#FFF7E8"},
  "portrait": {"time": 45.4},
  "landscape": {"time": 45.4}
}
```

必填：`title`、`video`、`output`。`time` 是**视频文件内的秒数**，不能把歌曲的原始时间直接当作剪辑内时间。缺省用片段中点，仅适合已有明确证据表明中点可用的情况，通常应从联系表主动选择。

- `source_crop`：先移除原画面边缘的字幕/黑边，默认原帧全部范围。
- `subject_box`：包住必须保留的所有主体，包括脸、手脚、花朵、手持物，略留余量。默认不裁任何主体。
- 两种框都为**原帧上的归一化 `[left, top, right, bottom]`**，范围 0 到 1；不是 `[x, y, width, height]`。`subject_box` 必须位于 `source_crop` 内，否则脚本拒绝渲染。
- 横竖构图可分别设置 `time`、`source_crop`、`subject_box`、`layout`、`background`、`title_color`、`stroke_color`，覆盖共享参数。不同帧必须重新测量主体位置。
- `layout` 支持 `auto`、`full-bleed`、`header`。前两者优先整图排字，不能同时保留主体和标题空间时回退为 `header`，实际布局记录在 `cover.json`；`header` 强制使用独立标题区。
- `background` 为可选颜色，默认从原帧上方取色。优先贴合原画，避免肤色被当成背景色时不加检查直接交付。`title_color`、`stroke_color` 必须形成可读对比。
- `font` 为可选的本地字体绝对路径，默认使用随附的站酷快乐体。用户指定字体、品牌系统时优先遵守。
- 默认保存 4:3 和 3:4；可覆盖成 16:9、9:16 等横竖比例，短边 1080。极端比例拒绝执行。

标题使用输入原文自动拆行，不截断内容，不强行把长标题变成巨大的单行字。若三行也无法保持可读，解释并请用户提供更短的封面标题。

## 输出与检查

输出目录中有两张 `cover-landscape-*.jpg` / `cover-portrait-*.jpg`，以及记录来源时间、尺寸、标题行和裁切信息的 `cover.json`。中间帧、联系表和手机缩略图在 `.cache` 下。成品已存在时脚本拒绝覆盖，使用新目录完成修改。

必须同时检查原尺寸与手机缩略图：文字清楚、人物完整、画面不糊、不留大片无效空白、没有无关副标题。特别检查动画角色的小花、触角、耳朵和四肢；“矩形边界未越界”不等于选帧好看。
