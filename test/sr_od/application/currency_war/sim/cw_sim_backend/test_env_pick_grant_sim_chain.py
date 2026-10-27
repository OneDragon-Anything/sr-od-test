"""环境直发策略取卡挂点 sim 全链轻量局测试(镜像 src = sim/cw_sim_backend.py
的 ``_begin_node_window`` 直发发放事件;按流程级测试落位本目录,引擎驱动
助手 import 自 sim/test_sim_backend.py〔在册超限拆分债文件,禁追加,只
import 复用不改;先例 = 本目录 test_env_bond_tier_sim_chain.py〕)。

测试面依据 = 迭代 2026-09-23-invest-effects-calc designs/
T-46-celue-dashi.md(定稿)§4 锁 5(§2.2(e) 落地形态):
- 定向策略大师推进至 P3r5 → 无选卡屏、active_strategies +1(随机新策略,
  排除已拥有)、发放行金额 = 2×直发后持有数(直发本身触发金币腿的耦合锁,
  金额对账 = 发放行值 − 同窗轮首收入行值,与收入数值解耦);
- 直发后 excluded_invest 含到手名(全程去重契约锁);
- 窗口重放不双发(幂等守卫族语义锁,boss 先例同款断言位);
- 非挂点节点不发;表外环境不发。

追加面 = 概念股族模式卡(正本 = game_state/gain-chain.md §3 随机支/随机
装备支段 + fields.md §5.2 效果缺口与载体登记,语义 = 「概念股族模式卡
登记约定」):sim 局选追击概念股 → 世界发放全链自动生效(选卡上报条件
解析注入流键 rng,世界真值)——bench 增追击阵营域 1★ 一张、equips 增
简易类别一件;同 seed 重放确定性。

再追加面 = 概念股族展开卡(燃血概念股 id 1002 族内第二实例/能量概念股
id 1003 第三实例/列车同行概念股 id 1004 第四实例/银河学者概念股
id 1005 第五实例/贝洛伯格概念股 id 1006 第六实例,概念股族展开卡登记
约定,正本同上):与追击全链同构
仅值异——期望名改从对应阵营池/简易池现算(列车同行域 = 开拓者双形态
按角色位合并后 7 名池,采样即发放名恒欢愉;银河学者域无开拓者条目,
合并对本域零作用,池 = 原始域;贝洛伯格域 = 布洛妮娅双羁绊注册表修正
后 6 名池,独立单位照发),选卡助手按环境名参数化(追击调用点
缺省值不变)。
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from test.sr_od.application.currency_war.sim.cw_sim_backend.test_p3_win_terminal import (
    _drive_step,
)
from test.sr_od.application.currency_war.sim.test_sim_backend import (
    _env_pick_backend,
    _force_settle,
    _seed_and_pick_env,
)

from sr_od.application.currency_war.data.cw_chars import chars_by_faction
from sr_od.application.currency_war.kernel.cw_action_report import (
    report_action_pick_invest_env_param,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    ChannelSig,
    consume_defect_sink,
    set_defect_sink,
)
from sr_od.application.currency_war.kernel.cw_investments import (
    equips_by_category,
)
from sr_od.application.currency_war.sim import cw_sim_ports
from sr_od.application.currency_war.sim.cw_sim_backend import (
    SCREEN_BRIEFING,
    SCREEN_INVEST_ENV,
    SCREEN_INVEST_STRATEGY,
    SimBackend,
    uninstall_backend,
)

_SIG = ChannelSig(family='logic_action', actor='T46PickGrantTest',
                  mode='compute')

_ENV = '策略大师'
_FOREIGN_ENV = '增发货币'   # ENV_ECONOMY 成员 ∉ ENV_PICK_GRANTS/ENV_POOL_REWRITE


@pytest.fixture
def _isolate_defect_buffer():
    """缺陷台账缓冲隔离(先例 = sim/test_sim_backend 同名 fixture,fixture
    不可跨文件 import 故本文件自带同名同语义副本)。"""
    consume_defect_sink()
    yield
    set_defect_sink(None)
    consume_defect_sink()


def _node_pos(b: SimBackend) -> tuple[int, int] | None:
    """当前节点序位(节点未进窗 = None)。"""
    node = b.gs.node.value
    return None if node is None else (node.plane, node.round_num)


def _drive_until_pos(b: SimBackend, pos: tuple[int, int],
                     limit: int = 512) -> None:
    """步进驱动至节点序位(超限响错防死循环;单步助手 =
    test_p3_win_terminal._drive_step——位面过渡屏在其分派表内,
    test_sim_backend._drive_env_grant_step 无该档,达 P3 必经)。"""
    for _ in range(limit):
        if _node_pos(b) == pos:
            return
        _drive_step(b, 37)
    raise AssertionError(f'驱动步数超限,未达 {pos}')


def _record_write_values(gs, monkeypatch: pytest.MonkeyPatch
                         ) -> list[tuple[str, str, str | None, object]]:
    """记录 (通道, 字段, evidence, 写入值) 四元写行(test_sim_backend
    ._record_all_writes 同式包装,本文件版增记 value 供发放金额对账;
    透传真实现零行为变化)。"""
    rows: list[tuple[str, str, str | None, object]] = []

    def _wrap_logic(real, channel: str):
        def rec(target, value, *, produced_by, evidence=None, sig, note=''):
            rows.append((channel, gs._field_name(target), evidence, value))
            real(target, value, produced_by=produced_by, evidence=evidence,
                 sig=sig, note=note)
        return rec

    def _wrap_obs(real):
        def rec(target, value, *, evidence=None, sig, note=''):
            rows.append(('obs', gs._field_name(target), evidence, value))
            real(target, value, evidence=evidence, sig=sig, note=note)
        return rec

    monkeypatch.setattr(gs, 'write_logic', _wrap_logic(gs.write_logic,
                                                       'logic'))
    monkeypatch.setattr(gs, 'write_logic_rand',
                        _wrap_logic(gs.write_logic_rand, 'rand'))
    monkeypatch.setattr(gs, 'observe', _wrap_obs(gs.observe))
    return rows


def _grant_gold_rows(rows: list[tuple[str, str, str | None, object]]
                     ) -> list[tuple[str, str, str | None, object]]:
    """直发金币腿写行(evidence = env_grant#<环境>#pick<k> 的 gold 行)。"""
    return [r for r in rows if r[0] == 'logic' and r[1] == 'gold'
            and r[2] and r[2].startswith('env_grant#策略大师#pick')]


def test_direct_grant_fires_at_p3r5_no_offer_screen(
        monkeypatch: pytest.MonkeyPatch, _isolate_defect_buffer) -> None:
    """主锁(T-46 设计 §4 锁 5):策略大师局推进至 P3r5 窗口 → 直发恰
    一张(随机新策略,排除已拥有)、无选卡屏(窗后直落节点屏)、发放行
    金额 = 2×直发后持有数(直发经获得链自动触发金币腿)、到手名并入
    excluded_invest。结算恒胜桩保全程存活(死亡腿与本测无关)。
    非挂点节点不发:r4 窗开时点已入快照基线——若误挂 (3,4),直发卡已在
    held_before 内、r5 段零新发放行,本组断言即红(最近邻非挂点窗负例;
    表外环境负例另测)。"""
    _force_settle(monkeypatch, True)
    b = _env_pick_backend(7)
    try:
        gs = b.gs
        _seed_and_pick_env(b, _ENV)
        assert gs.active_env.value == _ENV, '选卡事实前置'
        rows = _record_write_values(gs, monkeypatch)
        _drive_until_pos(b, (3, 4))
        held_before = list(gs.active_strategies.value or [])
        grants_before = len(_grant_gold_rows(rows))
        _drive_until_pos(b, (3, 5))
        # 无选卡屏:直发不开 offer,窗后直落节点屏
        assert b.screen_identity() != SCREEN_INVEST_STRATEGY, '无选卡屏'
        held_after = list(gs.active_strategies.value or [])
        assert len(held_after) == len(held_before) + 1, \
            f'r5 窗直发恰一张: {held_before} -> {held_after}'
        name = held_after[-1]
        assert name not in held_before, '随机新策略(排除已拥有)'
        # 直发本身触发金币腿(耦合锁):r4→r5 段恰一行新发放写,
        # 金额 = 2×直发后持有数(与同窗轮首收入解耦的差分;
        # 前段既有行 = offer 取卡腿各行,同 evidence 形态属预期)
        grants_after = _grant_gold_rows(rows)
        assert len(grants_after) == grants_before + 1, \
            f'r5 段恰一行新发放写: {grants_before} -> {len(grants_after)}'
        grant = grants_after[-1]
        assert grant[2] == f'env_grant#{_ENV}#pick{len(held_after)}', \
            f'evidence 携含本张 k: {grant[2]}'
        idx = rows.index(grant)
        income_value = next(r[3] for r in reversed(rows[:idx])
                            if r[1] == 'gold')
        assert int(grant[3]) - int(income_value) == 2 * len(held_after), \
            f'金额 = 2×含本张持有数: {grant[3]} - {income_value}'
        # 全程去重契约:到手名并入 excluded_invest
        assert name in b.excluded_invest, \
            f'到手名并入排除集: {name} ∉ {sorted(b.excluded_invest)}'
    finally:
        uninstall_backend()


def test_window_replay_no_double_grant(
        monkeypatch: pytest.MonkeyPatch, _isolate_defect_buffer) -> None:
    """窗口重放不双发(幂等守卫族语义锁,boss 先例同款断言位):P3r5 窗
    已开(直发已落)后,同节点二次 ``_begin_node_window`` 零二次发放
    (持有数与金不动)。"""
    _force_settle(monkeypatch, True)
    b = _env_pick_backend(7)
    try:
        gs = b.gs
        _seed_and_pick_env(b, _ENV)
        _drive_until_pos(b, (3, 5))
        held_at_window = len(gs.active_strategies.value or [])
        assert held_at_window >= 1, '直发已落(窗口已开)'
        rows = _record_write_values(gs, monkeypatch)
        b._begin_node_window()
        assert len(gs.active_strategies.value or []) == held_at_window, \
            '重放零二次发放(持有不动)'
        assert _grant_gold_rows(rows) == [], '重放零发放写行'
    finally:
        uninstall_backend()


def test_foreign_env_no_grant_at_p3r5(
        monkeypatch: pytest.MonkeyPatch, _isolate_defect_buffer) -> None:
    """表外环境不发(T-46 设计 §4 锁 5):登记表外环境(增发货币)局
    推进至 (3,5) 窗口 → 零直发(持有不动、零 env_grant gold 写行);
    direct 挂点查询 get None = 无直发的合法语义。"""
    _force_settle(monkeypatch, True)
    b = _env_pick_backend(7)
    try:
        gs = b.gs
        _seed_and_pick_env(b, _FOREIGN_ENV)
        assert gs.active_env.value == _FOREIGN_ENV
        rows = _record_write_values(gs, monkeypatch)
        _drive_until_pos(b, (3, 4))
        held_at_r4 = len(gs.active_strategies.value or [])
        _drive_until_pos(b, (3, 5))
        assert len(gs.active_strategies.value or []) == held_at_r4, \
            '表外环境零直发(持有不动)'
        assert _grant_gold_rows(rows) == [], '表外环境零 env_grant 写行'
    finally:
        uninstall_backend()


# ============================================================ 概念股族全链
# (选追击概念股:随机阵营赠卡 + 随机简易装备经 kernel 获得链自动双端
# 生效,零 sim 新代码;正本 = game_state/gain-chain.md §3 随机支/随机
# 装备支段 + fields.md §5.2 效果缺口与载体登记。)

_CONCEPT_ENV = '追击概念股'


def _bench_units(gs) -> list[tuple[str, int]]:
    return [(s.unit.char_id, s.unit.star)
            for s in gs.bench.value.slots
            if s is not None and s.kind == 'unit' and s.unit is not None]


def _pick_concept_stock_backend(seed: int,
                                env_name: str = _CONCEPT_ENV
                                ) -> tuple[SimBackend, list, list]:
    """驱动到环境选卡屏并选指定概念股(缺省 = 追击概念股,T-48 调用点
    不变;选卡前 bench 快照,防开局手牌巧合同阵营致成员计数失真;选卡
    步骤 = _seed_and_pick_env 同链展开,快照插入在播种 opts 之后、上报
    之前)。"""
    b = _env_pick_backend(seed)
    b._handle_click_source(SCREEN_BRIEFING, '按钮-下一步')
    assert b.screen_identity() == SCREEN_INVEST_ENV, '驱动至环境选卡屏'
    b.gs.write_logic(b.gs.invest_env_opts, [env_name, '轮岗', '头彩'],
                     produced_by='Test', evidence='t:opts',
                     sig=ChannelSig(family='logic_action', actor='Test',
                                    mode='compute'))
    bench_before = _bench_units(b.gs)
    env_out = report_action_pick_invest_env_param(
        b.gs, SimpleNamespace(idx=0),
        ChannelSig(family='logic_action', actor='Test', mode='compute'))
    assert env_out.applied
    cw_sim_ports.declare_world(env_out.world_decl)
    return b, bench_before, _bench_units(b.gs)


def test_concept_stock_env_pick_grant_sim_chain(
        _isolate_defect_buffer) -> None:
    """sim 选卡全链(gain-chain.md §3 随机支/随机装备支段:sim 世界
    真值 = 流键 rng,新形状经 kernel 获得链自动生效,零 sim 新代码):
    选追击概念股 → bench = 开局 4 + 追击阵营域 1★ 一张(星级 = spec
    先验;成员名 ∈ chars_by_faction('追击') 现算集,不手抄)、equips
    计数 +1 且名 ∈ equips_by_category('简易') 现算集;同 seed 重放
    确定性(世界发放可重放)。"""
    from collections import Counter
    faction_names = {c.name for c in chars_by_faction('追击')}
    simple_names = set(equips_by_category('简易'))

    def _run(seed: int) -> tuple[list, list, list]:
        b, bench_before, bench_after = _pick_concept_stock_backend(seed)
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
        f'赠卡名 ∈ 追击阵营池现算集: {granted[0][0]}'
    assert len(equips) == 1, f'equips 计数 +1: {equips}'
    assert equips[0] in simple_names, \
        f'装备名 ∈ 简易类别池现算集: {equips[0]}'
    before2, after2, equips2 = _run(7)
    assert (before, after, equips) == (before2, after2, equips2), \
        '同 seed 重放确定性'


_RANXUE_ENV = '燃血概念股'


def test_ranxue_concept_stock_env_pick_grant_sim_chain(
        _isolate_defect_buffer) -> None:
    """sim 选卡全链第二实例(gain-chain.md §3 随机支/随机装备支段:sim
    世界真值 = 流键 rng,族展开登记经 kernel 获得链自动生效,零 sim 新
    代码;概念股族展开卡登记约定):选燃血概念股 → bench = 开局 4 +
    燃血阵营域 1★ 一张(星级 = spec 先验;成员名 ∈ chars_by_faction
    ('燃血') 现算集,不手抄)、equips 计数 +1 且名 ∈ equips_by_category
    ('简易') 现算集;同 seed 重放确定性(世界发放可重放)。"""
    from collections import Counter
    faction_names = {c.name for c in chars_by_faction('燃血')}
    simple_names = set(equips_by_category('简易'))

    def _run(seed: int) -> tuple[list, list, list]:
        b, bench_before, bench_after = _pick_concept_stock_backend(
            seed, _RANXUE_ENV)
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
        f'赠卡名 ∈ 燃血阵营池现算集: {granted[0][0]}'
    assert len(equips) == 1, f'equips 计数 +1: {equips}'
    assert equips[0] in simple_names, \
        f'装备名 ∈ 简易类别池现算集: {equips[0]}'
    before2, after2, equips2 = _run(7)
    assert (before, after, equips) == (before2, after2, equips2), \
        '同 seed 重放确定性'


_ENERGY_ENV = '能量概念股'


def test_nengliang_concept_stock_env_pick_grant_sim_chain(
        _isolate_defect_buffer) -> None:
    """sim 选卡全链第三实例(gain-chain.md §3 随机支/随机装备支段:sim
    世界真值 = 流键 rng,族展开登记经 kernel 获得链自动生效,零 sim 新
    代码;概念股族展开卡登记约定):选能量概念股 → bench = 开局 4 +
    能量阵营域 1★ 一张(星级 = spec 先验;成员名 ∈ chars_by_faction
    ('能量') 现算集,不手抄)、equips 计数 +1 且名 ∈ equips_by_category
    ('简易') 现算集;同 seed 重放确定性(世界发放可重放)。"""
    from collections import Counter
    faction_names = {c.name for c in chars_by_faction('能量')}
    simple_names = set(equips_by_category('简易'))

    def _run(seed: int) -> tuple[list, list, list]:
        b, bench_before, bench_after = _pick_concept_stock_backend(
            seed, _ENERGY_ENV)
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
        f'赠卡名 ∈ 能量阵营池现算集: {granted[0][0]}'
    assert len(equips) == 1, f'equips 计数 +1: {equips}'
    assert equips[0] in simple_names, \
        f'装备名 ∈ 简易类别池现算集: {equips[0]}'
    before2, after2, equips2 = _run(7)
    assert (before, after, equips) == (before2, after2, equips2), \
        '同 seed 重放确定性'


_LIECHE_ENV = '列车同行概念股'


def test_lieche_concept_stock_env_pick_grant_sim_chain(
        _isolate_defect_buffer) -> None:
    """sim 选卡全链第四实例(gain-chain.md §3 随机支/随机装备支段:sim
    世界真值 = 流键 rng,族展开登记经 kernel 获得链自动生效,零 sim 新
    代码;概念股族展开卡登记约定 + 开拓者双形态角色位合并约定):选列车
    同行概念股 → bench = 开局 4 + 列车同行域 1★ 一张(星级 = spec 先验;
    成员名 ∈ 合并后池现算 = chars_by_faction('列车同行') 剔除
    '开拓者·记忆',采样即发放名恒欢愉,不手抄)、equips 计数 +1 且名 ∈
    equips_by_category('简易') 现算集;同 seed 重放确定性(世界发放可
    重放)。"""
    from collections import Counter
    faction_names = {c.name for c in chars_by_faction('列车同行')} \
        - {'开拓者·记忆'}
    simple_names = set(equips_by_category('简易'))

    def _run(seed: int) -> tuple[list, list, list]:
        b, bench_before, bench_after = _pick_concept_stock_backend(
            seed, _LIECHE_ENV)
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
        f'赠卡名 ∈ 列车同行合并池现算集: {granted[0][0]}'
    assert granted[0][0] != '开拓者·记忆', '发放恒欢愉形态(键侧剔除)'
    assert len(equips) == 1, f'equips 计数 +1: {equips}'
    assert equips[0] in simple_names, \
        f'装备名 ∈ 简易类别池现算集: {equips[0]}'
    before2, after2, equips2 = _run(7)
    assert (before, after, equips) == (before2, after2, equips2), \
        '同 seed 重放确定性'


_YINHE_ENV = '银河学者概念股'


def test_yinhe_concept_stock_env_pick_grant_sim_chain(
        _isolate_defect_buffer) -> None:
    """sim 选卡全链第五实例(gain-chain.md §3 随机支/随机装备支段:sim
    世界真值 = 流键 rng,族展开登记经 kernel 获得链自动生效,零 sim 新
    代码;概念股族展开卡登记约定):选银河学者概念股 → bench = 开局 4 +
    银河学者阵营域 1★ 一张(星级 = spec 先验;成员名 ∈ chars_by_faction
    ('银河学者') 现算集,不手抄;双阵营成员真理医生等按 factions 轴在池,
    域内无开拓者条目,合并对本域零作用)、equips 计数 +1 且名 ∈
    equips_by_category('简易') 现算集(装备身份零先验,economy.md 四卡
    线索名单不含银河学者);同 seed 重放确定性(世界发放可重放)。"""
    from collections import Counter
    faction_names = {c.name for c in chars_by_faction('银河学者')}
    simple_names = set(equips_by_category('简易'))

    def _run(seed: int) -> tuple[list, list, list]:
        b, bench_before, bench_after = _pick_concept_stock_backend(
            seed, _YINHE_ENV)
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
        f'赠卡名 ∈ 银河学者阵营池现算集: {granted[0][0]}'
    assert len(equips) == 1, f'equips 计数 +1: {equips}'
    assert equips[0] in simple_names, \
        f'装备名 ∈ 简易类别池现算集: {equips[0]}'
    before2, after2, equips2 = _run(7)
    assert (before, after, equips) == (before2, after2, equips2), \
        '同 seed 重放确定性'


_BELOBOGE_ENV = '贝洛伯格概念股'


def test_beluoboge_concept_stock_env_pick_grant_sim_chain(
        _isolate_defect_buffer) -> None:
    """sim 选卡全链第六实例(gain-chain.md §3 随机支/随机装备支段:sim
    世界真值 = 流键 rng,族展开登记经 kernel 获得链自动生效,零 sim 新
    代码;概念股族展开卡登记约定):选贝洛伯格概念股 → bench = 开局 4 +
    贝洛伯格阵营域 1★ 一张(星级 = spec 先验;成员名 ∈ chars_by_faction
    ('贝洛伯格') 现算集,不手抄;域 = 布洛妮娅双羁绊注册表修正后 6 名,
    独立单位「大守护者」在候选内照发)、equips 计数 +1 且名 ∈
    equips_by_category('简易') 现算集(装备身份零先验,economy.md 四卡
    线索名单不含贝洛伯格);同 seed 重放确定性(世界发放可重放)。"""
    from collections import Counter
    faction_names = {c.name for c in chars_by_faction('贝洛伯格')}
    simple_names = set(equips_by_category('简易'))

    def _run(seed: int) -> tuple[list, list, list]:
        b, bench_before, bench_after = _pick_concept_stock_backend(
            seed, _BELOBOGE_ENV)
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
        f'赠卡名 ∈ 贝洛伯格阵营池现算集: {granted[0][0]}'
    assert len(equips) == 1, f'equips 计数 +1: {equips}'
    assert equips[0] in simple_names, \
        f'装备名 ∈ 简易类别池现算集: {equips[0]}'
    before2, after2, equips2 = _run(7)
    assert (before, after, equips) == (before2, after2, equips2), \
        '同 seed 重放确定性'
