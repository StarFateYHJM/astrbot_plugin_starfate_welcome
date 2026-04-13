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
    """StarFate 入群欢迎插件"""

    def __init__(self, context: Context, config: dict = None):
        super().__init__(context)
        self.name = "astrbot_plugin_starfate_welcome"
        self.config = config or {}
        self.debug = self.config.get("debug_mode", False)

        self._init_paths()
        self._init_components()

        self._log(f"插件已加载，配置项: {len(self.config)}")

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
        """解析背景图：本地优先（转Base64），URL其次，都没有返回空"""
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
                self._log(f"本地背景图已转为Base64: {user_input}", "debug")
                return f"data:{mime_type};base64,{data}"
            except Exception as e:
                self._log(f"读取本地背景图失败: {e}", "error")
                return ""

        self._log(f"本地背景图不存在: {user_input}", "warning")
        return ""

    @filter.on_group_increase()
    async def on_group_welcome(self, event: AstrMessageEvent):
        """监听入群事件"""
        group_id = str(event.get_group_id())
        user_id = str(event.get_sender_id())

        self._log(f"入群事件: group={group_id}, user={user_id}")

        # 匹配欢迎语配置
        group_welcome_map = self.config.get("group_welcome_map", {})
        welcome_id = group_welcome_map.get(group_id, "default")

        self._log(f"使用欢迎语ID: {welcome_id}")

        # 查找欢迎语配置
        welcome_sets = self.config.get("welcome_sets", [])
        welcome = None
        for w in welcome_sets:
            if w.get("welcome_id") == welcome_id:
                welcome = w
                break

        if not welcome:
            # 找默认的
            for w in welcome_sets:
                if w.get("is_default", False):
                    welcome = w
                    break

        if not welcome and welcome_sets:
            welcome = welcome_sets[0]

        if not welcome:
            self._log("没有配置欢迎语，跳过", "warning")
            return

        try:
            html = self.handler.render(welcome, event)
            url = await self.html_render(html, {"full_page": True})
            self._log("欢迎图片已生成")
            yield event.image_result(url)
        except Exception as e:
            self._log(f"渲染失败: {e}", "error")
            if self.debug:
                import traceback
                logger.error(traceback.format_exc())

    @filter.command("sfwelcome_reload")
    async def cmd_reload(self, event: AstrMessageEvent):
        """重载配置（管理员）"""
        if not await self._check_admin(event):
            yield event.plain_result("权限不足")
            return
        await self._reload_config()
        self.handler.clear_cache()
        self._log("配置已重载", "debug")
        yield event.plain_result("入群欢迎配置已重载")

    async def _reload_config(self):
        try:
            if sm := self.context.get_star_manager():
                if p := sm.get_star(self.name):
                    if p.config:
                        self.config = p.config
                        self.debug = self.config.get("debug_mode", False)
                        return
            if (cf := self.data_dir / "config.json").exists():
                self.config = json.loads(cf.read_text(encoding="utf-8"))
                self.debug = self.config.get("debug_mode", False)
        except Exception as e:
            self._log(f"刷新失败: {e}", "warning")

    @filter.command("sfwelcome_list")
    async def cmd_list(self, event: AstrMessageEvent):
        """列出所有欢迎语"""
        ws = self.config.get("welcome_sets", [])
        if not ws:
            yield event.plain_result("暂无欢迎语配置")
            return

        lines = ["可用欢迎语："]
        for i, w in enumerate(ws, 1):
            name = w.get("welcome_name", "未命名")
            wid = w.get("welcome_id", "?")
            default = " [默认]" if w.get("is_default") else ""
            lines.append(f"  {i}. {name} ({wid}){default}")

        group_map = self.config.get("group_welcome_map", {})
        if group_map:
            lines.append("\n群聊绑定：")
            for gid, wid in group_map.items():
                lines.append(f"  群 {gid} -> {wid}")

        yield event.plain_result("\n".join(lines))

    @filter.command("sfwelcome_bind")
    async def cmd_bind(self, event: AstrMessageEvent, group_id: str = None, welcome_id: str = None):
        """绑定群聊与欢迎语（管理员）"""
        if not await self._check_admin(event):
            yield event.plain_result("权限不足")
            return

        if not group_id or not welcome_id:
            yield event.plain_result("用法: /sfwelcome_bind <群号> <欢迎语ID>")
            return

        if "group_welcome_map" not in self.config:
            self.config["group_welcome_map"] = {}

        self.config["group_welcome_map"][group_id] = welcome_id
        await self._save_config()
        self._log(f"绑定: 群 {group_id} -> {welcome_id}")
        yield event.plain_result(f"已绑定群 {group_id} 使用欢迎语 {welcome_id}")

    @filter.command("sfwelcome_unbind")
    async def cmd_unbind(self, event: AstrMessageEvent, group_id: str = None):
        """解绑群聊（管理员）"""
        if not await self._check_admin(event):
            yield event.plain_result("权限不足")
            return

        if not group_id:
            yield event.plain_result("用法: /sfwelcome_unbind <群号>")
            return

        if "group_welcome_map" in self.config:
            self.config["group_welcome_map"].pop(group_id, None)
            await self._save_config()

        yield event.plain_result(f"已解绑群 {group_id}")

    async def _save_config(self):
        """保存配置到文件"""
        config_file = self.data_dir / "config.json"
        with open(config_file, "w", encoding="utf-8") as f:
            json.dump(self.config, f, ensure_ascii=False, indent=2)

    async def _check_admin(self, event: AstrMessageEvent) -> bool:
        admins = self.context.get_config().get("admins_id") or []
        return str(event.get_sender_id()) in admins

    async def terminate(self):
        logger.info("入群欢迎插件已卸载")
