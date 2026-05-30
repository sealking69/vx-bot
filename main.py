import os
import time
import asyncio
import random
from contextlib import asynccontextmanager
from datetime import datetime, timezone, timedelta

from fastapi import FastAPI, Request, Response, Query
import uvicorn

from wechat import (
    verify_signature,
    parse_message,
    build_text_reply,
    get_access_token,
    send_custom_message,
)
from ai import chat as ai_chat, get_client


# ---- 配置 ----
WECHAT_TOKEN = os.environ["WECHAT_TOKEN"]
WECHAT_APP_ID = os.environ["WECHAT_APP_ID"]
WECHAT_APP_SECRET = os.environ["WECHAT_APP_SECRET"]
WECHAT_USER_OPENID = os.environ.get("WECHAT_USER_OPENID", "")  # 你的微信 openid

_access_token: str | None = None
_access_token_expires: float = 0.0

# 记录每个用户最近一次互动时间（内存存储，重启会丢失；可换成 redis/文件）
_last_interaction: dict[str, float] = {}

# 主动消息开关：在 .env 中设置 PROACTIVE_CHAT=true 来启用
PROACTIVE_CHAT = os.environ.get("PROACTIVE_CHAT", "true").lower() == "true"
# 主动消息间隔（秒），默认 3-6 小时随机
PROACTIVE_INTERVAL_MIN = int(os.environ.get("PROACTIVE_INTERVAL_MIN", "10800"))  # 3小时
PROACTIVE_INTERVAL_MAX = int(os.environ.get("PROACTIVE_INTERVAL_MAX", "21600"))  # 6小时


async def refresh_access_token():
    """定时刷新 access_token"""
    global _access_token, _access_token_expires
    while True:
        try:
            token = get_access_token(WECHAT_APP_ID, WECHAT_APP_SECRET)
            if token:
                _access_token = token
                _access_token_expires = time.time() + 7000
                print("[OK] access_token 已刷新")
        except Exception as e:
            print(f"[ERROR] 刷新 access_token 失败: {e}")
        await asyncio.sleep(3600)


async def proactive_chat_scheduler():
    """定时主动发消息的调度器"""
    global _access_token, _last_interaction, PROACTIVE_CHAT
    
    if not PROACTIVE_CHAT:
        print("[主动消息] 已关闭")
        return
    if not WECHAT_USER_OPENID:
        print("[主动消息] 未设置 WECHAT_USER_OPENID，跳过")
        return
    
    print(f"[主动消息] 已启动，间隔 {PROACTIVE_INTERVAL_MIN//3600}-{PROACTIVE_INTERVAL_MAX//3600} 小时")
    
    while True:
        try:
            interval = random.randint(PROACTIVE_INTERVAL_MIN, PROACTIVE_INTERVAL_MAX)
            await asyncio.sleep(interval)
            
            now = time.time()
            if WECHAT_USER_OPENID in _last_interaction:
                elapsed = now - _last_interaction[WECHAT_USER_OPENID]
                # 超过48小时就不能主动发了
                if elapsed > 48 * 3600:
                    print("[主动消息] 超过48小时未互动，无法主动发送")
                    continue
            else:
                print("[主动消息] 尚无互动记录，跳过")
                continue
            
            if not _access_token:
                print("[主动消息] access_token 未就绪")
                continue
            
            # 生成主动消息
            prompt = _pick_proactive_topic()
            print(f"[主动消息] 生成话题: {prompt}")
            
            client = get_client()
            response = await client.chat.completions.create(
                model=os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
                messages=[
                    {"role": "system", "content": """你是小亦，一个细腻灵动、有小脾气的女生。你在微信上给对方发消息。
现在是主动找对方聊天，语气自然，像平时一样。开头可以分享一件小事、问对方在干嘛、或者发一句带情绪的话。
控制在一两句话内，不要长篇大论。"""},
                    {"role": "user", "content": f"现在是{datetime.now().strftime('%H:%M')}，你主动来找我，话题引导：{prompt}。只说一句话开场就好，像微信聊天那样自然。"},
                ],
                max_tokens=200,
                temperature=0.9,
            )
            
            msg = response.choices[0].message.content.strip()
            print(f"[主动消息] 发送: {msg}")
            
            ok = send_custom_message(_access_token, WECHAT_USER_OPENID, msg)
            if ok:
                print("[主动消息] ✓ 已发送")
            else:
                print("[主动消息] ✗ 发送失败")
                
        except Exception as e:
            print(f"[主动消息] 异常: {e}")
            await asyncio.sleep(600)  # 出错等10分钟再试


