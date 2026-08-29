"""select_megastar comp 级偏好绑定测试(strategy/19 P2 重写)。"""
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_REPO / 'src'))

from sr_od.application.currency_war.kernel.cw_comps import (  # noqa: E402
    COMP_LIBRARY,
    COMP_MEGASTAR_PREFERENCE,
    select_megastar,
)

_ALL = ['大丽花', '加拉赫', '花火', '星期日', '知更鸟', '黑天鹅', '星徽']


class _S:
    pass


def _by_name(name: str):
    return next(c for c in COMP_LIBRARY if c.name == name)


def test_front_carry_binds_sunday() -> None:
    """前台单核族 → 星期日(132% 前台首位直乘)。"""
    s = _S()
    for name in ('反甲白厄', '万敌单C', '命运圣杯红A', '双王圣杯', '昼神阿雅'):
        assert select_megastar(s, _by_name(name), _ALL) == '星期日', name


def test_crit_engine_binds_robin() -> None:
    """暴击引擎族(群攻/欢愉/追击)→ 知更鸟(幸运一击率 +55%)。"""
    s = _S()
    for name in ('追击飞霄', '银枝群攻', '大黑塔银河学者', '希儿量子', '绯英欢愉', '狼尊欢愉'):
        assert select_megastar(s, _by_name(name), _ALL) == '知更鸟', name


def test_engine_families() -> None:
    """战技点 → 花火;击破 → 大丽花;DoT 5费堆叠 → 黑天鹅。"""
    s = _S()
    assert select_megastar(s, _by_name('龙丹战技点'), _ALL) == '花火'
    assert select_megastar(s, _by_name('列车同行'), _ALL) == '花火'   # 花火 core 先绑
    assert select_megastar(s, _by_name('巡海击破'), _ALL) == '大丽花'
    assert select_megastar(s, _by_name('DOT队'), _ALL) == '黑天鹅'
    assert select_megastar(s, _by_name('专家桑博DOT'), _ALL) == '黑天鹅'


def test_preference_respects_availability() -> None:
    """首选不在场 → 依偏好序取次选;core 在场永远优先。"""
    s = _S()
    # 白厄局,星期日不在场 → 知更鸟
    assert select_megastar(s, _by_name('反甲白厄'),
                           ['知更鸟', '花火', '黑天鹅']) == '知更鸟'
    # 追击飞霄,知更鸟(core)在场 → 直接绑
    assert select_megastar(s, _by_name('追击飞霄'), ['花火', '知更鸟']) == '知更鸟'
    # 巡海击破,大丽花/加拉赫都不在 → 知更鸟(偏好序第三)
    assert select_megastar(s, _by_name('巡海击破'),
                           ['知更鸟', '花火']) == '知更鸟'


def test_unlisted_comp_falls_back_attributes() -> None:
    """偏好表未列的 comp 走机械属性兜底(千冶/黄泉减益无强绑定)。"""
    s = _S()
    # 黄泉减益 attrs=['减益'] 兜底表无 → naive 首个
    assert select_megastar(s, _by_name('黄泉减益'), _ALL) == _ALL[0]


def test_preference_table_covers_and_valid() -> None:
    """偏好表健全性:键全部是真实 comp;值全部是真实巨星。"""
    comp_names = {c.name for c in COMP_LIBRARY}
    assert set(COMP_MEGASTAR_PREFERENCE) <= comp_names
    for stars in COMP_MEGASTAR_PREFERENCE.values():
        assert set(stars) <= set(_ALL)
