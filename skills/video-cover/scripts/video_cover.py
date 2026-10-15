"""Extract inspectable frames and compose two covers from original video pixels."""
import argparse
from datetime import datetime
import json
import math
from pathlib import Path
import re
import shutil
import subprocess
import sys

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps, ImageStat


SKILL = Path(__file__).resolve().parents[1]
DEFAULT_FONT = SKILL / 'assets' / 'fonts' / 'ZCOOLKuaiLe-Regular.ttf'


def tool(name, explicit=None):
    resolved = explicit or shutil.which(name)
    if not resolved:
        raise ValueError(f'{name} not found. Install FFmpeg or supply its executable path.')
    return str(resolved)


def run(args):
    result = subprocess.run(args, capture_output=True, timeout=120)
    if result.returncode:
        raise ValueError(result.stderr.decode('utf8', errors='replace')[-2500:])
    return result.stdout


def probe(video, ffprobe=None):
    video = Path(video).expanduser().resolve()
    if not video.is_file():
        raise ValueError(f'Video not found: {video}')
    data = json.loads(run([tool('ffprobe', ffprobe), '-v', 'error', '-select_streams', 'v:0',
                           '-show_streams', '-show_format', '-of', 'json', str(video)]))
    streams = data.get('streams', [])
    if not streams:
        raise ValueError('The file has no readable video stream.')
    stream = streams[0]
    duration = float(data.get('format', {}).get('duration') or stream.get('duration') or 0)
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError('Cannot measure video duration.')
    return {'video': str(video), 'duration': duration, 'width': stream['width'],
            'height': stream['height'], 'bytes': video.stat().st_size}


def extract(video, time, output, ffmpeg=None, max_side=1920):
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    run([tool('ffmpeg', ffmpeg), '-v', 'error', '-ss', f'{time:.6f}', '-i', str(video),
         '-map', '0:v:0', '-frames:v', '1', '-vf',
         f'scale={max_side}:{max_side}:force_original_aspect_ratio=decrease,setsar=1',
         '-q:v', '2', '-y', str(output)])
    if not output.is_file():
        raise ValueError(f'No frame at {time:.3f}s; choose an earlier timestamp.')
    with Image.open(output) as image:
        image.load()
        return image.convert('RGB')


def technical_score(image):
    gray = image.convert('L').resize((320, 180))
    gray = gray.crop((8, 8, 312, 172))
    stats = ImageStat.Stat(gray)
    brightness, contrast = stats.mean[0], stats.stddev[0]
    edges = ImageStat.Stat(gray.filter(ImageFilter.FIND_EDGES)).mean[0]
    exposed = max(0, 1 - abs(brightness - 128) / 128)
    return {'score': round(contrast * .55 + edges * 1.8 + exposed * 12, 3),
            'brightness': round(brightness, 2), 'contrast': round(contrast, 2),
            'low_information': contrast < 5 or brightness < 10 or brightness > 247}


def new_output(video):
    stem = re.sub(r'[^\w\-]+', '-', Path(video).stem, flags=re.UNICODE).strip('-')[:48] or 'video'
    stamp = datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    return Path.cwd() / 'outputs' / 'video-cover' / f'{stem}-{stamp}'


