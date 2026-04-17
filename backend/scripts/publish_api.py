#!/usr/bin/env python3
"""OmniPublish — CMS 发布 API 客户端（占位模块）

完整版包含 AES 加密通信、平台登录、图片/视频上传、帖子发布等功能。
请从预装包获取完整版本，覆盖此文件即可使用。
"""

import json, os, re

# ── 加密常量（占位，完整版从 config.json 自动加载） ──
APPKEY = ""
KEY = b""
IV = b""
MEDIA_KEY = b""
MEDIA_IV = b""
BUNDLE_ID = ""
DEFAULT_BASE_URL = ""
PROJECT_LIST_URL = ""


def encrypt_data(plaintext):
    raise NotImplementedError("发布插件未安装，请从预装包获取完整版本")

def decrypt_data(ciphertext):
    raise NotImplementedError("发布插件未安装，请从预装包获取完整版本")


class RemotePublishClient:
    """CMS 平台 API 客户端（占位）。完整版支持加密通信、自动登录、图片/视频上传等。"""

    MIN_REQUEST_INTERVAL = 1.0

    def __init__(self, base_url=""):
        self.base_url = base_url.rstrip("/")
        self.token = None
        self.projects = []
        self.current_project = None
        self.project_code = None
        self._api_base = None
        self._credentials = None
        self._site_config = None
        self._config_result = None

    @property
    def api_base(self):
        if self._api_base:
            return self._api_base
        if not self.current_project:
            raise RuntimeError("No project selected.")
        apis = self.current_project.get("api", [])
        if not apis:
            raise RuntimeError("Project has no API URLs")
        import random
        self._api_base = random.choice(apis)
        return self._api_base

    def get_projects(self):
        raise NotImplementedError("发布插件未安装，请从预装包获取完整版本")

    def select_project(self, project_code=None):
        raise NotImplementedError("发布插件未安装，请从预装包获取完整版本")

    def login(self, username, password):
        raise NotImplementedError("发布插件未安装，请从预装包获取完整版本")

    def resolve_category_id(self, category_name):
        raise NotImplementedError("发布插件未安装，请从预装包获取完整版本")

    def upload_image(self, image_path):
        raise NotImplementedError("发布插件未安装，请从预装包获取完整版本")

    def upload_video(self, video_path, cover_url=None, display_name=None):
        raise NotImplementedError("发布插件未安装，请从预装包获取完整版本")

    def get_mv_list(self):
        raise NotImplementedError("发布插件未安装，请从预装包获取完整版本")

    def find_video_by_mp4(self, mp4_url):
        raise NotImplementedError("发布插件未安装，请从预装包获取完整版本")

    def publish_post(self, title, body, cover_url="", category_id="",
                     tags="", keyword="", desc="", is_draft=3, raw_tags=False):
        raise NotImplementedError("发布插件未安装，请从预装包获取完整版本")


# ═══════════════════════════════════════════════════════════════════════
# 以下为非敏感工具函数，完整保留
# ═══════════════════════════════════════════════════════════════════════

def _normalize_tags(s):
    if not s:
        return ""
    s = s.replace("#", ",").replace("\uff0c", ",")
    return ",".join(p.strip() for p in s.split(",") if p.strip())


def parse_txt_file(txt_path):
    """解析文案 TXT 文件，提取标题/作者/分类/关键词/正文段落。"""
    with open(txt_path, "r", encoding="utf-8") as f:
        content = f.read()

    meta = {"title": "", "author": "", "category": "", "keywords": "", "sections": []}
    lines = content.strip().split("\n")
    body_start = 0

    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("title:") or stripped.startswith("标题:"):
            meta["title"] = stripped.split(":", 1)[1].strip()
        elif stripped.startswith("author:") or stripped.startswith("作者:"):
            meta["author"] = stripped.split(":", 1)[1].strip()
        elif stripped.startswith("category:") or stripped.startswith("分类:"):
            meta["category"] = stripped.split(":", 1)[1].strip()
        elif stripped.startswith("keywords:") or stripped.startswith("关键词:"):
            meta["keywords"] = stripped.split(":", 1)[1].strip()
        elif stripped == "":
            body_start = i + 1
            break
        body_start = i + 1

    current_heading = ""
    current_paragraphs = []
    for line in lines[body_start:]:
        stripped = line.strip()
        if stripped.startswith("## "):
            if current_paragraphs or current_heading:
                meta["sections"].append({"h": current_heading, "p": "\n".join(current_paragraphs)})
            current_heading = stripped[3:].strip()
            current_paragraphs = []
        elif stripped:
            current_paragraphs.append(stripped)
    if current_paragraphs or current_heading:
        meta["sections"].append({"h": current_heading, "p": "\n".join(current_paragraphs)})
    return meta


