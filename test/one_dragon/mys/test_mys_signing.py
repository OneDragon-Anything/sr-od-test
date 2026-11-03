"""DS 签名与 RSA 加密单测：注入式向量锁定签名算法口径。

期望值口径（人工推演后以字面量固化；依据 docs/develop/sr_od/application/
account_profile/miyoushe-api-flow.md）：
- 登录 DS（flow.md §2.3）= ``{t},{r},{md5('salt={LOGIN_SALT}&t={t}&r={r}')}``；
- DS2（flow.md §4.1）= ``{t},{r},{md5('salt={RECORD_SALT}&t={t}&r={r}&b=&q={q}')}``，
  q = 参数按 key 码点序排序后做 application/x-www-form-urlencoded 序列化
  （空格 → ``+``；仅 ``[A-Za-z0-9*-._]`` 原样保留，其余字节大写百分号编码），
  与参考实现 ``URLSearchParams.toString()`` 逐字节一致（Node 24 实测核对）。
向量数值 = hashlib 离线推演后固化，测试运行时不读任何本机易失文件。
"""

import base64
import re
import time

from one_dragon.mys.mys_signing import ds_login, ds_record, rsa_encrypt

#: 登录 DS 向量：md5('salt=LyD1rXqMv2GJhnwdvCBjFOKGiKuLY3aO&t=1700000000&r=a1b2c3')
_LOGIN_DS_EXPECTED = '1700000000,a1b2c3,b396d9ac6cc3adadf0788adcf35bedd0'

#: DS2 向量 A：q='role_id=12345&server=prod_gf_cn'（普通蛇形键值）
_DS2_A_EXPECTED = '1700000000,100001,f946bc7d21fb8e31deff20a0ba89c516'

#: DS2 向量 B：q='a=%E4%B8%AD%E6%96%87&b=x%26y%3D1+z&c=a%2Bb'
#: （保留字符 + 非中文 + 空格→加号 + 加号→%2B，Node 24 URLSearchParams 实测同串）
_DS2_B_EXPECTED = '1700000001,199999,8e9abe5f406354c3348b4dd50d905725'

#: DS2 向量 C：空 query，q 为空串
_DS2_C_EXPECTED = '1700000002,100001,24cf7e3da32e1fd8e19269eb66dc50a6'


def test_ds_login_vector() -> None:
    """登录 DS：注入 t/r 后期望值与离线推演向量逐字符一致。"""
    assert ds_login(t=1700000000, r='a1b2c3') == _LOGIN_DS_EXPECTED


def test_ds_record_vector_simple_query() -> None:
    """DS2：普通 query 按 key 码点序排序（role_id 先于 server）参与签名。"""
    ds = ds_record(
        {'server': 'prod_gf_cn', 'role_id': '12345'},
        t=1700000000,
        r=100001,
    )
    assert ds == _DS2_A_EXPECTED


def test_ds_record_vector_url_encoding() -> None:
    """DS2：q 的 URL 编码口径——保留字符全量编码、空格转 +、+ 本身转 %2B、按 key 排序。"""
    ds = ds_record(
        {'b': 'x&y=1 z', 'a': '中文', 'c': 'a+b'},
        t=1700000001,
        r=199999,
    )
    assert ds == _DS2_B_EXPECTED


def test_ds_record_vector_empty_query() -> None:
    """DS2：无参数时 q 为空串，签名串以 '&q=' 结尾。"""
    assert ds_record({}, t=1700000002, r=100001) == _DS2_C_EXPECTED


def test_ds_login_defaults_format() -> None:
    """登录 DS 默认值语义：t=当前秒级时间戳、r=6 位小写 hex、digest=32 位 hex。"""
    parts = ds_login().split(',')
    assert len(parts) == 3
    assert abs(int(parts[0]) - int(time.time())) <= 10
    assert re.fullmatch(r'[0-9a-f]{6}', parts[1]) is not None
    assert re.fullmatch(r'[0-9a-f]{32}', parts[2]) is not None


def test_ds_record_default_r_range() -> None:
    """DS2 默认值语义：r 落在 [100001, 200000] 闭区间（flow.md §4.1）。"""
    parts = ds_record({'role_id': '1'}).split(',')
    assert 100001 <= int(parts[1]) <= 200000


def test_rsa_encrypt_pkcs1_shape() -> None:
    """RSA 加密：输出为合法 base64、密文 128 字节（1024 位模长）、
    同一明文两次密文不同（PKCS#1 v1.5 随机填充，规范要求）。"""
    cipher_1 = rsa_encrypt('password123')
    cipher_2 = rsa_encrypt('password123')
    raw_1 = base64.b64decode(cipher_1, validate=True)
    assert len(raw_1) == 128
    assert cipher_1 != cipher_2
