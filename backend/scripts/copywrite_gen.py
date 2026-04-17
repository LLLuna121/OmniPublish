#!/usr/bin/env python3
"""OmniPublish — AI 文案生成（占位模块）

完整版包含 AI 提示词模板、文风系统、流式 API 调用等功能。
请从预装包获取完整版本，覆盖此文件即可使用。

Prompt 模板目录: scripts/cw_prompts/
"""

import os, re, sys


# ═══════════════════════════════════════════
# Style validation
# ═══════════════════════════════════════════

def _validate_style(style: str) -> str:
    """Sanitize style parameter."""
    if not re.match(r'^[\w\u4e00-\u9fff-]+$', style):
        print(f"[ERROR] Invalid style parameter: {style}", file=sys.stderr)
        sys.exit(1)
    return style


# ═══════════════════════════════════════════
# Prompt loading (placeholder)
# ═══════════════════════════════════════════

def read_txt(path):
    if not os.path.exists(path):
        return ""
    with open(path, "r", encoding="utf-8") as f:
        return f.read().strip()


def build_system_prompt(prompts_dir, style_name):
    """组装 system prompt。完整版从 cw_prompts/ 目录加载底色指令 + 文章结构 + 文风模板。"""
    parts = []
    base = read_txt(os.path.join(prompts_dir, "base_instruction.txt"))
    if base:
        parts.append(base)
    structure = read_txt(os.path.join(prompts_dir, "article_structure.txt"))
    if structure:
        parts.append(structure)
    style = read_txt(os.path.join(prompts_dir, f"style_{style_name}.txt"))
    if style:
        parts.append(f"【本次文风：{style_name}】\n{style}")
    if not parts:
        parts.append("你是一位专业的内容编辑，请根据素材生成文案。")
    return "\n\n".join(parts)


def build_user_prompt(args):
    """组装 user prompt = 素材 + 要求 + 输出格式"""
    category_str = args.category
    if isinstance(category_str, list):
        category_str = ",".join(category_str)

    lines = [
        "请根据以下素材生成文案：",
        "",
        f"【主角】{args.protagonist}",
        f"【事件】{args.event}",
    ]
    if args.photos:
        lines.append(f"【生活照】{args.photos}")
    if args.video_desc:
        lines.append(f"【视频内容描述】{args.video_desc}")

    lines += [
        "",
        "【输出要求】",
        f"标题：{args.title_range}字，吸引点击",
        f"关键词：{args.kw_count}个，英文逗号分隔",
        f"正文：约{args.body_len}字，分{args.paragraphs}段",
    ]

    cats = [c.strip() for c in category_str.split(",") if c.strip()] if category_str else []
    if len(cats) <= 2:
        category_instruction = category_str
    else:
        lines += [
            "",
            "【分类选择】从以下分类中选择2个最匹配的：",
            f"可选分类: {category_str}",
        ]
        category_instruction = "<从上面可选分类中选2个，逗号分隔>"

    lines += [
        "",
        "【输出格式】严格按以下格式输出：",
        f"作者: {args.author}",
        f"分类: {category_instruction}",
        "标题: <标题内容>",
        "关键词: <kw1,kw2,kw3,...>",
        "文案:",
        "<正文内容，段落间空一行>",
    ]
    return "\n".join(lines)


# ═══════════════════════════════════════════
# API 调用（占位）
# ═══════════════════════════════════════════

def call_api(system_prompt, user_prompt, api_base, api_key, model):
    """调用 AI API 生成文案。完整版支持 OpenAI 兼容 + Anthropic 原生协议，流式输出，指数退避重试。"""
    raise NotImplementedError(
        "文案生成插件未安装。请从预装包获取完整的 copywrite_gen.py 和 cw_prompts/ 目录。"
    )


# ═══════════════════════════════════════════
# 结果解析
# ═══════════════════════════════════════════

def parse_result(text, fallback_author, fallback_category):
    """从 AI 输出中解析结构化字段。"""
    result = {
        "author": fallback_author,
        "category": fallback_category,
        "title": "",
        "keywords": "",
        "body": "",
    }

    lines = text.strip().split("\n")
    body_started = False
    body_lines = []
    colon_pattern = r'\s*[:：]\s*'

    for line in lines:
        s = line.strip()
        if not body_started:
            m = re.match(r'^作者' + colon_pattern + r'(.+)$', s)
            if m:
                result["author"] = m.group(1).strip()
                continue
            m = re.match(r'^分类' + colon_pattern + r'(.+)$', s)
            if m:
                result["category"] = m.group(1).strip()
                continue
            m = re.match(r'^标题' + colon_pattern + r'(.+)$', s)
            if m:
                result["title"] = m.group(1).strip()
                continue
            m = re.match(r'^关键词' + colon_pattern + r'(.+)$', s)
            if m:
                result["keywords"] = m.group(1).strip()
                continue
            if re.match(r'^文案' + colon_pattern + r'$', s) or s in ("文案:", "文案："):
                body_started = True
                continue
        else:
            body_lines.append(line)

    result["body"] = "\n".join(body_lines).strip()
    return result


if __name__ == "__main__":
    print("此为占位模块，完整版请从预装包获取。")
    print("用法：将预装包中的 copywrite_gen.py 和 cw_prompts/ 覆盖至 backend/scripts/ 目录。")
