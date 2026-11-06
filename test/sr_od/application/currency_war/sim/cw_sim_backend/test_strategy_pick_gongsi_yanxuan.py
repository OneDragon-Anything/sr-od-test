"""sim 公司严选把结果写进状态副本的实现分支 walk 测试(镜像 src = sim/cw_sim_backend.py 的
选卡拍改写腿 + 位面段补发两条效果条目(B 案)+ 位面首节点窗金/改写腿 + 窗口
起点快照差分,经真实推进链)。

测试面依据 = 迭代设计 designs/T-309-gongsi-yanxuan.md §2.5/§2.6/§4
+ REVIEW-T309 §3(锁 2 反例 r1-S1/锁 3 可达面按 B 案重算/裁决点 5 =
B 案:用户裁定 2026-11-01 族级拍定「中途拿卡所在位面补发·当前位面
全额」;同拍「选卡改写 × 补发改写」双触发两条效果条目都发,禁静默合并)。
卡面官方原文:「现在及每个位面开始时，开启一个由5个独特4费角色组成
的商店，并获得3金币。」

可达面(B 案):
- (1,3) 拿卡局:拿卡拍三条效果条目(选卡改写 + 补发金 +3 + 补发改写,P1 已
  开始)→ (2,1)/(3,1) 位面开始照常(金 +3/位面 + 位面改写覆盖);
- (2,2) 拿卡局:拿卡拍补发(P2 已开始)→ (3,1) 照常;
- (3,2) 拿卡局:全程仅拿卡拍补发(P3 开始在拿卡前;其后无位面开始);
- 同拍双改写 journal 双行:双计数器(shop_rewrite_gain_count /
  shop_rewrite_plane_count)各 +1 与末行 evidence(refire)共证两行
  如实登记(容器 Field 只存末值,journal 双行以计数对账承载)。

路径选卡卫生:驱动途中逢 offer 一律定向落「淘金客」(无改写/位面/
burst 字段,落卡零扰目标断言);无环境局(RunConfig.env_present 缺省
False)翻星腿零发生,强制店恒 4 费 1★。复用声明:引擎驱动助手 import
自 test_p3_win_terminal._drive_step 与 sim/test_sim_backend._SIG 族
(在册超限拆分债文件,禁追加,只 import 复用不改;先例 =
test_strategy_pick_gudinglicai.py)。
"""
from __future__ import annotations

from types import SimpleNamespace

from test.sr_od.application.currency_war._cw_helpers import cw4_gs
from test.sr_od.application.currency_war.sim.cw_sim_backend.test_p3_win_terminal import (
    _drive_step,
)
from test.sr_od.application.currency_war.sim.test_sim_backend import (
    _SIG,
)

from sr_od.application.currency_war.kernel.cw_action_report import (
    report_action_pick_invest_strategy_param,
)
from sr_od.application.currency_war.kernel.cw_world_decl import WorldDecl
from sr_od.application.currency_war.sim import cw_sim_ports
from sr_od.application.currency_war.sim.cw_sim_backend import (
    SCREEN_BRIEFING,
    SCREEN_INVEST_STRATEGY,
    SCREEN_PREP,
    SimBackend,
    apply_strategy_plane_refire_gold,
    install_backend,
    uninstall_backend,
)
from sr_od.application.currency_war.sim.cw_sim_run_config import RunConfig

_CARD = '公司严选'
# 填充卡前提申报(T-311-r1 裁决 a:只修注释、卡不换——换卡位移种子轨迹,
# 明令禁止):淘金客现役 xp_per_refresh=2(cw_investments.py 注册行),
# 刷新 XP 把结果写进状态副本的实现分支已接入调用(T-311);本卡作填充的安全性前提 = 本目录
# sim 链驱动器(_drive_step)商店屏一律直接关店、零付费刷新帧 → XP
# 分支零开火,落卡零扰目标断言;未来引入付费刷新驱动须先换无 XP 字段
# 填充卡或显式预算 XP 推进对。
_SAFE_FILLER = '淘金客'
_SAFE_OPTS = ['淘金客', '躺平', '买断制']
_EV_GAIN = 'sim:engine:shop:rewrite:gain:'
_EV_PLANE = 'sim:engine:shop:rewrite:plane:'
_EV_REFIRE = 'sim:engine:shop:rewrite:refire:'
_EV_PLANE_GOLD = 'sim:engine:strategy:plane_gold:'
_EV_REFIRE_GOLD = 'sim:engine:strategy:plane_gold_refire:公司严选'


