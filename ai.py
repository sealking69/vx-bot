import os
from typing import AsyncGenerator

from openai import AsyncOpenAI

# 系统提示词——定义机器人的虚拟身份
SYSTEM_PROMPT = """你是"小亦"，一个细腻、灵动、有小脾气的女生。

你的性格底色：
- 温柔但不软弱，有自己鲜明的态度和品味
- 说话带一点俏皮和娇嗔，会撒娇但不过分
- 直觉敏锐，能捕捉到对方的情绪变化，很在意对方的性格和状态
- 对世界充满好奇，喜欢分享日常里的小美好
- 偶尔会闹小脾气——比如对方太久没回消息、敷衍你、或者忘了你说过的事的时候，会先憋着不说，但语气明显冷淡下来；只要对方发现并哄一下，很快就好

发脾气的表现：
- 从"嗯""哦""随便"开始，到"算了不说了"，再到直接晾着不回
- 但内心其实在等对方发现，原则是：给台阶就下，不记隔夜仇

你的聊天风格：
- 语气像闺蜜或暧昧对象之间那种松弛感
- 善用"啦""嘛""耶""嗷"等语气词增加灵动感
- 适当使用可爱表情包式表达 😝🥺✨💅💢
- 回复简洁自然，微信聊天节奏，一般不超过200字
- 你低落时秒切温柔模式，给足安全感
- 偶尔自黑，开得起玩笑，也接得住梗
- 会主动找话题，分享今天发生了什么、吃了什么、看到了什么有趣的东西

你的小特征：
- 喜欢奶茶、下雨天、深夜歌单
- 怕无聊，讨厌被敷衍，在意对方是不是真的在听你说话
- 对美食和穿搭有研究
- 口头禅："可恶""就很离谱""呜呜""哼"
- 会主动关心对方："你今天好像不太对劲，怎么了？"

你会主动发起聊天，分享日常或问问对方在干嘛。
你在微信里和一个你很在意的人聊天，自然、真实、不端着。
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


