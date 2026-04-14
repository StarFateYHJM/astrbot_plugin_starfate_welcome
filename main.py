"""StarFate 入群欢迎插件 - 主入口"""

import json
import base64
import mimetypes
import traceback
from pathlib import Path
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
from astrbot.api.message_components import At, Plain

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
        self._log(f"配置项数量: {len(self.config)}", "debug")
        self._log(f"欢迎语套数: {len(self.config.get('welcome_sets', []))}", "debug")
        self._log(f"群绑定数量: {len(self.config.get('group_welcome_map', []))}", "debug")

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
        self._log(f"数据目录: {self.data_dir}", "debug")
        self._log(f"背景图目录: {self.backgrounds_dir}", "debug")

    async def _check_admin(self, event: AstrMessageEvent) -> bool:
        admins = self.context.get_config().get("admins_id", [])
        user_id = str(event.get_sender_id())
        result = user_id in admins
        self._log(f"权限检查: user={user_id}, admin={result}", "debug")
        return result

    async def _save_config(self):
        cf = self.data_dir / "config.json"
        cf.write_text(json.dumps(self.config, ensure_ascii=False, indent=2), encoding="utf-8")
        self._log(f"配置已保存: {cf}", "debug")

    # ========== 背景图处理 ==========
    def resolve_background(self, user_input: str) -> str:
        self._log(f"解析背景图: input='{user_input}'", "debug")
        if not user_input:
            self._log("背景图为空", "debug")
            return ""
        if user_input.startswith(("http://", "https://")):
            self._log(f"使用 URL: {user_input}", "debug")
            return user_input

        local_path = self.backgrounds_dir / user_input
        self._log(f"本地路径: {local_path}", "debug")
        if not local_path.exists():
            self._log(f"本地文件不存在: {user_input}", "warning")
            return ""

        try:
            mime_type, _ = mimetypes.guess_type(str(local_path))
            mime_type = mime_type or "image/png"
            with open(local_path, "rb") as f:
                data = base64.b64encode(f.read()).decode("utf-8")
            self._log(f"Base64 转换成功，类型: {mime_type}", "debug")
            return f"data:{mime_type};base64,{data}"
        except Exception as e:
            self._log(f"读取背景图失败: {e}", "error")
            return ""

    # ========== 欢迎语查找 ==========
    def _get_welcome_by_id(self, wid: str) -> dict:
        self._log(f"按ID查找欢迎语: {wid}", "debug")
        for i, w in enumerate(self.config.get("welcome_sets", [])):
            if str(w.get("welcome_id")) == str(wid):
                self._log(f"找到: 索引={i}, name={w.get('welcome_name')}", "debug")
                return w
        self._log(f"未找到欢迎语: {wid}", "debug")
        return None

    def _get_welcome_for_group(self, group_id: str) -> dict:
        self._log(f"查找群欢迎语: group={group_id}", "debug")
        ws = self.config.get("welcome_sets", [])
        if not ws:
            self._log("没有配置任何欢迎语", "debug")
            return None

        bindings = self.config.get("group_welcome_map", [])
        self._log(f"群绑定配置: {bindings}", "debug")
        
        welcome_id = next(
            (b.get("welcome_id") for b in bindings if str(b.get("group_id")) == str(group_id)),
            None
        )
        self._log(f"绑定的欢迎语ID: {welcome_id}", "debug")

        if welcome_id:
            w = self._get_welcome_by_id(welcome_id)
            if w:
                return w

        default_w = next((w for w in ws if w.get("is_default")), ws[0] if ws else None)
        self._log(f"使用默认欢迎语: {default_w.get('welcome_id') if default_w else 'None'}", "debug")
        return default_w

    # ========== 事件处理 ==========
    def _extract_raw(self, event: AstrMessageEvent, msg_obj) -> dict:
        self._log("提取 raw 数据...", "debug")
        
        if hasattr(msg_obj, 'raw_message'):
            raw = msg_obj.raw_message
            self._log(f"从 msg_obj.raw_message 获取，类型: {type(raw)}", "debug")
            if isinstance(raw, str):
                try:
                    parsed = json.loads(raw)
                    self._log("JSON 解析成功", "debug")
                    return parsed
                except json.JSONDecodeError:
                    self._log("JSON 解析失败", "debug")
                    return None
            if isinstance(raw, dict):
                self._log("已经是字典", "debug")
                return raw

        for source_name, source in [('event.raw', getattr(event, 'raw', None)), 
                                    ('msg_obj.raw', getattr(msg_obj, 'raw', None))]:
            if isinstance(source, dict):
                self._log(f"从 {source_name} 获取到字典", "debug")
                return source

        self._log("未获取到 raw 数据", "debug")
        return None

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def on_all_event(self, event: AstrMessageEvent):
        self._log("=" * 50, "debug")
        self._log("收到事件", "debug")
        
        group_id = event.get_group_id()
        self._log(f"group_id: {group_id}", "debug")
        if not group_id:
            self._log("无 group_id，退出", "debug")
            return

        raw = self._extract_raw(event, event.message_obj)
        self._log("=== 完整 raw 数据 ===", "info")
        self._log(json.dumps(raw, ensure_ascii=False, indent=2, default=str), "info")
        self._log("=== raw 数据结束 ===", "info")
        if not isinstance(raw, dict):
            self._log("raw 不是字典，退出", "debug")
            return

        post_type = raw.get("post_type")
        notice_type = raw.get("notice_type")
        sub_type = raw.get("sub_type")
        self._log(f"事件类型: post_type={post_type}, notice_type={notice_type}, sub_type={sub_type}", "debug")

        if post_type != "notice" or notice_type != "group_increase":
            self._log("不是入群事件，退出", "debug")
            return

        if sub_type not in ("invite", "approve"):
            self._log(f"忽略入群子事件: {sub_type}", "debug")
            return

        group_id_str = str(group_id)
        user_id_str = str(raw.get("user_id", ""))

        self._log(f"入群事件确认: group={group_id_str}, user={user_id_str}")

        welcome = self._get_welcome_for_group(group_id_str)
        if not welcome:
            self._log(f"群 {group_id_str} 无欢迎语，退出", "debug")
            return

        self._log(f"使用欢迎语: id={welcome.get('welcome_id')}, name={welcome.get('welcome_name')}")

        try:
            self._log("开始渲染...", "debug")
            html = self.handler.render(welcome, event, user_id_str)
            self._log(f"HTML 长度: {len(html)}", "debug")
            
            image_url = await self.html_render(html, {"full_page": True})
            self._log(f"图片 URL: {image_url}")

            at_text = welcome.get("at_text", " 欢迎入群！")
            self._log(f"@ 文字: '{at_text}'", "debug")
            
            self._log("发送 @ 消息...", "debug")
            yield event.chain_result([At(qq=user_id_str), Plain(at_text)])
            self._log("@ 消息已发送", "debug")
            
            self._log("发送图片...", "debug")
            yield event.image_result(image_url)
            self._log("图片已发送", "debug")

            event.stop_event()
            self._log("事件处理完成", "debug")
            
        except Exception as e:
            self._log(f"渲染失败: {e}", "error")
            self._log(traceback.format_exc(), "error")
        finally:
            self._log("=" * 50, "debug")

    # ========== 命令 ==========
    @filter.command("sfwelcome_test")
    async def cmd_test(self, event: AstrMessageEvent, welcome_id: str = None):
        self._log(f"测试命令: welcome_id={welcome_id}", "debug")
        
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

        self._log(f"测试欢迎语: {welcome.get('welcome_id')}", "debug")
        try:
            html = self.handler.render(welcome, event, str(event.get_sender_id()))
            image_url = await self.html_render(html, {"full_page": True})
            yield event.image_result(image_url)
            self._log("测试图片已发送", "debug")
        except Exception as e:
            self._log(f"测试失败: {e}", "error")
            yield event.plain_result(f"失败: {e}")

    @filter.command("sfwelcome_reload")
    async def cmd_reload(self, event: AstrMessageEvent):
        self._log("重载命令", "debug")
        if not await self._check_admin(event):
            yield event.plain_result("权限不足")
            return
        await self._reload_config()
        self.handler.clear_cache()
        self._log("配置已重载", "debug")
        yield event.plain_result("已重载")

    async def _reload_config(self):
        self._log("刷新配置...", "debug")
        try:
            if sm := self.context.get_star_manager():
                if p := sm.get_star(self.name):
                    if p and p.config:
                        self.config = p.config
                        self.debug = self.config.get("debug_mode", False)
                        self._log("从插件管理器刷新成功", "debug")
                        return
            cf = self.data_dir / "config.json"
            if cf.exists():
                self.config = json.loads(cf.read_text(encoding="utf-8"))
                self.debug = self.config.get("debug_mode", False)
                self._log("从配置文件刷新成功", "debug")
        except Exception as e:
            self._log(f"刷新失败: {e}", "warning")

    @filter.command("sfwelcome_list")
    async def cmd_list(self, event: AstrMessageEvent):
        self._log("列表命令", "debug")
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
        self._log(f"绑定命令: group={group_id}, welcome={welcome_id}", "debug")
        if not await self._check_admin(event):
            yield event.plain_result("权限不足")
            return

        bindings = self.config.get("group_welcome_map", [])
        for bind in bindings:
            if str(bind.get("group_id")) == str(group_id):
                bind["welcome_id"] = welcome_id
                self._log(f"更新已有绑定", "debug")
                break
        else:
            bindings.append({"group_id": group_id, "welcome_id": welcome_id})
            self._log(f"新增绑定", "debug")

        self.config["group_welcome_map"] = bindings
        await self._save_config()
        yield event.plain_result(f"已绑定群 {group_id} -> {welcome_id}")

    @filter.command("sfwelcome_unbind")
    async def cmd_unbind(self, event: AstrMessageEvent, group_id: str):
        self._log(f"解绑命令: group={group_id}", "debug")
        if not await self._check_admin(event):
            yield event.plain_result("权限不足")
            return

        old_count = len(self.config.get("group_welcome_map", []))
        self.config["group_welcome_map"] = [
            b for b in self.config.get("group_welcome_map", [])
            if str(b.get("group_id")) != str(group_id)
        ]
        new_count = len(self.config["group_welcome_map"])
        self._log(f"绑定数量: {old_count} -> {new_count}", "debug")
        
        await self._save_config()
        yield event.plain_result(f"已解绑群 {group_id}")

    async def terminate(self):
        self._log("插件卸载", "debug")
        logger.info("插件已卸载")