def prepare(video, output=None, count=12, ffmpeg=None, ffprobe=None):
    info = probe(video, ffprobe)
    tool('ffmpeg', ffmpeg)
    if not 4 <= count <= 20:
        raise ValueError('Candidate count must be between 4 and 20.')
    output = Path(output or new_output(video)).resolve()
    cache = output / '.cache'
    if (cache / 'analysis.json').exists():
        raise ValueError('This analysis already exists. Reuse it or choose a new output folder.')
    cache.mkdir(parents=True, exist_ok=True)
    candidates = []
    tiles = []
    font = ImageFont.truetype(str(DEFAULT_FONT), 22)
    for i in range(count):
        time = info['duration'] * (.03 + .90 * i / (count - 1))
        frame_path = cache / 'frames' / f'frame-{i + 1:02d}.jpg'
        frame = extract(info['video'], time, frame_path, ffmpeg, max_side=1280)
        candidate = {'id': i + 1, 'time': round(time, 5), 'file': str(frame_path),
                     'display_size': list(frame.size), **technical_score(frame)}
        candidates.append(candidate)
        tile = Image.new('RGB', (320, 212), '#F4F5F7')
        thumb = ImageOps.contain(frame, (320, 180), Image.Resampling.LANCZOS)
        tile.paste(thumb, ((320 - thumb.width) // 2, (180 - thumb.height) // 2))
        ImageDraw.Draw(tile).text((10, 185), f'{i + 1:02d}   {time:.2f}s', font=font, fill='#222831')
        tiles.append(tile)
    sheet = Image.new('RGB', (1280, math.ceil(count / 4) * 212), '#F4F5F7')
    for i, tile in enumerate(tiles):
        sheet.paste(tile, ((i % 4) * 320, (i // 4) * 212))
    sheet.save(cache / 'contact-sheet.jpg', quality=92)
    valid = [item for item in candidates if not item['low_information']]
    info.update({'output': str(output), 'candidates': candidates,
                 'technical_recommendation': max(valid or candidates, key=lambda item: item['score'])['id'],
                 'note': 'Scores measure exposure/edges only. Visually choose subjects and avoid subtitles or end cards.'})
    (cache / 'analysis.json').write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding='utf8')
    return {'output': str(output), 'analysis': str(cache / 'analysis.json'),
            'contact_sheet': str(cache / 'contact-sheet.jpg')}


def normalized_box(box):
    if len(box) != 4:
        raise ValueError('Boxes use [left, top, right, bottom], normalized to 0..1.')
    box = tuple(float(v) for v in box)
    if not all(math.isfinite(v) for v in box) or not (0 <= box[0] < box[2] <= 1 and 0 <= box[1] < box[3] <= 1):
        raise ValueError('Box must satisfy 0 <= left < right <= 1 and 0 <= top < bottom <= 1.')
    return box


def source_region(size, source_crop=None, subject_box=None):
    region = normalized_box(source_crop or (0, 0, 1, 1))
    subject = normalized_box(subject_box or region)
    if subject[0] < region[0] or subject[1] < region[1] or subject[2] > region[2] or subject[3] > region[3]:
        raise ValueError('source_crop would remove part of subject_box.')
    w, h = size
    pixels = (math.floor(region[0] * w), math.floor(region[1] * h),
              math.ceil(region[2] * w), math.ceil(region[3] * h))
    pw, ph = pixels[2] - pixels[0], pixels[3] - pixels[1]
    relative = ((subject[0] * w - pixels[0]) / pw, (subject[1] * h - pixels[1]) / ph,
                (subject[2] * w - pixels[0]) / pw, (subject[3] * h - pixels[1]) / ph)
    return pixels, tuple(max(0, min(1, v)) for v in relative)


def subject_crop(size, box, aspect, padding=.08):
    w, h = size
    left, top, right, bottom = normalized_box(box)
    bw, bh = (right - left) * w, (bottom - top) * h
    crop_w = max(bw, bh * aspect)
    crop_h = crop_w / aspect
    if crop_w > w + 1e-6 or crop_h > h + 1e-6:
        return None
    grow = min(1 + padding * 2, w / crop_w, h / crop_h)
    crop_w *= grow
    crop_h *= grow
    x = min(max((left + right) * w / 2 - crop_w / 2, 0), w - crop_w)
    y = min(max((top + bottom) * h / 2 - crop_h / 2, 0), h - crop_h)
    return (math.floor(x), math.floor(y), math.ceil(x + crop_w), math.ceil(y + crop_h))


def full_bleed_crop(size, box, aspect, title_fraction):
    w, h = size
    left, top, right, bottom = normalized_box(box)
    left, top, right, bottom = left * w, top * h, right * w, bottom * h
    minimum = max((right - left) / (.78 * aspect), (bottom - top) / .46)
    maximum = min(h, w / aspect)
    if minimum > maximum:
        return None
    # Solve crop bounds while reserving space above the entire subject for text.
    for step in range(17):
        ch = minimum + (maximum - minimum) * step / 16
        cw = ch * aspect
        x0, x1 = max(0, right - cw), min(left, w - cw)
        y0, y1 = max(0, bottom - .95 * ch), min(top - title_fraction * ch, h - ch)
        if x0 > x1 or y0 > y1:
            continue
        x = min(max((left + right - cw) / 2, x0), x1)
        y = min(max((top + bottom) / 2 - .66 * ch, y0), y1)
        return (math.floor(x), math.floor(y), math.ceil(x + cw), math.ceil(y + ch))
    return None


def text_width(text, font, stroke=4):
    bbox = font.getbbox(text, stroke_width=stroke)
    return bbox[2] - bbox[0]


def wrap_title(text, font, width):
    lines = []
    for paragraph in text.splitlines():
        line = ''
        tokens = re.findall(r'[A-Za-z0-9]+|[^A-Za-z0-9]', paragraph)
        for token in tokens:
            pieces = [token] if text_width(token, font) <= width else list(token)
            for piece in pieces:
                candidate = line + piece
                if line and text_width(candidate.rstrip(), font) > width:
                    lines.append(line.rstrip())
                    line = piece.lstrip()
                else:
                    line = candidate.lstrip()
        if line:
            lines.append(line.rstrip())
    return lines


def title_geometry(lines, font):
    boxes = [font.getbbox(line, stroke_width=4) for line in lines]
    gap = round(font.size * .16)
    height = sum(box[3] - box[1] for box in boxes) + gap * max(0, len(lines) - 1)
    return boxes, gap, height


def fit_title(text, font_path, area, max_font, min_font=36, max_lines=3):
    for size in range(max_font, min_font - 1, -2):
        font = ImageFont.truetype(str(font_path), size)
        lines = wrap_title(text, font, area[0])
        if not lines or len(lines) > max_lines:
            continue
        boxes, _, height = title_geometry(lines, font)
        if height <= area[1] and all(box[2] - box[0] <= area[0] for box in boxes):
            return lines, font
    raise ValueError('Title cannot fit legibly in three lines. Supply a shorter cover title.')


def cover_size(ratio, orientation):
    parts = ratio.split(':')
    if len(parts) != 2:
        raise ValueError('Ratio must look like 4:3 or 3:4.')
    a, b = map(int, parts)
    if min(a, b) <= 0 or max(a, b) / min(a, b) > 3:
        raise ValueError('Ratio must be positive and no more extreme than 3:1.')
    if orientation == 'landscape' and a <= b or orientation == 'portrait' and a >= b:
        raise ValueError('Landscape must be wider than tall; portrait must be taller than wide.')
    return (round(1080 * a / b), 1080) if a > b else (1080, round(1080 * b / a))


def sample_background(image):
    w, h = image.size
    strip = image.crop((0, 0, w, max(1, round(h * .08))))
    return tuple(round(v) for v in ImageStat.Stat(strip).median[:3])


def compose(frame, title, size, options, font_path):
    pixels, relative_subject = source_region(frame.size, options.get('source_crop'), options.get('subject_box'))
    art = frame.crop(pixels)
    bg = options.get('background') or sample_background(art)
    canvas = Image.new('RGB', size, bg)
    w, h = size
    inset = round(w * .055)
    lines, font = fit_title(title, font_path, (w - inset * 2, round(h * .27)),
                           round(min(w * .26, h * .22)), max(36, round(w * .035)))
    boxes, gap, text_h = title_geometry(lines, font)
    text_y = round(h * .06)
    title_bottom = text_y + text_h
    layout = options.get('layout', 'auto')
    if layout not in ('auto', 'full-bleed', 'header'):
        raise ValueError('layout must be auto, full-bleed, or header.')
    crop = None if layout == 'header' else full_bleed_crop(
        art.size, relative_subject, w / h, (title_bottom + h * .035) / h)
    source_size = art.size
    if crop is not None:
        layout = 'full-bleed'
        art = art.crop(crop).resize(size, Image.Resampling.LANCZOS)
        origin = (0, 0)
    else:
        layout = 'header'
        art_y = title_bottom + round(h * .045)
        art_size = (w, round(h * .95) - art_y)
        crop = subject_crop(art.size, relative_subject, art_size[0] / art_size[1])
        if crop is not None:
            art = art.crop(crop).resize(art_size, Image.Resampling.LANCZOS)
            origin = (0, art_y)
        else:
            art = ImageOps.contain(art, art_size, Image.Resampling.LANCZOS)
            origin = ((w - art.width) // 2, art_y + (art_size[1] - art.height) // 2)
    canvas.paste(art, origin)
    color_sample = canvas.getpixel((inset, max(0, text_y - 1)))
    light = sum(color_sample) / 3 > 150
    ink = options.get('title_color') or ('#28313E' if light else '#FFF6E6')
    stroke = options.get('stroke_color') or ('#FFF8ED' if light else '#222831')
    draw = ImageDraw.Draw(canvas)
    for line, bbox in zip(lines, boxes):
        x = round((w - (bbox[2] - bbox[0])) / 2 - bbox[0])
        y = text_y - bbox[1]
        draw.text((x + 2, y + 4), line, font=font, fill=stroke, stroke_width=5, stroke_fill=stroke)
        draw.text((x, y), line, font=font, fill=ink, stroke_width=4, stroke_fill=stroke)
        text_y += bbox[3] - bbox[1] + gap
    crop_bounds = crop or (0, 0, *source_size)
    sx = art.width / (crop_bounds[2] - crop_bounds[0])
    sy = art.height / (crop_bounds[3] - crop_bounds[1])
    subject = [origin[0] + (relative_subject[0] * source_size[0] - crop_bounds[0]) * sx,
               origin[1] + (relative_subject[1] * source_size[1] - crop_bounds[1]) * sy,
               origin[0] + (relative_subject[2] * source_size[0] - crop_bounds[0]) * sx,
               origin[1] + (relative_subject[3] * source_size[1] - crop_bounds[1]) * sy]
    return canvas, {'title_lines': lines, 'font_size': font.size,
                    'layout': layout, 'title_bounds': [inset, round(h * .06), w - inset, title_bottom],
                    'subject_bounds': [round(v, 2) for v in subject],
                    'source_crop_pixels': list(pixels), 'subject_crop_pixels': list(crop) if crop else None,
                    'fit': 'subject-preserving-crop' if crop else 'contain',
                    'art_bounds': [origin[0], origin[1], origin[0] + art.width, origin[1] + art.height]}


def render_request(path):
    request = json.loads(Path(path).read_text(encoding='utf-8-sig'))
    title = str(request.get('title', '')).strip()
    if not title or len(title) > 120:
        raise ValueError('Supply a non-empty title of at most 120 characters.')
    info = probe(request['video'], request.get('ffprobe'))
    output = Path(request['output']).expanduser().resolve()
    font = Path(request.get('font') or DEFAULT_FONT)
    if not font.is_file():
        raise ValueError(f'Font not found: {font}')
    ratios = {'landscape': '4:3', 'portrait': '3:4', **request.get('ratios', {})}
    plans = []
    for orientation in ['landscape', 'portrait']:
        options = {**request.get('design', {}), **request.get(orientation, {})}
        for key in ['subject_box', 'source_crop']:
            if key not in options and key in request:
                options[key] = request[key]
        time = float(options.get('time', request.get('time', info['duration'] / 2)))
        if not math.isfinite(time) or not 0 <= time < info['duration']:
            raise ValueError(f'{orientation}: timestamp is outside the video.')
        ratio = ratios[orientation]
        size = cover_size(ratio, orientation)
        destination = output / f"cover-{orientation}-{ratio.replace(':', 'x')}.jpg"
        plans.append((orientation, options, time, size, destination))
    if (output / 'cover.json').exists() or any(plan[4].exists() for plan in plans):
        raise ValueError('Final covers already exist. Choose a new output folder; existing files are preserved.')
    cache = output / '.cache'
    cache.mkdir(parents=True, exist_ok=True)
    covers = []
    prepared = []
    for orientation, options, time, size, destination in plans:
        frame = extract(info['video'], time, cache / f'source-{orientation}.jpg', request.get('ffmpeg'))
        canvas, details = compose(frame, title, size, options, font)
        staging = cache / destination.name
        canvas.save(staging, quality=95, subsampling=0, optimize=True)
        prepared.append((staging, destination))
        covers.append({'orientation': orientation, 'file': str(destination), 'size': list(size),
                       'time': time, **details})
    for staging, destination in prepared:
        staging.rename(destination)
    thumbs = Image.new('RGB', (560, 380), '#FFFFFF')
    for index, cover in enumerate(covers):
        with Image.open(cover['file']) as image:
            image.thumbnail((260, 344), Image.Resampling.LANCZOS)
            thumbs.paste(image, (index * 280 + (280 - image.width) // 2, (380 - image.height) // 2))
    thumbs.save(cache / 'mobile-preview.jpg', quality=94)
    manifest = {**info, 'title': title, 'covers': covers,
                'preview': str(cache / 'mobile-preview.jpg'),
                'method': 'Original video pixels, local composition; no external generation API.'}
    (output / 'cover.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf8')
    return {'covers': [cover['file'] for cover in covers], 'preview': manifest['preview'],
            'manifest': str(output / 'cover.json')}


def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf8')
        sys.stderr.reconfigure(encoding='utf8')
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    prep = commands.add_parser('prepare', help='Extract candidates for visual selection.')
    prep.add_argument('--video', required=True)
    prep.add_argument('--output')
    prep.add_argument('--count', type=int, default=12)
    prep.add_argument('--ffmpeg')
    prep.add_argument('--ffprobe')
    render = commands.add_parser('render', help='Render both covers from a JSON request.')
    render.add_argument('--request', required=True)
    args = parser.parse_args()
    try:
        result = (prepare(args.video, args.output, args.count, args.ffmpeg, args.ffprobe)
                  if args.command == 'prepare' else render_request(args.request))
    except (ValueError, KeyError, OSError, subprocess.TimeoutExpired) as error:
        print(f'Error: {error}', file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
