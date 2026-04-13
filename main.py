@filter.event_message_type(filter.EventMessageType.ALL)
async def on_all_event(self, event: AstrMessageEvent):
    """监听所有事件，过滤入群事件"""
    msg_obj = event.message_obj
    
    group_id = event.get_group_id()
    if not group_id:
        return
    
    is_increase = False
    user_id = None
    
    if hasattr(msg_obj, 'raw'):
        raw = msg_obj.raw
        if isinstance(raw, dict):
            if raw.get("post_type") == "notice" and raw.get("notice_type") == "group_increase":
                is_increase = True
                user_id = raw.get("user_id")
    
    if not is_increase:
        return
    
    group_id_str = str(group_id)
    user_id_str = str(user_id) if user_id else ""
    
    self._log(f"入群事件触发: group={group_id_str}, user={user_id_str}")
    
    welcome = self._get_welcome_for_group(group_id_str)
    if not welcome:
        return
    
    try:
        html = self.handler.render(welcome, event, user_id_str)
        url = await self.html_render(html, {"full_page": True})
        yield event.image_result(url)
    except Exception as e:
        self._log(f"渲染失败: {e}", "error")