def _backend(seed: int = 37) -> SimBackend:
    """装配后端至 P1r1 备战屏(调用方负责 uninstall;装配形态先例 =
    test_strategy_pick_gudinglicai._backend;定向种子全程可达 P3)。"""
    b = SimBackend(seed=seed, cfg=RunConfig(
        selected_difficulty='A8', enemy_difficulty=108))
    install_backend(b)
    b._handle_click_source(SCREEN_BRIEFING, '按钮-下一步')
    b._maybe_finish_wait()
    assert b.screen_identity() == SCREEN_PREP
    return b


def _pick(b: SimBackend, name: str, opts: list[str]) -> WorldDecl:
    """定向选卡落地(直写 opts 定卡 + 上报 + 声明喂入;先例 =
    test_strategy_pick_gudinglicai._pick)。返回声明供重放用例复喂。"""
    gs = b.gs
    gs.write_logic(gs.invest_strategy_opts, opts,
                   produced_by='Test', evidence='t:opts', sig=_SIG)
    out = report_action_pick_invest_strategy_param(
        gs, SimpleNamespace(norm_name=name), _SIG, session=SimpleNamespace())
    assert out.applied
    cw_sim_ports.declare_world(out.world_decl)
    return out.world_decl


def _drive_with_safe_picks(b: SimBackend, pred, limit: int = 512) -> None:
    """步进驱动至谓词成立;途中逢策略 offer 定向落安全 filler,其余屏
    交 _drive_step 分派。超限响错防死循环(先例同形)。"""
    for _ in range(limit):
        if pred():
            return
        if b.screen_identity() == SCREEN_INVEST_STRATEGY:
            _pick(b, _SAFE_FILLER, _SAFE_OPTS)
            continue
        _drive_step(b, 43)
    raise AssertionError('驱动步数超限,谓词未达成')


def _drive_to_offer(b: SimBackend, plane: int, round_num: int) -> None:
    """驱动至指定位面的策略 offer 呈现(途中 offer 安全 filler 化)。"""

    def _at_offer() -> bool:
        node = b.gs.node.value
        return (b.screen_identity() == SCREEN_INVEST_STRATEGY
                and node is not None and node.plane == plane
                and node.round_num == round_num)
    _drive_with_safe_picks(b, _at_offer)


def _drive_steps_tolerant(b: SimBackend, steps: int) -> None:
    """有界步进(局败容忍):驱动至多 steps 步,局败回大厅即停——本腿
    断言面是「无后续位面开始零增量」,局败属合法终局非驱动故障。"""
    for _ in range(steps):
        if b.screen_identity() == '货币战争-大厅':
            return
        _drive_step(b, 43)


def _assert_forced_shop(gs, *, plane: int, r: int) -> None:
    """强制店牌面断言:5 槽全 content、名互异、恒 4 费 1★(无环境局
    翻星零发生);末行 evidence = 指定拍改写行。"""
    shop = gs.shop.value
    assert shop is not None and len(shop.cards) == 5
    names = [s.card.name for s in shop.cards if s.card is not None]
    assert len(names) == 5, f'桶满局 5 content: {len(names)}'
    assert len(set(names)) == 5, f'「独特」同帧去重: {names}'
    for slot in shop.cards:
        assert slot.card.cost == 4 and slot.card.star == 1, \
            f'强制 4 费 1★(无环境局): {slot.card.cost}/{slot.card.star}'


