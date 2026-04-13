"""入群欢迎处理器"""

import re
import json
import hashlib
from astrbot.api.event import AstrMessageEvent
from astrbot.api import logger


class WelcomeHandler:

    def __init__(self, plugin):
        self.plugin = plugin
        self._cache = {}

    def _log(self, msg: str):
        if self.plugin.debug:
            logger.info(f"[DEBUG] {msg}")

    def _hash(self, welcome: dict, user_id: str, group_id: str) -> str:
        """计算哈希（含用户和群信息）"""
        data = json.dumps({
            "welcome": welcome,
            "user_id": user_id,
            "group_id": group_id
        }, sort_keys=True, ensure_ascii=False)
        return hashlib.md5(data.encode()).hexdigest()[:8]

    def clear_cache(self):
        """清空缓存"""
        self._cache.clear()
        self._log("缓存已清空")

    def render(self, welcome: dict, event: AstrMessageEvent) -> str:
        """渲染欢迎图片"""
        user_id = str(event.get_sender_id())
        group_id = str(event.get_group_id())

        h = self._hash(welcome, user_id, group_id)
        if h in self._cache:
            self._log(f"缓存命中: {h}")
            return self._cache[h]

        self._log(f"渲染: {h}")
        html = self._build_html(welcome, event)
        self._cache[h] = html
        return html

    def _replace_vars(self, text: str, event: AstrMessageEvent) -> str:
        """替换模板变量"""
        user_id = str(event.get_sender_id())
        group_id = str(event.get_group_id())

        # 尝试获取用户名和群名（不同平台可能不同）
        user_name = user_id
        group_name = group_id
        if hasattr(event, 'get_sender_name'):
            user_name = event.get_sender_name() or user_id
        if hasattr(event, 'get_group_name'):
            group_name = event.get_group_name() or group_id

        return text.replace("{user_id}", user_id)\
                  .replace("{user_name}", user_name)\
                  .replace("{group_id}", group_id)\
                  .replace("{group_name}", group_name)\
                  .replace("{at_user}", f"[CQ:at,qq={user_id}]")

    def _build_html(self, w: dict, event: AstrMessageEvent) -> str:
        """构建 HTML"""
        content = w.get("content", "")
        content = self._replace_vars(content, event)

        bg = self.plugin.resolve_background(w.get("background_image", ""))
        overlay = f'<div class="overlay" style="background:{w.get("overlay_color","#000")};opacity:{w.get("overlay_opacity",0.5)}"></div>' if bg and w.get("background_overlay", True) else ""

        return f'''<!DOCTYPE html>
<html><head><meta charset="UTF-8"><script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:"Microsoft YaHei",sans-serif;zoom:{w.get("css_zoom",2)};background:{w.get("background_color","#1A1A2E")};position:relative;font-size:{w.get("base_font_size","16px")}}}
.bg-layer{{position:absolute;top:0;left:0;z-index:0}}
.bg-layer img{{display:block;width:100%;height:100%;object-fit:cover}}
.overlay{{position:absolute;top:0;left:0;width:100%;height:100%;pointer-events:none;z-index:1}}
.welcome-container{{position:relative;padding:{w.get("padding_body","40px 50px")};color:{w.get("text_color","#FFF")};z-index:2}}
.content h1{{font-size:{w.get("h1_font_size","2.5em")};border-bottom:2px solid {w.get("border_color","#333")};margin-bottom:20px;padding-bottom:15px}}
.content h2{{font-size:{w.get("h2_font_size","2em")};margin:30px 0 15px}}
.content h3{{font-size:{w.get("h3_font_size","1.5em")};margin:25px 0 10px}}
.content p{{margin-bottom:15px;line-height:1.6}}
.content ul,.content ol{{margin-left:25px;margin-bottom:15px}}
.content li{{margin-bottom:8px}}
.content a{{color:{w.get("link_color","#0DF")};text-decoration:none}}
.content code{{background:{w.get("code_bg_color","#2D2D2D")};color:{w.get("code_text_color","#E6E6E6")};padding:2px 6px;border-radius:4px}}
.content pre{{background:{w.get("code_bg_color","#2D2D2D")};padding:15px;border-radius:8px;overflow-x:auto}}
.content pre code{{background:none;padding:0}}
.content table{{width:100%;border-collapse:collapse}}
.content th,.content td{{border:1px solid {w.get("border_color","#333")};padding:10px 15px}}
.content hr{{border:none;border-top:2px solid {w.get("border_color","#333")};margin:30px 0}}
</style></head>
<body><div class="bg-layer" id="bgLayer"></div>{overlay}
<div class="welcome-container"><div class="content" id="content"></div></div>
<script>
(function(){{
    document.getElementById('content').innerHTML = marked.parse({json.dumps(content)});
    var bg = '{bg}';
    if(bg){{
        var i = new Image();
        i.onload = function(){{
            var w = this.width, h = this.height, max = 2000;
            if(w > max || h > max){{ var s = Math.min(max/w, max/h); w = Math.round(w*s); h = Math.round(h*s); }}
            document.body.style.width = w + 'px';
            document.body.style.height = h + 'px';
            document.getElementById('bgLayer').innerHTML = '<img src="' + bg + '" style="width:' + w + 'px;height:' + h + 'px;">';
        }};
        i.src = bg;
    }}
}})();
</script></body></html>'''