def _pick_proactive_topic() -> str:
    """随机选一个主动聊天的话题"""
    topics = [
        "分享一件今天发生的小事",
        "问对方在干嘛，带点小情绪",
        "突然想到一个梗，分享给对方",
        "吐槽天气或者心情",
        "分享你刚吃的/喝的/看到的",
        "问对方睡了没，说点睡前的话",
        "哼一声表示对方很久没找你了",
        "分享一首最近在听的歌",
        "突然说一句肉麻的但马上又嘴硬",
    ]
    return random.choice(topics)


@asynccontextmanager
async def lifespan(app: FastAPI):
    tasks = [
        asyncio.create_task(refresh_access_token()),
        asyncio.create_task(proactive_chat_scheduler()),
    ]
    yield
    for t in tasks:
        t.cancel()


app = FastAPI(lifespan=lifespan)


@app.get("/wechat")
async def wechat_verify(
    signature: str = Query(...),
    timestamp: str = Query(...),
    nonce: str = Query(...),
    echostr: str = Query(...),
):
    """微信服务器配置验证 (GET 请求)"""
    if verify_signature(signature, timestamp, nonce, WECHAT_TOKEN):
        return Response(content=echostr)
    return Response(content="signature check failed", status_code=403)


@app.post("/wechat")
async def wechat_message(request: Request):
    """接收微信消息推送 (POST 请求)"""
    body = await request.body()
    xml_str = body.decode("utf-8")
    
    msg = parse_message(xml_str)
    msg_type = msg.get("MsgType", "")
    from_user = msg.get("FromUserName", "")
    to_user = msg.get("ToUserName", "")
    
    # 记录互动时间（用于主动消息判断）
    _last_interaction[from_user] = time.time()
    
    print(f"[MSG] 收到 {msg_type} 消息, 来自: {from_user}")
    
    # 处理文本消息
    if msg_type == "text":
        content = msg.get("Content", "")
        asyncio.create_task(_handle_text_message(from_user, to_user, content))
        return Response(content="success")
    
    # 处理关注事件
    if msg_type == "event" and msg.get("Event") == "subscribe":
        welcome = "嗨！我是小亦～终于等到你啦 ✨\n\n随便聊什么都可以，我会主动找你聊天的嗷 😝"
        return Response(
            content=build_text_reply(from_user, to_user, welcome),
            media_type="application/xml",
        )
    
    return Response(content="success")


async def _handle_text_message(from_user: str, to_user: str, content: str):
    """异步处理文本消息：调用 AI 并通过客服接口回复"""
    global _access_token
    
    try:
        retries = 0
        while not _access_token and retries < 5:
            await asyncio.sleep(2)
            retries += 1
        
        if not _access_token:
            print("[ERROR] access_token 未就绪")
            return
        
        print(f"[AI] 用户说: {content}")
        reply = await ai_chat(from_user, content)
        print(f"[AI] 回复: {reply}")
        
        for chunk in _split_text(reply, max_bytes=2000):
            ok = send_custom_message(_access_token, from_user, chunk)
            if ok:
                print(f"[OK] 已回复")
            else:
                print("[ERROR] 回复失败，尝试刷新 token")
                _access_token = get_access_token(WECHAT_APP_ID, WECHAT_APP_SECRET)
                if _access_token:
                    send_custom_message(_access_token, from_user, chunk)
            await asyncio.sleep(0.5)
            
    except Exception as e:
        print(f"[ERROR] 处理消息异常: {e}")
        if _access_token:
            send_custom_message(_access_token, from_user, "哎呀，我刚刚走神了 😅 再说一遍？")


def _split_text(text: str, max_bytes: int = 2000) -> list[str]:
    """将长文本按字节数分段"""
    chunks = []
    current = ""
    for char in text:
        if len((current + char).encode("utf-8")) > max_bytes:
            chunks.append(current)
            current = char
        else:
            current += char
    if current:
        chunks.append(current)
    return chunks


@app.get("/health")
async def health():
    """健康检查"""
    return {
        "status": "ok",
        "access_token": bool(_access_token),
        "proactive_chat": PROACTIVE_CHAT,
        "last_interaction": {
            k: datetime.fromtimestamp(v, tz=timezone(timedelta(hours=8))).isoformat()
            for k, v in _last_interaction.items()
        },
    }


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
