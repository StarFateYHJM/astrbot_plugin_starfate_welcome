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

    async def _get_user_name(self, event: AstrMessageEvent, user_id: str) -> str:
        """获取用户昵称"""
        # 方式1：从 raw 数据获取
        msg_obj = event.message_obj
        if hasattr(msg_obj, 'raw'):
            raw = msg_obj.raw
            if isinstance(raw, dict):
                sender = raw.get("sender", {})
                if isinstance(sender, dict):
                    name = sender.get("nickname") or sender.get("card")
                    if name:
                        self._log(f"从 raw.sender 获取昵称: {name}")
                        return name

        # 方式2：主动调用 API
        try:
            user_info = await self.plugin.context.get_user_info(user_id)
            if user_info:
                name = user_info.get("nickname") or user_info.get("user_name")
                if name:
                    self._log(f"从 API 获取昵称: {name}")
                    return name
        except Exception as e:
            self._log(f"API 获取昵称失败: {e}")

        # 方式3：调用事件方法
        if hasattr(event, 'get_sender_name'):
            try:
                name = event.get_sender_name()
                if name and name != user_id:
                    self._log(f"从 get_sender_name 获取昵称: {name}")
                    return name
            except Exception as e:
                self._log(f"get_sender_name 失败: {e}")

        self._log(f"无法获取昵称，使用 QQ 号: {user_id}")
        return user_id

    def _get_group_name(self, event: AstrMessageEvent, group_id: str) -> str:
        msg_obj = event.message_obj
        if hasattr(msg_obj, 'raw'):
            raw = msg_obj.raw
            if isinstance(raw, dict):
                name = raw.get("group_name")
                if name:
                    return name

        if hasattr(event, 'get_group_name'):
            try:
                name = event.get_group_name()
                if name:
                    return name
            except:
                pass

        return group_id

    async def _replace_vars(self, text: str, event: AstrMessageEvent, user_id: str) -> str:
        gid = str(event.get_group_id())
        uname = await self._get_user_name(event, user_id)
        gname = self._get_group_name(event, gid)

        self._log(f"变量替换: user_id={user_id}, user_name={uname}, group_id={gid}, group_name={gname}")

        return (text
                .replace("{user_id}", user_id)
                .replace("{user_name}", uname)
                .replace("{group_id}", gid)
                .replace("{group_name}", gname)
                .replace("{at_user}", f"[CQ:at,qq={user_id}]"))

    async def _build_html(self, w: dict, event: AstrMessageEvent, user_id: str) -> str:
        content = await self._replace_vars(w.get("content", ""), event, user_id)
        bg = self.plugin.resolve_background(w.get("background_image", ""))

        overlay = ""
        if bg and w.get("background_overlay", True):
            overlay = f'<div class="overlay" style="background:{w.get("overlay_color","#000")};opacity:{w.get("overlay_opacity",0.5)}"></div>'

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
    if(bg && !bg.startsWith('data:')){{
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
