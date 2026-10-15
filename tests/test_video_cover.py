import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'skills' / 'video-cover' / 'scripts' / 'video_cover.py'
FONT = ROOT / 'skills' / 'video-cover' / 'assets' / 'fonts' / 'ZCOOLKuaiLe-Regular.ttf'


def load_module():
    spec = importlib.util.spec_from_file_location('video_cover', SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CoverWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.scratch = ROOT / '.test-tmp'
        cls.scratch.mkdir(exist_ok=True)
        cls.temp = tempfile.TemporaryDirectory(dir=cls.scratch)
        cls.work = Path(cls.temp.name)
        cls.video = cls.work / '片段 with spaces ; dollar$.mp4'
        subprocess.run([
            shutil.which('ffmpeg'), '-v', 'error', '-f', 'lavfi', '-i',
            'testsrc2=size=640x360:rate=12:duration=2', '-c:v', 'libx264',
            '-pix_fmt', 'yuv420p', '-y', str(cls.video),
        ], check=True, capture_output=True)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def run_cli(self, *args):
        return subprocess.run([sys.executable, str(SCRIPT), *map(str, args)],
                              capture_output=True, text=True, encoding='utf8')

    def test_prepare_then_render_only_two_final_images(self):
        output = self.work / 'covers'
        result = self.run_cli('prepare', '--video', self.video, '--output', output, '--count', 4)
        self.assertEqual(result.returncode, 0, result.stderr)
        analysis = json.loads((output / '.cache' / 'analysis.json').read_text(encoding='utf8'))
        self.assertEqual(len(analysis['candidates']), 4)
        self.assertTrue((output / '.cache' / 'contact-sheet.jpg').is_file())
        request = self.work / 'request.json'
        request.write_text(json.dumps({
            'title': '用 AI 把日常变成动画', 'video': str(self.video),
            'output': str(output), 'time': 0.8, 'subject_box': [.28, .2, .72, .85],
        }, ensure_ascii=False), encoding='utf8')
        result = self.run_cli('render', '--request', request)
        self.assertEqual(result.returncode, 0, result.stderr)
        files = sorted(p.name for p in output.glob('*.jpg'))
        self.assertEqual(files, ['cover-landscape-4x3.jpg', 'cover-portrait-3x4.jpg'])
        for name, expected in [('landscape-4x3', (1440, 1080)), ('portrait-3x4', (1080, 1440))]:
            with Image.open(output / f'cover-{name}.jpg') as image:
                self.assertEqual(image.size, expected)
        manifest = json.loads((output / 'cover.json').read_text(encoding='utf8'))
        self.assertEqual(manifest['title'], '用 AI 把日常变成动画')
        self.assertEqual(len(manifest['covers']), 2)
        before = {p.name: p.read_bytes() for p in output.glob('*.jpg')}
        result = self.run_cli('render', '--request', request)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(before, {p.name: p.read_bytes() for p in output.glob('*.jpg')})

    def test_missing_video_creates_no_output(self):
        output = self.work / 'must not exist'
        result = self.run_cli('prepare', '--video', self.work / 'missing.mp4', '--output', output)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(output.exists())

    def test_crop_preserves_subject_near_edges(self):
        module = load_module()
        box = (.71, .14, .98, .92)
        crop = module.subject_crop((1920, 1080), box, .9)
        self.assertIsNotNone(crop)
        left, top, right, bottom = crop
        self.assertTrue(0 <= left < right <= 1920)
        self.assertTrue(0 <= top < bottom <= 1080)
        self.assertLessEqual(left, box[0] * 1920)
        self.assertGreaterEqual(right, box[2] * 1920)
        self.assertLessEqual(top, box[1] * 1080)
        self.assertGreaterEqual(bottom, box[3] * 1080)

    def test_wide_subject_uses_contain_instead_of_cutting_it(self):
        module = load_module()
        self.assertIsNone(module.subject_crop((1920, 1080), (0, 0, 1, 1), .75))

    def test_long_chinese_and_latin_title_stays_inside_its_box(self):
        module = load_module()
        for title in ['我用AI给两只小螃蟹拍了支《爱你》MV', 'ClaudeCodeWithAVeryLongUnbrokenName 自动生成视频封面']:
            lines, font = module.fit_title(title, FONT, (900, 330), 190, 36, 3)
            self.assertLessEqual(len(lines), 3)
            for line in lines:
                bbox = font.getbbox(line, stroke_width=4)
                self.assertLessEqual(bbox[2] - bbox[0], 900)
            self.assertEqual(''.join(''.join(lines).split()), ''.join(title.split()))

    def test_rejects_trim_that_would_remove_a_subject(self):
        module = load_module()
        with self.assertRaises(ValueError):
            module.source_region((1000, 600), (0, 0, 1, .5), (.2, .3, .8, .9))

    def test_full_bleed_layout_keeps_subject_below_title(self):
        module = load_module()
        frame = Image.new('RGB', (1920, 1080), '#AFCBD3')
        for size in [(1440, 1080), (1080, 1440)]:
            canvas, details = module.compose(frame, '爱你', size, {
                'layout': 'full-bleed', 'subject_box': [.40, .35, .655, .61],
            }, FONT)
            self.assertEqual(canvas.size, size)
            self.assertEqual(details['art_bounds'], [0, 0, *size])
            self.assertLess(details['title_bounds'][3], details['subject_bounds'][1])
            self.assertGreaterEqual(details['subject_bounds'][0], 0)
            self.assertLessEqual(details['subject_bounds'][2], size[0])
            self.assertLessEqual(details['subject_bounds'][3], size[1])

    def test_full_bleed_falls_back_when_a_wide_subject_cannot_fit(self):
        module = load_module()
        frame = Image.new('RGB', (1920, 1080), '#AFCBD3')
        _, details = module.compose(frame, '测试', (1080, 1440), {
            'layout': 'full-bleed', 'subject_box': [0, 0, 1, 1],
        }, FONT)
        self.assertEqual(details['layout'], 'header')
        self.assertEqual(details['fit'], 'contain')


if __name__ == '__main__':
    unittest.main()
