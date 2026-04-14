"""StarFate 入群欢迎插件 - 主入口"""

import json
import base64
import mimetypes
import traceback
from pathlib import Path
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
from astrbot.api.message_components import At, Plain,MessageChain

from .handlers.welcome_handler import WelcomeHandler


@register("astrbot_plugin_starfate_welcome", "YHJM", "StarFate 入群欢迎", "1.0.0")
class StarFateWelcomePlugin(Star):
    """StarFate 入群欢迎插件"""

    def __init__(self, context: Context, config: dict = None):
        super().__init__(context)
        self.name = "astrbot_plugin_starfate_welcome"
        self.config = config or {}
        self.debug = self.config.get("debug_mode", False)

        self._init_paths()
        self.handler = WelcomeHandler(self)

        self._log(f"插件已加载，debug={self.debug}")

    # ========== 工具方法 ==========
    def _log(self, msg: str, level: str = "info"):
        if self.debug or level != "debug":
            getattr(logger, level)(f"[DEBUG] {msg}" if level == "debug" else msg)

    def _init_paths(self):
        from astrbot.core.utils.astrbot_path import get_astrbot_data_path
        path = get_astrbot_data_path()
        self.data_dir = (Path(path) if isinstance(path, str) else path) / "plugin_data" / self.name
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.backgrounds_dir = self.data_dir / "backgrounds"
        self.backgrounds_dir.mkdir(exist_ok=True)

    async def _check_admin(self, event: AstrMessageEvent) -> bool:
        admins = self.context.get_config().get("admins_id", [])
        return str(event.get_sender_id()) in admins

    async def _save_config(self):
        cf = self.data_dir / "config.json"
        cf.write_text(json.dumps(self.config, ensure_ascii=False, indent=2), encoding="utf-8")

    # ========== 背景图处理 ==========
    def resolve_background(self, user_input: str) -> str:
        if not user_input:
            return ""
        if user_input.startswith(("http://", "https://")):
            return user_input

        local_path = self.backgrounds_dir / user_input
        if not local_path.exists():
            return ""

        try:
            mime_type, _ = mimetypes.guess_type(str(local_path))
            mime_type = mime_type or "image/png"
            with open(local_path, "rb") as f:
                data = base64.b64encode(f.read()).decode("utf-8")
            return f"data:{mime_type};base64,{data}"
        except Exception as e:
            self._log(f"读取背景图失败: {e}", "error")
            return ""

    # ========== 欢迎语查找 ==========
    def _get_welcome_by_id(self, wid: str) -> dict:
        for w in self.config.get("welcome_sets", []):
            if str(w.get("welcome_id")) == str(wid):
                return w
        return None

    def _get_welcome_for_group(self, group_id: str) -> dict:
        ws = self.config.get("welcome_sets", [])
        if not ws:
            return None

        bindings = self.config.get("group_welcome_map", [])
        welcome_id = next(
            (b.get("welcome_id") for b in bindings if str(b.get("group_id")) == str(group_id)),
            None
        )

        if welcome_id:
            w = self._get_welcome_by_id(welcome_id)
            if w:
                return w

        return next((w for w in ws if w.get("is_default")), ws[0] if ws else None)

    # ========== 事件处理 ==========
    def _extract_raw(self, event: AstrMessageEvent, msg_obj) -> dict:
        if hasattr(msg_obj, 'raw_message'):
            raw = msg_obj.raw_message
            if isinstance(raw, str):
                try:
                    return json.loads(raw)
                except json.JSONDecodeError:
                    return None
            if isinstance(raw, dict):
                return raw

        for source in (getattr(event, 'raw', None), getattr(msg_obj, 'raw', None)):
            if isinstance(source, dict):
                return source

        return None

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def on_all_event(self, event: AstrMessageEvent):
        self._log("=== 收到事件 ===", "debug")
        
        group_id = event.get_group_id()
        self._log(f"group_id: {group_id}", "debug")
        if not group_id:
            self._log("无 group_id，退出", "debug")
            return

        raw = self._extract_raw(event, event.message_obj)
        self._log(f"raw 数据类型: {type(raw)}", "debug")
        if not isinstance(raw, dict):
            self._log("raw 不是字典，退出", "debug")
            return

        post_type = raw.get("post_type")
        notice_type = raw.get("notice_type")
        self._log(f"post_type={post_type}, notice_type={notice_type}", "debug")

        if post_type != "notice" or notice_type != "group_increase":
            self._log("不是入群事件，退出", "debug")
            return

        sub_type = raw.get("sub_type")
        self._log(f"sub_type={sub_type}", "debug")
        if sub_type not in ("invite", "approve"):
            self._log(f"忽略入群子事件: sub_type={sub_type}", "debug")
            return

        group_id_str = str(group_id)
        user_id_str = str(raw.get("user_id", ""))

        self._log(f"入群事件确认: group={group_id_str}, user={user_id_str}")

        welcome = self._get_welcome_for_group(group_id_str)
        if not welcome:
            self._log(f"群 {group_id_str} 无欢迎语", "debug")
            return

        self._log(f"找到欢迎语: {welcome.get('welcome_id')}")

        try:
            self._log("开始渲染 HTML...", "debug")
            html = self.handler.render(welcome, event, user_id_str)
            self._log(f"HTML 渲染完成，长度: {len(html)}", "debug")
            
            self._log("调用 html_render...", "debug")
            image_url = await self.html_render(html, {"full_page": True})
            self._log(f"图片 URL: {image_url}")
        
            self._log("发送欢迎消息...", "debug")
            chain = MessageChain()
            chain.add(At(qq=user_id_str))
            chain.add(Plain(" "))
            chain.add(image_url)
            await event.send(chain)
            self._log("欢迎消息已发送", "debug")
        
            event.stop_event()
    
        except Exception as e:
            self._log(f"渲染失败: {e}", "error")
            self._log(traceback.format_exc(), "error")

    # ========== 命令 ==========
    @filter.command("sfwelcome_test")
    async def cmd_test(self, event: AstrMessageEvent, welcome_id: str = None):
        if not await self._check_admin(event):
            yield event.plain_result("权限不足")
            return

        group_id = str(event.get_group_id())
        if not group_id:
            yield event.plain_result("请在群聊中使用")
            return

        welcome = self._get_welcome_by_id(welcome_id) if welcome_id else self._get_welcome_for_group(group_id)
        if not welcome:
            yield event.plain_result("无欢迎语")
            return

        try:
            html = self.handler.render(welcome, event, str(event.get_sender_id()))
            image_url = await self.html_render(html, {"full_page": True})
            yield event.chain_result([image_url])
        except Exception as e:
            yield event.plain_result(f"失败: {e}")

    @filter.command("sfwelcome_reload")
    async def cmd_reload(self, event: AstrMessageEvent):
        if not await self._check_admin(event):
            yield event.plain_result("权限不足")
            return
        await self._reload_config()
        self.handler.clear_cache()
        yield event.plain_result("已重载")

    async def _reload_config(self):
        try:
            if sm := self.context.get_star_manager():
                if p := sm.get_star(self.name):
                    if p and p.config:
                        self.config = p.config
                        self.debug = self.config.get("debug_mode", False)
                        return
            cf = self.data_dir / "config.json"
            if cf.exists():
                self.config = json.loads(cf.read_text(encoding="utf-8"))
                self.debug = self.config.get("debug_mode", False)
        except Exception as e:
            self._log(f"刷新配置失败: {e}", "warning")

    @filter.command("sfwelcome_list")
    async def cmd_list(self, event: AstrMessageEvent):
        ws = self.config.get("welcome_sets", [])
        if not ws:
            yield event.plain_result("暂无配置")
            return

        lines = ["=== 欢迎语列表 ==="]
        for i, w in enumerate(ws, 1):
            name = w.get("welcome_name", "?")
            wid = w.get("welcome_id", "?")
            default = " [默认]" if w.get("is_default") else ""
            lines.append(f"{i}. {name} ({wid}){default}")

        bindings = self.config.get("group_welcome_map", [])
        if bindings:
            lines.append("\n=== 群聊绑定 ===")
            for b in bindings:
                lines.append(f"群 {b.get('group_id')} -> {b.get('welcome_id')}")

        yield event.plain_result("\n".join(lines))

    @filter.command("sfwelcome_bind")
    async def cmd_bind(self, event: AstrMessageEvent, group_id: str, welcome_id: str):
        if not await self._check_admin(event):
            yield event.plain_result("权限不足")
            return

        bindings = self.config.get("group_welcome_map", [])
        for bind in bindings:
            if str(bind.get("group_id")) == str(group_id):
                bind["welcome_id"] = welcome_id
                break
        else:
            bindings.append({"group_id": group_id, "welcome_id": welcome_id})

        self.config["group_welcome_map"] = bindings
        await self._save_config()
        yield event.plain_result(f"已绑定群 {group_id} -> {welcome_id}")

    @filter.command("sfwelcome_unbind")
    async def cmd_unbind(self, event: AstrMessageEvent, group_id: str):
        if not await self._check_admin(event):
            yield event.plain_result("权限不足")
            return

        self.config["group_welcome_map"] = [
            b for b in self.config.get("group_welcome_map", [])
            if str(b.get("group_id")) != str(group_id)
        ]
        await self._save_config()
        yield event.plain_result(f"已解绑群 {group_id}")

    async def terminate(self):
        logger.info("插件已卸载")
