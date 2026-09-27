#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成灵树 PWA 图标：192/512/apple-touch (180)"""
import os
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'icons')
os.makedirs(OUT, exist_ok=True)

BG = (245, 242, 234, 255)      # --bg 暖纸色
GREEN = (62, 107, 79, 255)     # --accent 苔绿
DEEP = (47, 83, 64, 255)
GOLD = (201, 162, 39, 255)
SOFT = (231, 238, 229, 255)


def draw(size):
    img = Image.new('RGBA', (size, size), BG)
    d = ImageDraw.Draw(img)
    s = size / 512.0
    # 树干
    d.rounded_rectangle([232*s, 250*s, 280*s, 440*s], radius=14*s, fill=DEEP)
    # 树冠三簇
    d.ellipse([110*s, 120*s, 402*s, 360*s], fill=SOFT)
    d.ellipse([136*s, 140*s, 376*s, 330*s], fill=GREEN)
    d.ellipse([200*s, 70*s, 312*s, 220*s], fill=GREEN)
    d.ellipse([150*s, 190*s, 230*s, 260*s], fill=DEEP)
    d.ellipse([282*s, 190*s, 362*s, 260*s], fill=DEEP)
    # 金色果实
    d.ellipse([300*s, 92*s, 356*s, 148*s], fill=GOLD)
    # 地面
    d.rounded_rectangle([100*s, 434*s, 412*s, 462*s], radius=10*s, fill=(228, 223, 210, 255))
    return img


for size, name in [(192, 'icon-192.png'), (512, 'icon-512.png'), (180, 'apple-touch-icon.png')]:
    draw(size).save(os.path.join(OUT, name))
    print('saved', name)
