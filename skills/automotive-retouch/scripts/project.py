#!/usr/bin/env python3
"""Local inventory, output auditing and comparison layout. No model calls."""
import argparse
import hashlib
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp', '.tif', '.tiff', '.bmp'}


def fresh_destination(path):
    path = Path(path).expanduser().resolve()
    if path.exists():
        raise ValueError(f'Output already exists; choose a new path: {path}')
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def image_info(path):
    with Image.open(path) as im:
        im.load()
        oriented = ImageOps.exif_transpose(im)
        width, height = oriented.size
    return dict(file=str(path.resolve()), width=width, height=height,
                bytes=path.stat().st_size,
                sha256=hashlib.sha256(path.read_bytes()).hexdigest())


def enumerate_images(args):
    root = Path(args.input).expanduser().resolve()
    if not root.is_dir():
        raise ValueError(f'Not a directory: {root}')
    exclusions = [Path(p).expanduser().resolve() for p in args.exclude]
    files = root.rglob('*') if args.recursive else root.iterdir()
    results = []
    for path in sorted(files):
        if not path.is_file() or path.suffix.lower() not in EXTENSIONS:
            continue
        if any(path == ex or ex in path.parents for ex in exclusions):
            continue
        try:
            item = image_info(path)
            item['status'] = 'not_visually_reviewed' if args.command == 'audit' else 'queued'
            results.append(item)
        except (OSError, ValueError) as exc:
            results.append(dict(file=str(path), status='unreadable', error=str(exc)))
    dest = fresh_destination(args.output)
    dest.write_text(json.dumps(dict(items=results), ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'{len(results)} image records -> {dest}')


def compare(args):
    paths = [Path(p).expanduser().resolve() for p in args.images]
    if len(paths) not in (2, 3) or len(args.labels) != len(paths):
        raise ValueError('Supply 2 or 3 existing images and one label per image.')
    if len(set(paths)) != len(paths):
        raise ValueError('Each comparison version must be a distinct file.')
    if args.width < 320 or args.height < 320:
        raise ValueError('Comparison canvas must be at least 320 x 320.')
    missing = [str(p) for p in paths if not p.is_file()]
    if missing:
        raise ValueError('Missing version; no comparison was created: ' + ', '.join(missing))
    dest = fresh_destination(args.output)
    font = ImageFont.truetype(args.font, max(14, round(min(args.width, args.height)*.027))) if args.font else ImageFont.load_default()
    if not args.font and any(not s.isascii() for s in args.labels):
        raise ValueError('Non-ASCII labels require --font pointing to a font with those glyphs.')
    vertical = args.layout == 'vertical'
    cols, rows = (1, len(paths)) if vertical else (len(paths), 1)
    cw, ch = args.width//cols, args.height//rows
    pad = max(12, round(min(cw,ch)*.03))
    title_h = max(36, round(getattr(font, 'size', 14)*1.8))
    canvas = Image.new('RGB', (args.width,args.height), '#171c1e')
    draw = ImageDraw.Draw(canvas)
    for i,(path,label) in enumerate(zip(paths,args.labels)):
        x, y = (i%cols)*cw, (i//cols)*ch
        box = draw.textbbox((0,0),label,font=font)
        if box[2]-box[0] > cw-2*pad:
            raise ValueError(f'Label too wide for its panel: {label}')
        draw.text((x+pad,y+pad),label,font=font,fill='#f4f2ec')
        with Image.open(path) as im:
            fitted=ImageOps.contain(ImageOps.exif_transpose(im).convert('RGB'),(cw-2*pad,ch-title_h-2*pad),Image.Resampling.LANCZOS)
            canvas.paste(fitted,(x+(cw-fitted.width)//2,y+title_h+pad+(ch-title_h-2*pad-fitted.height)//2))
    if dest.suffix.lower() in {'.jpg','.jpeg'}:
        canvas.save(dest,quality=94,subsampling=0)
    elif dest.suffix.lower()=='.png':
        canvas.save(dest)
    else:
        raise ValueError('Output must end in .jpg, .jpeg or .png.')
    print(f'{canvas.width} x {canvas.height} comparison -> {dest}')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    for command in ('inventory','audit'):
        p=sub.add_parser(command)
        p.add_argument('--input',required=True)
        p.add_argument('--output',required=True)
        p.add_argument('--recursive',action='store_true')
        p.add_argument('--exclude',action='append',default=[],help='Directory/file to exclude; repeat as needed.')
        p.set_defaults(run=enumerate_images)
    p=sub.add_parser('compare')
    p.add_argument('--images',nargs='+',required=True)
    p.add_argument('--labels',nargs='+',required=True)
    p.add_argument('--output',required=True)
    p.add_argument('--font')
    p.add_argument('--layout',choices=['horizontal','vertical'],default='horizontal')
    p.add_argument('--width',type=int,default=1600)
    p.add_argument('--height',type=int,default=900)
    p.set_defaults(run=compare)
    args=parser.parse_args()
    try:
        args.run(args)
    except (OSError,ValueError) as exc:
        parser.exit(2,f'Error: {exc}\n')


if __name__=='__main__':
    main()
