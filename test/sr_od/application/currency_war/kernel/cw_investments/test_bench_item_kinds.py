"""占席道具映射桥 BENCH_ITEM_KINDS 测试(镜像 src = kernel/cw_investments.py,
被测 = 映射表数据性质,按拆目录规范落位;同 src 兄弟测试 =
kernel/test_cw_investments.py〔已登记超限文件,只读复用不追加〕)。

测试面依据 = 原稿锁面 effects-calc/本文件锁面申报)§2.2 + §4 锁 1;
2026-10-28 校验治理后 `_validate_bench_item_kinds` 已删(键集双向闭合/
值域封闭属防登记笔误类,漏登的运行期后果 = 落席直查 KeyError 响亮可见)。

v4.7 换季语义修正(T-5 r2 编排者裁定):原「映射键集 == 授予通道并集」
双向闭合把「道具是什么类」(识别面/落席语义,识别器与开卡链基础设施
保留 = 键必须存在)与「谁发放」(当期卡池,V4.7 专家邀请函无发放源)
两个域耦死——S1 全盛期两域恰好一致,换季暴露耦合错位。守卫改两条
单向锁:
- 授予通道道具名(items_* 通道) ⊆ 映射键(发放来的必须可落席);
- 识别面钉名三组(武装箱族 supply_box/专家邀请函 bookcard/星徽秘典
  tome)↔ 映射一致(字面量钉名,防识别面改名漂移)。
「映射键 ⊆ 授予并集」反向约束删除(专家邀请函无发放源键合法在场)。
"""
from __future__ import annotations

from sr_od.application.currency_war.kernel.cw_investments import (
    BENCH_ITEM_KINDS,
    BENCH_ITEM_NAMES,
    ENV_GIFTS,
    STRATEGY_GRANTS,
)


def _granted_item_names() -> set[str]:
    """授予通道占席道具名并集(期望单一来源 = 登记表本身,不手抄)。"""
    granted: set[str] = set()
    for grant in (*ENV_GIFTS.values(), *STRATEGY_GRANTS.values()):
        granted.update(grant.items_immediate)
        granted.update(item for _node_key, item in grant.items_scheduled)
    return granted


def test_bench_item_kinds_cover_granted_items() -> None:
    """授予通道单向锁:items_* 通道发放的道具必须 ∈ 映射键(落席直查
    KeyError 的前置防线;反向「映射键 ⊆ 授予」不约束——识别面键可先于
    发放源在场,专家邀请函 V4.7 无发放源键保留见 src 表注)。"""
    missing = _granted_item_names() - set(BENCH_ITEM_KINDS)
    assert not missing, f'发放通道道具缺落席登记: {sorted(missing)}'


def test_bench_item_kinds_pinned_names_match_recognition() -> None:
    """识别面钉名三组 ↔ 映射一致(字面量钉名防漂移;识别器/开卡链按
    道具名直查映射,改名即落席身份错派):
    - 武装箱族 = supply_box(简/特权/进阶三品名同布局弹窗异文案);
    - 专家邀请函 = bookcard(开卡动作链首例槽件);
    - 星徽秘典 = tome(四选一开典籍链槽件)。"""
    assert BENCH_ITEM_KINDS['简易武装箱'] == 'supply_box'
    assert BENCH_ITEM_KINDS['特权武装箱'] == 'supply_box'
    assert BENCH_ITEM_KINDS['进阶武装箱'] == 'supply_box'
    assert BENCH_ITEM_KINDS['专家邀请函'] == 'bookcard'
    assert BENCH_ITEM_KINDS['星徽秘典'] == 'tome'


def test_bench_item_names_derived_from_kinds() -> None:
    """词表派生锁:BENCH_ITEM_NAMES = 映射键集派生(单一源,不手抄)。"""
    assert frozenset(BENCH_ITEM_KINDS) == BENCH_ITEM_NAMES, '词表派生自映射'
