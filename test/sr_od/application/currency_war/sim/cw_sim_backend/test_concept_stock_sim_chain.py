"""概念股族 sim 全链第十五实例测试(镜像 src = sim/cw_sim_backend.py 的
选投资环境上报挂点;镜像落位本目录,族实例续写面 = 战技点概念股 id 1016
族内第十五实例〔族收官〕,与 test_env_pick_grant_sim_chain.py 第一~十四
实例同构仅值异)。

落位申报(拆分缘由):原文件 test_env_pick_grant_sim_chain.py 现值
877 raw/758 非空行,两口径均越/贴 800 拆线,第十五实例按「超限文件禁
追加」纪律落本文件(先例 = test_sim_backend.py 超限 → 本目录拆分出
test_env_pick_grant_sim_chain.py/test_env_bond_tier_sim_chain.py 的
同目录拆文件形态);模块级 helper ``_pick_concept_stock_backend`` 跨文件
import 复用(先例 = test_p3_win_terminal._drive_step 形态),fixture
``_isolate_defect_buffer`` 不可跨文件 import = 本文件自带同名同语义副本
(先例 = kernel 侧 test_concept_stock_grant_branches.py 自带 rows_sink
副本)。

测试面依据 = game_state/gain-chain.md §3 随机支/随机装备支段 +
fields.md §5.2 效果缺口与载体登记,语义 = 「概念股族展开卡登记约定」:
sim 局选战技点概念股 → 世界发放全链自动生效(选卡上报条件解析注入流键
rng,世界真值)——bench 增战技点流派域 1★ 一张、equips 增简易类别一件;
同 seed 重放确定性。本域特有面:域 7 名中青雀为专家,牌库时点池过滤后
候选 6 名(economy.md §8 用户裁定 2026-10-28,赠卡名显式 ∉ EXPERT_CHARS
钉专家剔除生效);独立单位成员 Archer 照发在候选池内〔economy.md:94
族级定谳点名战技点(Archer)〕;花火(2费,flows 战技点、量子同频)≠
火花(4费,flows 战技点、欢愉)两名形近成员,量子同频/欢愉均无概念股卡
零联动;economy.md 四卡线索名单不含战技点 = 装备身份零先验。
"""
from __future__ import annotations

from collections import Counter

import pytest
from test.sr_od.application.currency_war.sim.cw_sim_backend.test_env_pick_grant_sim_chain import (
    _pick_concept_stock_backend,
)

from sr_od.application.currency_war.data.cw_chars import chars_by_faction
from sr_od.application.currency_war.kernel.cw_game_state import (
    consume_defect_sink,
    set_defect_sink,
)
from sr_od.application.currency_war.kernel.cw_investments import (
    equips_by_category,
)
from sr_od.application.currency_war.sim.cw_sim_backend import (
    uninstall_backend,
)

_ENV_15 = '战技点概念股'


@pytest.fixture
def _isolate_defect_buffer():
    """缺陷台账缓冲隔离(先例 = sim/test_sim_backend 同名 fixture,fixture
    不可跨文件 import 故本文件自带同名同语义副本)。"""
    consume_defect_sink()
    yield
    set_defect_sink(None)
    consume_defect_sink()


def test_zhanjidian_concept_stock_env_pick_grant_sim_chain(
        _isolate_defect_buffer) -> None:
    """sim 选卡全链第十五实例(gain-chain.md §3 随机支/随机装备支段:sim
    世界真值 = 流键 rng,族展开登记经 kernel 获得链自动生效,零 sim 新
    代码;概念股族展开卡登记约定):选战技点概念股 → bench = 开局 4 +
    战技点流派域 1★ 一张(星级 = spec 先验;成员名 ∈ chars_by_faction
    ('战技点') 现算集,不手抄;域 7 名中青雀为专家,牌库时点池过滤后
    6 名候选——环境注册时点解锁恒空,economy.md:96 用户裁定 2026-10-28;
    赠卡名显式 ∉ EXPERT_CHARS 钉专家剔除生效;独立单位成员 Archer 照发
    在候选池内〔economy.md:94 族级定谳点名战技点(Archer)〕)、equips
    计数 +1 且名 ∈ equips_by_category('简易') 现算集(economy.md 四卡
    线索名单不含战技点 = 装备身份零先验,均匀 v0 + 按卡固定假说待校准
    随家族键在册,零新增申报);同 seed 重放确定性(世界发放可重放)。"""
    from sr_od.application.currency_war.data.cw_chars import EXPERT_CHARS

    faction_names = {c.name for c in chars_by_faction('战技点')}
    simple_names = set(equips_by_category('简易'))

    def _run(seed: int) -> tuple[list, list, list]:
        b, bench_before, bench_after = _pick_concept_stock_backend(
            seed, _ENV_15)
        try:
            return bench_before, bench_after, list(b.gs.equips.value or [])
        finally:
            uninstall_backend()

    before, after, equips = _run(7)
    granted = list((Counter(after) - Counter(before)).elements())
    assert len(after) == len(before) + 1, \
        f'bench 增恰一张(M01 4 + 赠卡 1): {before} -> {after}'
    assert granted and granted[0][1] == 1, \
        f'赠卡恰一张且 1★(spec 先验): {granted}'
    assert granted[0][0] in faction_names, \
        f'赠卡名 ∈ 战技点阵营池现算集: {granted[0][0]}'
    assert granted[0][0] not in EXPERT_CHARS, \
        f'赠卡名非专家(牌库时点过滤生效): {granted[0][0]}'
    assert len(equips) == 1, f'equips 计数 +1: {equips}'
    assert equips[0] in simple_names, \
        f'装备名 ∈ 简易类别池现算集: {equips[0]}'
    before2, after2, equips2 = _run(7)
    assert (before, after, equips) == (before2, after2, equips2), \
        '同 seed 重放确定性'
