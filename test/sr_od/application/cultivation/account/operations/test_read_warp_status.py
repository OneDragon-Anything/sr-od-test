"""ReadWarpStatusOp 纯函数解析测试。

锁跃迁读数的文本解析契约(OCR 原文 → 结构化读数):
- 池类型按标签关键子串判定,四种池型 + 未知;
- 货币数量容 OCR 噪声(尾部「+」充值按钮、杂字符),无数字返 None;
- 跃迁进度保留「N/M」形态,无斜杠不算进度。

画面事实出处:docs/game/screens/跃迁.md(2026-11-12 六池实机走查,
OCR 噪声形态见 guide_check_power 同类清理先例)。
"""

from sr_od.application.cultivation.account.operations.read_warp_status import (
    POOL_TYPE_CHARACTER,
    POOL_TYPE_COLLAB,
    POOL_TYPE_CONE,
    POOL_TYPE_STANDARD,
    POOL_TYPE_UNKNOWN,
    parse_count,
    parse_pool_type,
    parse_progress,
)


def test_parse_pool_type_by_label_keyword() -> None:
    """四种标签文本(含 OCR 前缀噪声)各判对应池型。"""
    assert parse_pool_type('角色活动跃迁') == POOL_TYPE_CHARACTER
    assert parse_pool_type('光锥活动跃迁') == POOL_TYPE_CONE
    # 联动标签带活动前缀,Fate[UBW] 部分 OCR 可能残缺,按「联动跃迁」子串判
    assert parse_pool_type('Fate[UBW]联动跃迁') == POOL_TYPE_COLLAB
    assert parse_pool_type('联动跃迁') == POOL_TYPE_COLLAB
    assert parse_pool_type('常驻跃迁') == POOL_TYPE_STANDARD


def test_parse_pool_type_unknown_for_empty_or_foreign() -> None:
    """空文本/异类文本 → unknown(调用方 fail,防把加载中误判成常驻池)。"""
    assert parse_pool_type(None) == POOL_TYPE_UNKNOWN
    assert parse_pool_type('') == POOL_TYPE_UNKNOWN
    assert parse_pool_type('推荐商店') == POOL_TYPE_UNKNOWN


def test_parse_count_tolerates_ocr_noise() -> None:
    """数字区 OCR 噪声(尾部+、空格)可解析;无数字 → None。

    契约边界:parse_count 只接纯数量文本(进度「N/M」走 parse_progress,
    不会喂到这里,不测该输入)。
    """
    assert parse_count('12183+') == 12183
    assert parse_count(' 13 ') == 13
    assert parse_count('11') == 11
    assert parse_count(None) is None
    assert parse_count('') is None
    assert parse_count('跃迁') is None


def test_parse_progress_keeps_ratio_form() -> None:
    """进度保留「N/M」原文;无斜杠的文本不算进度(常驻池 area 为空返 None)。"""
    assert parse_progress('0/3200') == '0/3200'
    assert parse_progress(' 1600/3200 ') == '1600/3200'
    assert parse_progress(None) is None
    assert parse_progress('') is None
    assert parse_progress('3200') is None