def test_pick_p1r3_gain_refire_then_later_planes_normal() -> None:
    """(1,3) 拿卡局:拿卡拍三条效果条目(改写 + 补发金 +3 + 补发改写)→
    (2,1)/(3,1) 位面开始照常(金腿 + 位面改写覆盖)。"""
    b = _backend(seed=37)
    try:
        gs = b.gs
        _drive_to_offer(b, 1, 3)
        gold_before = int(gs.gold.value or 0)
        _pick(b, _CARD, [_CARD, '躺平', _SAFE_FILLER])
        # 拿卡拍:选卡改写 + 补发金 +3 + 补发改写(P1 已开始)——双改写
        # journal 双行由双计数器各 +1 共证,末行 = refire。
        _assert_forced_shop(gs, plane=1, r=3)
        assert gs.shop.evidence == f'{_EV_REFIRE}p1r3', \
            f'末行 = 补发改写: {gs.shop.evidence}'
        assert b.disclosures.get('shop_rewrite_gain_count') == 1
        assert b.disclosures.get('shop_rewrite_plane_count') == 1
        assert 'shop_rewrite_shortfall_count' not in b.disclosures, '桶满零短缺'
        assert gs.gold.value == gold_before + 3, \
            f'补发金 +3(P1 已开始): {gs.gold.value}'
        assert gs.gold.evidence == _EV_REFIRE_GOLD
        # (2,1) 位面开始照常:金腿单笔 + 位面改写覆盖(M05 后后置)。
        _drive_with_safe_picks(
            b, lambda: gs.gold.evidence == f'{_EV_PLANE_GOLD}p2')
        assert gs.shop.evidence == f'{_EV_PLANE}p2r1', \
            f'(2,1) 位面改写覆盖: {gs.shop.evidence}'
        _assert_forced_shop(gs, plane=2, r=1)
        assert b.disclosures.get('shop_rewrite_plane_count') == 2
        assert b.disclosures.get('shop_rewrite_gain_count') == 1, \
            '位面拍不计 gain 计数(分拍对账)'
        # (3,1) 照常(evidence 转移即证;值面含窗口收入干扰不作精确断言)。
        _drive_with_safe_picks(
            b, lambda: gs.shop.evidence == f'{_EV_PLANE}p3r1')
        assert b.disclosures.get('shop_rewrite_plane_count') == 3
        assert gs.gold.evidence == f'{_EV_PLANE_GOLD}p3'
    finally:
        uninstall_backend()


def test_pick_p2r2_refire_then_plane3_normal() -> None:
    """(2,2) 拿卡局(B 案可达):拿卡拍补发(P2 已开始)→ (3,1)
    位面开始照常;(2,1) 窗(拿卡前)未持卡零改写零位面金。"""
    b = _backend(seed=37)
    try:
        gs = b.gs
        _drive_to_offer(b, 1, 3)
        _pick(b, _SAFE_FILLER, _SAFE_OPTS)
        # (2,1) 位面开始未持目标卡:零位面金笔、零改写(M05 deal 行除外)。
        _drive_with_safe_picks(
            b, lambda: gs.node.value is not None
            and (gs.node.value.plane, gs.node.value.round_num) >= (2, 1))
        assert not str(gs.gold.evidence or '').startswith(_EV_PLANE_GOLD), \
            '未持卡位面开始零位面金笔'
        assert not str(gs.shop.evidence or '').startswith(_EV_PLANE), \
            '未持卡零位面改写行'
        _drive_to_offer(b, 2, 2)
        gold_before = int(gs.gold.value or 0)
        _pick(b, _CARD, [_CARD, '躺平', _SAFE_FILLER])
        _assert_forced_shop(gs, plane=2, r=2)
        assert gs.shop.evidence == f'{_EV_REFIRE}p2r2'
        assert b.disclosures.get('shop_rewrite_gain_count') == 1
        assert b.disclosures.get('shop_rewrite_plane_count') == 1
        assert gs.gold.value == gold_before + 3
        assert gs.gold.evidence == _EV_REFIRE_GOLD
        # (3,1) 照常。
        _drive_with_safe_picks(
            b, lambda: gs.shop.evidence == f'{_EV_PLANE}p3r1')
        assert b.disclosures.get('shop_rewrite_plane_count') == 2
        assert gs.gold.evidence == f'{_EV_PLANE_GOLD}p3'
    finally:
        uninstall_backend()


