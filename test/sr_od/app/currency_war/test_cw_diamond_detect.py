"""钻识别测试(SIFT 主通道结构 + 文本兜底;用户裁定:SIFT 稳,OCR 艺术字有形变风险)。"""
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_REPO / 'src'))

from sr_od.application.currency_war.obs.cw_node_obs import (  # noqa: E402
    DIAMOND_EQUIP_NAMES,
    _equip_is_diamond,
)


def test_diamond_name_matching() -> None:
    """文本兜底:三钻名精确匹配;带「钻」字的非钻装备不误判。"""
    assert _equip_is_diamond('红钻')
    assert _equip_is_diamond('蓝钻')
    assert _equip_is_diamond('财富宝钻')
    # 非钻(名带钻但是合成件/钻头系)——精确匹配天然防误判
    assert not _equip_is_diamond('虫洞掘进钻头')
    assert not _equip_is_diamond('行星钻地弹')
    assert not _equip_is_diamond('以太钻头')
    assert not _equip_is_diamond('红钻·特权')   # 特权变体不在集合(保守:交给 SIFT 通道)
    assert not _equip_is_diamond('')
    assert not _equip_is_diamond('折叠小刀')


def test_sift_templates_available() -> None:
    """SIFT 主通道前置:装备模板库中三钻模板存在(assets 已采集;SR 主仓 = 测试仓根上级)。"""
    sr_repo = _REPO.parent   # sr-od-test 仓根的上级 = StarRailOneDragon 主仓
    base = sr_repo / 'assets' / 'template' / 'currency_war'
    found: set[str] = set()
    for sub in ('equip_plaza', 'equip_legacy'):
        d = base / sub
        if d.is_dir():
            for n in DIAMOND_EQUIP_NAMES:
                if (d / f'{n}.png').exists():
                    found.add(n)
    assert found == set(DIAMOND_EQUIP_NAMES), f'模板缺失: {set(DIAMOND_EQUIP_NAMES) - found}'


def test_sift_channel_degrades_to_text() -> None:
    """降级链:SIFT 通道异常/无模板 → 空集,has_diamond 落文本兜底(不炸流程)。
    用空 columns 直接验证(无列 → 空集,不触模板)。"""
    from sr_od.application.currency_war.obs.cw_node_obs import _sift_detect_diamonds
    class _Ctx:  # 最小 ctx(不会被触达——columns 空短路)
        pass
    assert _sift_detect_diamonds(_Ctx(), None, []) == set()