def _video_tag(video_url, poster=""):
    """Generate platform-compatible DPlayer shortcode."""
    pic_attr = f' pic="{poster}"' if poster else ''
    return f'[dplayer url="{video_url}"{pic_attr} /]'


def build_markdown(meta, image_urls, video_entries=None, layout_template=None):
    """构建帖子正文 Markdown。支持自定义排版模板。"""
    video_entries = video_entries or []

    if not layout_template:
        md_parts = []
        img_idx = 0
        for sec in meta["sections"]:
            if sec["h"]:
                md_parts.append(f"## {sec['h']}")
            if sec["p"]:
                md_parts.append(sec["p"])
            for _ in range(3):
                if img_idx < len(image_urls):
                    md_parts.append(f"![img]({image_urls[img_idx]})")
                    img_idx += 1
        while img_idx < len(image_urls):
            md_parts.append(f"![img]({image_urls[img_idx]})")
            img_idx += 1
        for ve in video_entries:
            md_parts.append(_video_tag(ve.get("video_url", ""), ve.get("cover", "")))
        return "\n\n".join(md_parts)

    # Template-based layout
    md = layout_template
    md = re.sub(r'^(正文)$', r'{正文}', md, flags=re.MULTILINE)
    md = re.sub(r'^## 小标题$', r'## {小标题}', md, flags=re.MULTILINE)
    md = re.sub(r'^图片(\d+)-(\d+)$', r'{img:\1-\2}', md, flags=re.MULTILINE)
    md = re.sub(r'^图片(\d+)$', r'{img:\1}', md, flags=re.MULTILINE)
    md = re.sub(r'^视频(\d+)$', r'{vid:\1}', md, flags=re.MULTILINE)
    md = re.sub(r'^视频$', r'{vid:next}', md, flags=re.MULTILINE)

    section_idx = 0
    while "{正文}" in md and section_idx < len(meta["sections"]):
        md = md.replace("{正文}", meta["sections"][section_idx].get("p", ""), 1)
        section_idx += 1
    headings = [s["h"] for s in meta["sections"] if s.get("h")]
    h_idx = 0
    while "{小标题}" in md and h_idx < len(headings):
        md = md.replace("{小标题}", headings[h_idx], 1)
        h_idx += 1

    placed_imgs = set()
    placed_vids = set()
    for match in re.finditer(r'\{img:(\d+)-(\d+)\}', md):
        start, end = int(match.group(1)) - 1, int(match.group(2))
        imgs = [f"![img]({image_urls[i]})" for i in range(start, min(end, len(image_urls)))]
        placed_imgs.update(range(start, min(end, len(image_urls))))
        md = md.replace(match.group(0), "\n\n".join(imgs), 1)
    for match in re.finditer(r'\{img:(\d+)\}', md):
        idx = int(match.group(1)) - 1
        if idx < len(image_urls):
            placed_imgs.add(idx)
            md = md.replace(match.group(0), f"![img]({image_urls[idx]})", 1)
        else:
            md = md.replace(match.group(0), "", 1)

    vid_idx = 0
    for match in re.finditer(r'\{vid:(\w+)\}', md):
        token = match.group(1)
        vi = int(token) - 1 if token.isdigit() else vid_idx
        if vi < len(video_entries):
            ve = video_entries[vi]
            placed_vids.add(vi)
            md = md.replace(match.group(0), _video_tag(ve.get("video_url", ""), ve.get("cover", "")), 1)
            vid_idx = vi + 1
        else:
            md = md.replace(match.group(0), "", 1)

    remaining_imgs = [f"![img]({image_urls[i]})" for i in range(len(image_urls)) if i not in placed_imgs]
    remaining_vids = [_video_tag(ve.get("video_url", ""), ve.get("cover", ""))
                      for i, ve in enumerate(video_entries) if i not in placed_vids]
    if remaining_imgs or remaining_vids:
        md += "\n\n" + "\n\n".join(remaining_imgs + remaining_vids)

    return md.strip()


if __name__ == "__main__":
    print("此为占位模块，完整版请从预装包获取。")
    print("用法：将预装包中的 publish_api.py 覆盖此文件。")