def test_pick_p3r2_late_pick_refire_only() -> None:
    """(3,2) 拿卡局(B 案可达,非零火):P3 开始在拿卡前(未持卡零发),
    补发恰覆盖 P3 段;其后无位面开始 → 计数恒稳。"""
    b = _backend(seed=37)
    try:
        gs = b.gs
        _drive_to_offer(b, 1, 3)
        _pick(b, _SAFE_FILLER, _SAFE_OPTS)
        _drive_to_offer(b, 2, 2)
        _pick(b, _SAFE_FILLER, _SAFE_OPTS)
        # P3 开始(3,1)未持卡:零位面金笔、零改写。
        _drive_with_safe_picks(
            b, lambda: gs.node.value is not None
            and (gs.node.value.plane, gs.node.value.round_num) >= (3, 1))
        assert not str(gs.gold.evidence or '').startswith(_EV_PLANE_GOLD)
        assert not str(gs.shop.evidence or '').startswith(_EV_PLANE)
        _drive_to_offer(b, 3, 2)
        gold_before = int(gs.gold.value or 0)
        _pick(b, _CARD, [_CARD, '躺平', _SAFE_FILLER])
        _assert_forced_shop(gs, plane=3, r=2)
        assert gs.shop.evidence == f'{_EV_REFIRE}p3r2'
        assert b.disclosures.get('shop_rewrite_gain_count') == 1
        assert b.disclosures.get('shop_rewrite_plane_count') == 1
        assert gs.gold.value == gold_before + 3
        # 其后无位面开始:继续驱动(局败容忍),改写计数恒稳(途径节点窗
        # M05 deal 行覆盖 shop evidence 属预期,不断言其稳定)。
        _drive_steps_tolerant(b, 40)
        assert b.disclosures.get('shop_rewrite_gain_count') == 1, \
            '无后续获得拍零增量'
        assert b.disclosures.get('shop_rewrite_plane_count') == 1, \
            '无后续位面开始零增量'
    finally:
        uninstall_backend()


def test_later_pick_no_rescan_counterexample() -> None:
    """反例锁(r1-S1):先拿 公司严选、再拿他卡 → 零改写重燃(「本次
    新获得」限定,防扫描式回归);位面窗腿照常不受影响。"""
    b = _backend(seed=37)
    try:
        gs = b.gs
        _drive_to_offer(b, 1, 3)
        _pick(b, _CARD, [_CARD, '躺平', _SAFE_FILLER])
        assert b.disclosures.get('shop_rewrite_gain_count') == 1
        # 推进至 (2,1) 窗(位面腿照常 → plane_count=2),再至 (2,2) offer。
        _drive_with_safe_picks(
            b, lambda: gs.shop.evidence == f'{_EV_PLANE}p2r1')
        assert b.disclosures.get('shop_rewrite_plane_count') == 2
        _drive_to_offer(b, 2, 2)
        # (2,2) 窗开自带 M05 deal 行,选拍零写判据 = 选拍前后 shop 末行
        # evidence 不变(改写/refire 行缺位)。
        shop_ev_before = gs.shop.evidence
        _pick(b, _SAFE_FILLER, _SAFE_OPTS)
        # 他卡无改写/位面字段:拍内零写——gain 计数不变、plane 计数不变、
        # shop 末行不新增改写笔(本拍零 shop 写)。
        assert b.disclosures.get('shop_rewrite_gain_count') == 1, \
            '他卡零选卡改写(防扫描式回归)'
        assert b.disclosures.get('shop_rewrite_plane_count') == 2, \
            '他卡零补发改写'
        assert gs.shop.evidence == shop_ev_before, \
            f'他卡拍零 shop 写: {gs.shop.evidence}'
    finally:
        uninstall_backend()


def test_replay_advance_zero_double() -> None:
    """重放防双发:同 offer 落地声明重放 → 第二次零写(快照差分已前滚,
    重放差分恒空)。"""
    b = _backend(seed=37)
    try:
        gs = b.gs
        _drive_to_offer(b, 1, 3)
        gold_before = int(gs.gold.value or 0)
        decl = _pick(b, _CARD, [_CARD, '躺平', _SAFE_FILLER])
        assert b.disclosures.get('shop_rewrite_gain_count') == 1
        assert gs.gold.value == gold_before + 3
        cw_sim_ports.declare_world(decl)
        assert b.disclosures.get('shop_rewrite_gain_count') == 1, '重放双发'
        assert b.disclosures.get('shop_rewrite_plane_count') == 1, '重放双发'
        assert gs.gold.value == gold_before + 3, f'重放金双发: {gs.gold.value}'
        assert gs.shop.evidence == f'{_EV_REFIRE}p1r3'
    finally:
        uninstall_backend()


def test_refire_gold_node_absent_conservative_zero() -> None:
    """补发金腿 node 缺席保守零补发锁:gs.node None → 返回 0、零写
    (禁猜;登记恒在节点窗内,node 缺席 = bypass 形态防御)。"""
    gs = cw4_gs(gold=30, node_fill=False, shop_screen='off')
    assert gs.node.value is None
    applied = apply_strategy_plane_refire_gold(gs, [_CARD])
    assert applied == 0, 'node 缺席保守零补发'
    assert gs.gold.value == 30, '零写'
