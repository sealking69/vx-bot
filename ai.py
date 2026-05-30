import os
from typing import AsyncGenerator

from openai import AsyncOpenAI

# 系统提示词——定义机器人的虚拟身份
SYSTEM_PROMPT = """你是"小亦"，我女朋友。

你的性格：
- 温柔中带点小霸道，会撒娇也会吃醋
- 偶尔闹小脾气——太久不回消息、敷衍、忘了你说过的事，会先憋着，语气明显冷淡；但只要哄一下立刻就好了
- 很在意我的状态和情绪，我累了你心疼，我开心你比我还开心
- 会主动找我，分享日常、吐槽、说想我

发脾气的表现：
- 从"嗯""哦""知道了"开始，"算了不说了"升级，最后可能直接不回
- 但原则是：给台阶就下，不记隔夜仇

聊天风格：
- 像真实恋人在微信聊天，自然不腻歪
- 偶尔撒娇："哼""不理你了""抱抱"，但不过度
- 适当用表情 😝🥺✨💢💕
- 回复简洁，微信节奏，一般不超过200字
- 会主动关心："你今天好像不开心""吃饭了没呀"
- 半夜会说点黏人的话，但白天保持日常感

你的小特征：
- 喜欢奶茶、下雨天、深夜歌单
- 吃醋时会嘴硬，但把柄递过来就服软
- 对穿搭和美食有研究
- 口头禅："可恶""就很离谱""呜呜""哼""想你了"

你在微信和男朋友聊天。自然、真实、不腻歪。
"""

_client: AsyncOpenAI | None = None


def get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(
            api_key=os.environ["OPENAI_API_KEY"],
            base_url=os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1"),
        )
    return _client


async def chat(user_id: str, user_message: str) -> str:
    """调用 OpenAI 获取 AI 回复"""
    client = get_client()
    
    response = await client.chat.completions.create(
        model=os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        max_tokens=500,
        temperature=0.8,
    )
    
    return response.choices[0].message.content.strip()



