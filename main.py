"""StarFate 入群欢迎插件 - 主入口"""

import json
import base64
import mimetypes
from pathlib import Path
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger

from .handlers.welcome_handler import WelcomeHandler


@register("astrbot_plugin_starfate_welcome", "YHJM", "StarFate 入群欢迎", "1.0.0")
class StarFateWelcomePlugin(Star):

    def __init__(self, context: Context, config: dict = None):
        super().__init__(context)
        self.name = "astrbot_plugin_starfate_welcome"
        self.config = config or {}
        self.debug = self.config.get("debug_mode", False)

        self._init_paths()
        self._init_components()

        self._log(f"插件已加载，debug={self.debug}")

    def _log(self, msg: str, level: str = "info"):
        if not self.debug and level == "debug":
            return
        getattr(logger, level)(f"[DEBUG] {msg}" if level == "debug" else msg)

    def _init_paths(self):
        from astrbot.core.utils.astrbot_path import get_astrbot_data_path
        path = get_astrbot_data_path()
        self.data_dir = (Path(path) if isinstance(path, str) else path) / "plugin_data" / self.name
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.backgrounds_dir = self.data_dir / "backgrounds"
        self.backgrounds_dir.mkdir(exist_ok=True)

    def _init_components(self):
        self.handler = WelcomeHandler(self)

    def resolve_background(self, user_input: str) -> str:
        if not user_input:
            return ""
        if user_input.startswith(("http://", "https://")):
            return user_input
        local_path = self.backgrounds_dir / user_input
        if local_path.exists():
            try:
                mime_type, _ = mimetypes.guess_type(str(local_path))
                if not mime_type:
                    mime_type = "image/png"
                with open(local_path, "rb") as f:
                    data = base64.b64encode(f.read()).decode("utf-8")
                return f"data:{mime_type};base64,{data}"
            except Exception as e:
                self._log(f"读取失败: {e}", "error")
                return ""
        return ""

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def on_all_event(self, event: AstrMessageEvent):
        """监听所有事件，过滤入群事件"""
        msg_obj = event.message_obj
        
        group_id = event.get_group_id()
        self._log(f"事件检查: group_id={group_id}", "debug")
        
        if not group_id:
            return
        
        is_increase = False
        user_id = None
        
        if hasattr(msg_obj, 'raw'):
            raw = msg_obj.raw
            if isinstance(raw, dict):
                post_type = raw.get("post_type")
                notice_type = raw.get("notice_type")
                self._log(f"raw数据: post_type={post_type}, notice_type={notice_type}", "debug")
                
                if post_type == "notice" and notice_type == "group_increase":
                    is_increase = True
                    user_id = raw.get("user_id")
                    self._log(f"检测到入群事件: user_id={user_id}", "debug")
        
        if not is_increase:
            return
        
        group_id_str = str(group_id)
        user_id_str = str(user_id) if user_id else ""
        
        self._log(f"入群事件确认: group={group_id_str}, user={user_id_str}")
        
        welcome = self._get_welcome_for_group(group_id_str)
        if not welcome:
            self._log(f"群 {group_id_str} 无欢迎语配置")
            return
        
        self._log(f"找到欢迎语: {welcome.get('welcome_id')}")
        
        try:
            html = self.handler.render(welcome, event, user_id_str)
            url = await self.html_render(html, {"full_page": True})
            yield event.image_result(url)
            self._log("欢迎图片已发送")
        except Exception as e:
            self._log(f"渲染失败: {e}", "error")

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
            url = await self.html_render(html, {"full_page": True})
            yield event.image_result(url)
        except Exception as e:
            yield event.plain_result(f"失败: {e}")

    def _get_welcome_for_group(self, group_id: str) -> dict:
        ws = self.config.get("welcome_sets", [])
        if not ws:
            return None

        bindings = self.config.get("group_welcome_map", [])
        welcome_id = None
        for bind in bindings:
            if str(bind.get("group_id")) == str(group_id):
                welcome_id = bind.get("welcome_id")
                break

        if welcome_id is not None:
            for w in ws:
                if str(w.get("welcome_id")) == str(welcome_id):
                    return w

        for w in ws:
            if w.get("is_default"):
                return w

        return ws[0] if ws else None

    def _get_welcome_by_id(self, wid: str) -> dict:
        for w in self.config.get("welcome_sets", []):
            if str(w.get("welcome_id")) == str(wid):
                return w
        return None

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
                    if p.config:
                        self.config = p.config
                        self.debug = self.config.get("debug_mode", False)
                        return
            cf = self.data_dir / "config.json"
            if cf.exists():
                self.config = json.loads(cf.read_text(encoding="utf-8"))
                self.debug = self.config.get("debug_mode", False)
        except Exception as e:
            self._log(f"刷新失败: {e}", "warning")

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
            d = " [默认]" if w.get("is_default") else ""
            lines.append(f"{i}. {name} ({wid}){d}")

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
        found = False
        for bind in bindings:
            if str(bind.get("group_id")) == str(group_id):
                bind["welcome_id"] = welcome_id
                found = True
                break
        if not found:
            bindings.append({"group_id": group_id, "welcome_id": welcome_id})

        self.config["group_welcome_map"] = bindings
        await self._save_config()
        yield event.plain_result(f"已绑定群 {group_id} 使用欢迎语 {welcome_id}")

    @filter.command("sfwelcome_unbind")
    async def cmd_unbind(self, event: AstrMessageEvent, group_id: str):
        if not await self._check_admin(event):
            yield event.plain_result("权限不足")
            return

        bindings = self.config.get("group_welcome_map", [])
        self.config["group_welcome_map"] = [b for b in bindings if str(b.get("group_id")) != str(group_id)]
        await self._save_config()
        yield event.plain_result(f"已解绑群 {group_id}")

    async def _save_config(self):
        cf = self.data_dir / "config.json"
        cf.write_text(json.dumps(self.config, ensure_ascii=False, indent=2), encoding="utf-8")

    async def _check_admin(self, event: AstrMessageEvent) -> bool:
        admins = self.context.get_config().get("admins_id") or []
        return str(event.get_sender_id()) in admins

    async def terminate(self):
        logger.info("插件已卸载")
