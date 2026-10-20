# -*- coding: utf-8 -*-
"""Pass-2: apply audited terminology fixes to zh-TW files, re-validate in place."""
import re
import yaml

BASE = r'E:/Program Files/AI_Projects/CorentinTh'
FILES = [
    BASE + '/it-tools-fork/locales/zh-TW.yml',
    BASE + '/it-tools-fork/src/tools/fstab-generator/locales/zh-TW.yml',
]
# order matters; every replacement is CJK->CJK so CJK-Latin glue stays untouched
TABLE = [
    ('原始原始碼', '原始碼'),      # s2twp seam: 還原原始原始碼
    ('佔點陣圖', '佔位圖'),        # s2twp hit 位图 inside 占位图
    ('許可權', '權限'),            # s2twp overreach; TW software says 權限
    ('攝像頭', '攝影機'),
    ('轉義', '跳脫'),              # 反轉義 -> 反跳脫 falls out
    ('超時', '逾時'),
    ('倒計時', '倒數計時'),
    ('檢測器', '偵測器'),
    ('分隔符字元', '分隔字元'),    # before the generic rule below
    ('分隔符', '分隔符號'),
]

# Only quality-related UI values use 品質. Physical mass and BMI retain 質量.
# Match YAML key paths rather than replacing the same spelling across the file.
QUALITY_KEYS = {
    'tools.crop-image.texts.image-quality',
    'tools.color-contrast-checker.texts.label-contrast-quality',
    'tools.image-converter.texts.label-output-quality',
    'tools.image-exif-reader.title',
    'tools.image-exif-reader.description',
    'tools.image-exif-reader.texts.title-jpeg-quality',
    'tools.image-exif-reader.texts.label-jpeg-quality',
    'tools.pdf-compressor.texts.label-printer-high-quality',
    'tools.pdf-compressor.texts.label-prepress-best-quality',
    'tools.pdf-compressor.texts.label-compression-quality',
    'tools.pdf-compressor.texts.placeholder-select-compression-quality',
}
MASS_KEYS = {
    'tools.mass-converter.title',
    'tools.mass-converter.description',
    'tools.fitness-computer.description',
}


def fix_quality_terms(text):
    """Replace 質量 only within reviewed quality values; preserve YAML formatting."""
    edits = []

    def visit(node, prefix=''):
        if not isinstance(node, yaml.MappingNode):
            return
        for key_node, value_node in node.value:
            key = f'{prefix}.{key_node.value}' if prefix else key_node.value
            if key in QUALITY_KEYS and isinstance(value_node, yaml.ScalarNode):
                start, end = value_node.start_mark.index, value_node.end_mark.index
                raw = text[start:end]
                if '質量' in raw:
                    edits.append((start, end, raw.replace('質量', '品質'), raw.count('質量')))
            else:
                visit(value_node, key)

    visit(yaml.compose(text))
    for start, end, replacement, _ in sorted(edits, reverse=True):
        text = text[:start] + replacement + text[end:]
    return text, sum(count for _, _, _, count in edits)


grand = {}
for path in FILES:
    text = open(path, encoding='utf-8').read()
    counts = {}
    for a, b in TABLE:
        n = text.count(a)
        if n:
            text = text.replace(a, b)
            counts[a] = n
            grand[a] = grand.get(a, 0) + n
    text, quality_count = fix_quality_terms(text)
    if quality_count:
        counts['質量 (quality keys only)'] = quality_count
        grand['質量 (quality keys only)'] = grand.get('質量 (quality keys only)', 0) + quality_count
    with open(path, 'w', encoding='utf-8', newline='') as f:
        f.write(text)
    print(path.split('it-tools-fork')[-1], '->', counts if counts else 'no matches')

print('\ntotal replacements:', grand, 'sum=', sum(grand.values()))

# ---- full revalidation ----
class T(yaml.SafeLoader):
    pass
T.add_constructor('tag:yaml.org,2002:value', lambda l, n: l.construct_scalar(n))


def leaves(d, p=''):
    out = {}
    for k, v in (d or {}).items():
        kp = f'{p}.{k}' if p else str(k)
        out.update(leaves(v, kp)) if isinstance(v, dict) else out.__setitem__(kp, v)
    return out


zh = leaves(yaml.load(open(BASE + '/it-tools-fork/locales/zh.yml', encoding='utf-8'), Loader=T))
fstab_zh = leaves(yaml.load(open(BASE + '/it-tools-fork/src/tools/fstab-generator/locales/zh.yml', encoding='utf-8'), Loader=T))
PH = re.compile(r'\{[^{}]+\}')
ok = True
for path, ref in [(FILES[0], zh), (FILES[1], fstab_zh)]:
    tw = leaves(yaml.load(open(path, encoding='utf-8'), Loader=T))
    miss = len(set(ref) - set(tw))
    extra = len(set(tw) - set(ref))
    ph = sum(1 for k, v in ref.items() if isinstance(v, str)
             and sorted(PH.findall(v)) != sorted(PH.findall(str(tw.get(k, '')))))
    print(f'{path.split("it-tools-fork")[-1]}: keys ref={len(ref)} tw={len(tw)} miss={miss} extra={extra} ph_bad={ph}')
    ok &= miss == 0 and extra == 0 and ph == 0

text = open(FILES[0], encoding='utf-8').read()
tw_base = leaves(yaml.load(text, Loader=T))
quality_bad = [key for key in sorted(QUALITY_KEYS)
               if not isinstance(tw_base.get(key), str) or '品質' not in tw_base[key] or '質量' in tw_base[key]]
mass_bad = [key for key in sorted(MASS_KEYS)
            if not isinstance(tw_base.get(key), str) or '質量' not in tw_base[key] or '品質' in tw_base[key]]
print('quality/mass context check:', {'quality_bad': quality_bad, 'mass_bad': mass_bad})
ok &= not quality_bad and not mass_bad
res = {w: text.count(w) for w in ['許可權', '轉義', '攝像頭', '佔點陣圖', '超時', '倒計時', '檢測器', '演演']}
print('residual check (expect all 0):', res)
dups = re.findall(r'([\u4e00-\u9fff])\1', text)
from collections import Counter
print('doubled bigrams now:', dict(Counter(dups)))
print('ALL OK' if ok and not any(res.values()) else 'FAIL')
