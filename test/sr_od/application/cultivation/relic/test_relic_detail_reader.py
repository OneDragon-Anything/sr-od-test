"""relic_detail_reader.read_detail 两帧解析单测（% 形态 + 平坦形态）。

fixture = 摸底归档帧（screens/遗器-替换/候选详情词缀.webp 与
候选详情词缀平坦值.webp），断言值全部来自帧实读标定：
- % 形态帧：救世主的登程风帽（头部 +15），主词条生命值 705；副词条
  生命值 6.9%[1]/防御力 9.1%[1]/暴击伤害 22.0%[3]/效果抵抗 3.4%[0 次
  无角标]——角标区域判读生效（行级 OCR 把角标拼进值串「6.9%0」被清洗）。
- 平坦形态帧：先驱的泊星桩锚（脚部 +15），主词条攻击力 43.2%；副词条
  防御力 55[2]/生命值 3.4%[0]/防御力 5.4%[0]/暴击伤害 18.1%[2]——平坦
  与 % 同帧共存，同名异义按 % 后缀消歧不混桶（防御力平坦与防御力提高
  是两个标准名）。

慢计算只算一次：每帧 read_detail 一次调用，全部断言共享其结果（内部
整帧 OCR 缓存复用 + 角标小图 OCR 各一次）。帧缺失时 skip（存档帧属
测试仓资产管理，本地缺失不红）。
"""

import pytest
from cv2.typing import MatLike

from sr_od.application.cultivation.relic.relic_detail_reader import read_detail
from test.conftest import SrTestContext

_FRAME_DIR = '遗器-替换'
_FRAME_PERCENT = '候选详情词缀'
_FRAME_FLAT = '候选详情词缀平坦值'


def _load_frame(test_context: SrTestContext, frame: str) -> MatLike | None:
    """读存档帧；缺失返 None（调用方 skip）。"""
    if not test_context.has_screen(_FRAME_DIR, frame):
        return None
    return test_context.load_screen(_FRAME_DIR, frame)


def test_read_detail_percent_form(test_context: SrTestContext) -> None:
    """% 词条帧：角标判读次数 + 行级 OCR 尾数清洗 + 标准名消歧。"""
    screen = _load_frame(test_context, _FRAME_PERCENT)
    if screen is None:
        pytest.skip(f'存档帧缺失:screens/{_FRAME_DIR}/{_FRAME_PERCENT}.webp')
    detail = read_detail(test_context, screen)
    assert detail is not None, '详情面板帧应解析成功'
    assert detail['piece'] == '救世主的登程风帽'
    assert detail['pos_cn'] == '头部'
    assert detail['level'] == 15
    assert detail['main'] == {'name': '生命值', 'stat': '生命值', 'value': '705'}
    subs = detail['subs']
    assert len(subs) == 4
    assert subs[0] == {'name': '生命值', 'stat': '生命值提高', 'value': '6.9%',
                       'times': 1, 'times_confirmed': True}
    assert subs[1] == {'name': '防御力', 'stat': '防御力提高', 'value': '9.1%',
                       'times': 1, 'times_confirmed': True}
    assert subs[2] == {'name': '暴击伤害', 'stat': '暴击伤害', 'value': '22.0%',
                       'times': 3, 'times_confirmed': True}
    # 0 次无角标：几何确证（confirmed=True）而非 OCR 猜测
    assert subs[3] == {'name': '效果抵抗', 'stat': '效果抵抗', 'value': '3.4%',
                       'times': 0, 'times_confirmed': True}


def test_read_detail_flat_form(test_context: SrTestContext) -> None:
    """平坦词条帧：平坦/% 同帧共存消歧 + 平坦值串清洗（「55②」→「55」）。"""
    screen = _load_frame(test_context, _FRAME_FLAT)
    if screen is None:
        pytest.skip(f'存档帧缺失:screens/{_FRAME_DIR}/{_FRAME_FLAT}.webp')
    detail = read_detail(test_context, screen)
    assert detail is not None, '详情面板帧应解析成功'
    assert detail['piece'] == '先驱的泊星桩锚'
    assert detail['pos_cn'] == '脚部'
    assert detail['level'] == 15
    # 脚部主词条攻击力：% 后缀消歧为「攻击力提高」（平坦/% 同名异义）
    assert detail['main'] == {'name': '攻击力', 'stat': '攻击力提高', 'value': '43.2%'}
    subs = detail['subs']
    assert len(subs) == 4
    # 平坦防御力与 % 防御力是两个标准名，同帧不混桶
    assert subs[0] == {'name': '防御力', 'stat': '防御力', 'value': '55',
                       'times': 2, 'times_confirmed': True}
    assert subs[1] == {'name': '生命值', 'stat': '生命值提高', 'value': '3.4%',
                       'times': 0, 'times_confirmed': True}
    assert subs[2] == {'name': '防御力', 'stat': '防御力提高', 'value': '5.4%',
                       'times': 0, 'times_confirmed': True}
    assert subs[3] == {'name': '暴击伤害', 'stat': '暴击伤害', 'value': '18.1%',
                       'times': 2, 'times_confirmed': True}
