"""select_megastar comp 级偏好绑定测试(strategy/19 P2 重写)。

出处:被测模块本体——现行基建锁(模块见本文件 import;设计总览 docs/develop/currency_war/strategy/README.md)(2026-08-31 测试瘦身批考证补记)。"""
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
    """暴击引擎族(群攻/欢愉/追击)→ 知更鸟(幸运一击率 +55%)。

    希儿量子例外(修复项1,2026-08-31):core 修正后 花火(盛会之星,63/67 第二引擎)
    入 core —— select 序 1「core 里的盛会之星」优先于偏好序,故绑 花火(战技点引擎,
    与量子线拉条链同构);知更鸟已移出 core(n=67 非核心组),退偏好序次选。"""
    s = _S()
    for name in ('追击飞霄', '银枝群攻', '大黑塔银河学者', '绯英欢愉', '狼尊欢愉'):
        assert select_megastar(s, _by_name(name), _ALL) == '知更鸟', name
    assert select_megastar(s, _by_name('希儿量子'), _ALL) == '花火'   # core 优先(修复项1)


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


def test_no_target_and_empty_candidates() -> None:
    """target=None → 首个可选;候选空 → None(select_megastar 出口契约)。

    语义自 test_cw_comps 的 no_target/empty 两测归并(select_megastar 主题文件,
    README 纪律 14);原位待其文件批删除。空候选门在生产函数首行短路、先于
    target 分支,故有 target + 空候选同走 None 出口(分支序一并锁定)。"""
    s = _S()
    assert select_megastar(s, None, ['花火', '知更鸟']) == '花火'
    assert select_megastar(s, None, []) is None
    assert select_megastar(s, _by_name('反甲白厄'), []) is None


# (select_megastar_enhance 绑定序锁段已随 megastar_enhance_enabled 开关族
#  删除——旧方案清退批,清查报告 OLD_MIX_AUDIT §1.3;函数与开关同批删,
#  MegastarPick.enhance_char_id 字段保留恒 None。)
