import time
import hashlib
import xml.etree.ElementTree as ET
from typing import Optional

import requests
from Crypto.Cipher import AES
import base64
import struct


def verify_signature(
    signature: str,
    timestamp: str,
    nonce: str,
    token: str,
) -> bool:
    """验证微信服务器签名"""
    tmp_list = sorted([token, timestamp, nonce])
    tmp_str = "".join(tmp_list)
    computed = hashlib.sha1(tmp_str.encode()).hexdigest()
    return computed == signature


def decrypt_message(
    encrypted: str,
    encoding_aes_key: str,
    app_id: str,
) -> tuple[str, str]:
    """解密微信加密消息, 返回 (明文XML, 消息ID)"""
    aes_key = base64.b64decode(encoding_aes_key + "=")
    cipher = AES.new(aes_key, AES.MODE_CBC, iv=aes_key[:16])
    decrypted = cipher.decrypt(base64.b64decode(encrypted))
    
    # 去除 PKCS7 padding
    pad = decrypted[-1]
    decrypted = decrypted[:-pad]
    
    # 前16字节是随机字符串
    content = decrypted[16:]
    # 接下来4字节是消息长度
    msg_len = struct.unpack(">I", content[:4])[0]
    msg = content[4:4 + msg_len].decode("utf-8")
    received_app_id = content[4 + msg_len:].decode("utf-8")
    
    return msg, received_app_id


def encrypt_message(
    plain: str,
    encoding_aes_key: str,
    app_id: str,
) -> str:
    """加密回复消息"""
    aes_key = base64.b64decode(encoding_aes_key + "=")
    
    random_bytes = hashlib.sha1(str(time.time()).encode()).digest()[:16]
    msg_bytes = plain.encode("utf-8")
    msg_len = struct.pack(">I", len(msg_bytes))
    app_id_bytes = app_id.encode("utf-8")
    
    raw = random_bytes + msg_len + msg_bytes + app_id_bytes
    
    # PKCS7 padding
    pad = 32 - len(raw) % 32
    raw += bytes([pad] * pad)
    
    cipher = AES.new(aes_key, AES.MODE_CBC, iv=aes_key[:16])
    encrypted = cipher.encrypt(raw)
    return base64.b64encode(encrypted).decode()


def parse_message(xml_str: str) -> dict:
    """解析微信推送的 XML 消息"""
    root = ET.fromstring(xml_str)
    msg = {}
    for child in root:
        msg[child.tag] = child.text or ""
    return msg


def build_text_reply(to_user: str, from_user: str, content: str) -> str:
    """构建文本回复 XML"""
    return f"""<xml>
<ToUserName><![CDATA[{to_user}]]></ToUserName>
<FromUserName><![CDATA[{from_user}]]></FromUserName>
<CreateTime>{int(time.time())}</CreateTime>
<MsgType><![CDATA[text]]></MsgType>
<Content><![CDATA[{content}]]></Content>
</xml>"""


def get_access_token(app_id: str, app_secret: str) -> Optional[str]:
    """获取微信 access_token"""
    url = (
        f"https://api.weixin.qq.com/cgi-bin/token"
        f"?grant_type=client_credential&appid={app_id}&secret={app_secret}"
    )
    resp = requests.get(url, timeout=10)
    data = resp.json()
    if "access_token" in data:
        return data["access_token"]
    print(f"[ERROR] 获取 access_token 失败: {data}")
    return None


def send_custom_message(
    access_token: str,
    to_user: str,
    content: str,
) -> bool:
    """通过客服消息接口回复用户（无5秒限制）"""
    url = (
        f"https://api.weixin.qq.com/cgi-bin/message/custom/send"
        f"?access_token={access_token}"
    )
    body = {
        "touser": to_user,
        "msgtype": "text",
        "text": {"content": content},
    }
    resp = requests.post(url, json=body, timeout=10)
    result = resp.json()
    if result.get("errcode") == 0:
        return True
    print(f"[ERROR] 发送客服消息失败: {result}")
    return False
