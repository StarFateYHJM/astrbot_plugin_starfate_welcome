"""入群欢迎处理器"""

import json
import hashlib
from astrbot.api.event import AstrMessageEvent
from astrbot.api import logger


class WelcomeHandler:
    """入群欢迎渲染器"""

    def __init__(self, plugin):
        self.plugin = plugin
        self._cache = {}

    def _log(self, msg: str):
        if self.plugin.debug:
            logger.info(f"[DEBUG] {msg}")

    def clear_cache(self):
        self._cache.clear()
        self._log("缓存已清空")

    async def render(self, welcome: dict, event: AstrMessageEvent, override_user_id: str = None) -> str:
        user_id = override_user_id or str(event.get_sender_id())
        group_id = str(event.get_group_id())

        cache_key = hashlib.md5(
            json.dumps({"w": welcome, "u": user_id, "g": group_id}, sort_keys=True).encode()
        ).hexdigest()[:8]

        if cache_key in self._cache:
            self._log(f"缓存命中: {cache_key}")
            return self._cache[cache_key]

        self._log(f"渲染: {cache_key}")
        html = await self._build_html(welcome, event, user_id)
        self._cache[cache_key] = html
        return html

    async def _replace_vars(self, text: str, event: AstrMessageEvent, user_id: str) -> str:
        gid = str(event.get_group_id())

        return (text
                .replace("{user_id}", user_id)
                .replace("{user_name}", user_id)
                .replace("{group_id}", gid)
                .replace("{group_name}", gid)
                .replace("{at_user}", f"[CQ:at,qq={user_id}]"))

    async def _build_html(self, w: dict, event: AstrMessageEvent, user_id: str) -> str:
        content = await self._replace_vars(w.get("content", ""), event, user_id)
        bg = self.plugin.resolve_background(w.get("background_image", ""))

        overlay = ""
        if bg and w.get("background_overlay", True):
            overlay = f'<div class="overlay" style="background:{w.get("overlay_color","#000")};opacity:{w.get("overlay_opacity",0.5)}"></div>'

        # 构建 body 样式
        body_style = f'font-family:"Microsoft YaHei",sans-serif;zoom:{w.get("css_zoom",2)};position:relative;font-size:{w.get("base_font_size","16px")}'
        if bg:
            # 清理 Base64 中的换行符
            bg_clean = bg.replace('\n', '').replace('\r', '')
            body_style += f';background-image:url(\'{bg_clean}\');background-size:cover;background-position:center;background-repeat:no-repeat'
        else:
            body_style += f';background:{w.get("background_color","#1A1A2E")}'

        return f'''<!DOCTYPE html>
<html><head><meta charset="UTF-8"><script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
html,body{{width:100%;min-height:100vh}}
body{{{body_style}}}
.overlay{{position:fixed;top:0;left:0;width:100%;height:100%;pointer-events:none;z-index:1}}
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
<body>{overlay}
<div class="welcome-container"><div class="content" id="content"></div></div>
<script>
(function(){{
    document.getElementById('content').innerHTML = marked.parse({json.dumps(content)});
}})();
</script></body></html>'''
