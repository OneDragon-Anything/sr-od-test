"""期望态 infra 单测(W971 EXPECTED_STATE.md FINAL v3.1;P4)。

覆盖三块:①merge_simulate 合成引擎(merge_mechanics §2 两例 + 满栏自动多买
3 例 + 装备继承 1 例);②apply_op_effect 逐 op 推进(§3 表精确区/到账登记区
+ 理由区零登记);③覆盖点 reconcile diff(一致清账/不一致留证五分类/可信门
/条目绑覆盖点/组确认)。纯函数 + StrategySession 直构,零 IO 零识别。
"""
from __future__ import annotations

from sr_od.application.currency_war.kernel.cw_expected_state import (
    DIFF_MERGE_MODEL,
    DIFF_OP_EFFECT,
    ExpectedEntry,
    apply_op_effect,
    reconcile_expected,
    register_expected,
)
from sr_od.application.currency_war.kernel.cw_merge_simulate import (
    merge_simulate,
)
from sr_od.application.currency_war.kernel.cw_prep_actions import (
    ClickSpheres,
    OpenBox,
    RunBuyPhase,
    SellBench,
    SellDeployed,
)
from sr_od.application.currency_war.kernel.cw_state import (
    BENCH_CAPACITY,
    BenchChar,
    GameState,
)
from sr_od.application.currency_war.kernel.cw_strategy_session import (
    StrategySession,
)


def _bc(slot: int, name: str, star: int = 1,
        equips: list[str] | None = None) -> BenchChar:
    return BenchChar(slot=slot, char_id=name, star=star,
                     position_pref='back', equips=list(equips or []))


def _pad(bench: list[BenchChar | None]) -> list[BenchChar | None]:
    return list(bench) + [None] * (BENCH_CAPACITY - len(bench))


# ==================== ① merge_simulate ====================

def test_merge_bench_leftmost() -> None:
    """merge_mechanics §2 例 1(备战合成):同名 1★×3 全在备战 → 升 2★
    落最左占用槽,其余两槽腾空,无关角色不动。"""
    bench = _pad([_bc(1, '桑博'), _bc(2, '卡芙卡'), _bc(3, '桑博'),
                  _bc(5, '桑博'), _bc(6, '希儿')])
    res = merge_simulate(bench, [], '桑博', 1, k=0)
    # k=0 零买:仅推演既有板面的合成(买前凑 3 形态由 k>=1 路径覆盖)
    assert res.buy_k == 0
    sambos = [(i + 1, b) for i, b in enumerate(res.bench_after)
              if b is not None and b.char_id == '桑博']
    assert len(sambos) == 1
    slot, bc = sambos[0]
    assert slot == 1        # 落点 = 最左
    assert bc.star == 2
    # 被合成槽(原 3/5)腾空;合成前板面桑博 3 份 → 合成后 1 份
    assert res.bench_after[4] is None or res.bench_after[4].char_id != '桑博'
    assert res.chain and res.chain[0].to_star == 2


def test_merge_chain_lands_on_deployed() -> None:
    """merge_mechanics §2 例 2(连锁合成落场):场上 2★ + 备战 2★×2 →
    3★ 落**场上那个同星的位置**(deployed 槽位表下标不变)。"""
    bench = _pad([_bc(1, '桑博', 2), _bc(2, '桑博', 2)])
    deployed = [_bc(1, '希儿', 1), None, None, None,
                _bc(1, '桑博', 2)]   # idx4 = 后排槽 1
    res = merge_simulate(bench, deployed, '桑博', 2, k=0)
    assert res.chain[-1].to_star == 3
    top = res.chain[-1]
    assert top.landing_kind == 'deployed'
    assert top.landing_slot == 4      # 槽位表下标(场上吸收)
    assert res.deployed_after[4].star == 3
    # 连锁:2★ 层级的合成步骤在链中(2×1★→2★ 在前,2★ 凑 3→3★ 在后)


def test_full_bench_no_merge_rejected() -> None:
    """满栏自动多买例 1:满栏且同星计数 mod 3 == 0、店内不足 3 →
    不可触发合成 → 拒买(buy_k=0,板面零变更)。"""
    bench = [_bc(i + 1, f'c{i}') for i in range(BENCH_CAPACITY)]
    res = merge_simulate(bench, [], '桑博', 1, k=1, in_shop_count=2)
    assert res.buy_k == 0
    assert res.chain == []
    assert all(b is not None for b in res.bench_after)


def test_full_bench_auto_multibuy_completes() -> None:
    """满栏自动多买例 2:已有 mod 3 == 2、店内 ≥1 → 自动多买 1 张,
    买后合成触发,腾出槽位。"""
    bench = [_bc(i + 1, f'c{i}') for i in range(7)]
    bench += [_bc(8, '桑博'), _bc(9, '桑博')]
    res = merge_simulate(bench, [], '桑博', 1, k=1, in_shop_count=2)
    assert res.buy_k == 1
    assert res.multi_buy is False   # 请求 1 = 实买 1(自动多买未超额)
    assert res.chain, '买第 3 张必须触发合成'


def test_full_bench_multibuy_caps_at_shop_stock() -> None:
    """满栏自动多买例 3:mod 3 == 0(无已有)→ 需 3 张;店内仅 2 →
    不可合成 → 拒买(绝不多买不触发量,§2.5 上限口径)。"""
    bench = [_bc(i + 1, f'c{i}') for i in range(BENCH_CAPACITY)]
    res = merge_simulate(bench, [], '桑博', 1, k=1, in_shop_count=2)
    assert res.buy_k == 0


def test_equipment_full_inheritance() -> None:
    """装备继承:三只身上的装备**全部**继承到升星产物(玩家定谳;
    合成装备守恒)。"""
    bench = _pad([_bc(1, '桑博', 1, ['幸运星']),
                  _bc(2, '桑博', 1, ['轮滑鞋', '光能电池']),
                  _bc(3, '桑博', 1, [])])
    res = merge_simulate(bench, [], '桑博', 1, k=0)
    merged = next(b for b in res.bench_after
                  if b is not None and b.char_id == '桑博')
    assert sorted(merged.equips) == ['光能电池', '幸运星', '轮滑鞋']
    # 继承面 = 被消耗两只的全部装备(载体自身装备留在载体)
    assert sorted(res.chain[0].inherited_equips) == ['光能电池', '轮滑鞋']


def test_deploy_invariant_asserted() -> None:
    """恒成立不变量(§P2 批注 5):输入场上同名同星 >1 → 断言当场抛
    (模型错不静默)。"""
    import pytest
    deployed = [_bc(1, '桑博', 1), _bc(2, '桑博', 1)]
    with pytest.raises(AssertionError):
        merge_simulate([], deployed, '桑博', 1, k=0)


# ==================== ② apply_op_effect ====================

def _session_with_board() -> StrategySession:
    s = StrategySession()
    s.last_state = GameState(gold=50, plane=1, round_num=4)
    s.tracked_bench_chars = [_bc(1, '卡芙卡', 2)]
    s.tracked_deployed = [_pad([_bc(1, '希儿', 1, ['幸运星'])])[0]] \
        + [None] * 9
    return s


def test_apply_sell_bench_advances_gold_and_registers() -> None:
    """§3 #10:卖备战 → gold += sell_refund(2★, cost=2 = 3×2−1 = 5);
    bench 槽组条目登记。"""
    s = _session_with_board()
    effects = apply_op_effect(s, SellBench(slot=1), produced_by='test')
    assert s.last_state.gold == 55
    paths = [e['path'] for e in effects]
    assert 'gold' in paths
    assert any(p.startswith('tracked_bench_chars[1]') for p in paths)
    entry = s.expected_state['tracked_bench_chars[1]']
    assert entry.kind == 'tracked' and entry.value is None
    assert entry.group_id            # 卖出条目带组 id


def test_apply_sell_deployed_returns_equips() -> None:
    """§3 #9:卖场上 → 装备全额返还 owned(逐件登记)+ gold 回金。"""
    s = _session_with_board()
    apply_op_effect(s, SellDeployed(row='front', slot=1))
    kinds = {e.kind for e in s.expected_state.values()}
    assert 'owned' in kinds
    assert any(p.startswith('owned[幸运星]') for p in s.expected_state)


def test_apply_click_spheres_pending_reward() -> None:
    """§3 #12:点球 → pending_reward 到账登记(待实读,覆盖点只清账)。"""
    s = _session_with_board()
    apply_op_effect(s, ClickSpheres(max_k=2))
    e = s.expected_state['pending_reward']
    assert '待实读' in e.value


def test_apply_run_buy_phase_mirrors_buy_expect() -> None:
    """buy 分道(F1):BuyExpect 载体原样挂载,expected_state 仅统一挂载点。"""
    s = _session_with_board()
    sentinel = object()
    s.pending_buy_expect = sentinel
    apply_op_effect(s, RunBuyPhase())
    assert s.expected_state['buy_expect'].value is sentinel
    assert s.expected_state['buy_expect'].kind == 'buy_expect'


def test_apply_no_model_ops_register_nothing() -> None:
    """§3 理由区:OpenBox(箱不消失,画面态)等零登记——无例外枚举的
    「不更新」面。"""
    s = _session_with_board()
    apply_op_effect(s, OpenBox())
    assert not s.expected_state


def test_apply_overlay_dict_confirm_registers_owned() -> None:
    """到账登记区(§3 #27 武装箱选卡):owned += 选中装备。"""
    s = _session_with_board()
    apply_op_effect(s, {'op': 'ConfirmBox', 'item': '和平手枪'})
    assert '和平手枪' in s.last_owned_equips
    assert 'owned[和平手枪]' in s.expected_state


def test_executor_face_registers_via_hook() -> None:
    """两执行面同源(F8):PrepActionExecutor.execute 成功路径调
    apply_op_effect(源码锁);decision_assembly.execute 委托本执行器
    (同点覆盖,零双写)。"""
    import inspect

    import sr_od.application.currency_war.prep_actions as pa
    src = inspect.getsource(pa.PrepActionExecutor.execute)
    assert 'apply_op_effect' in src
    from sr_od.application.currency_war import decision_assembly
    dsrc = inspect.getsource(decision_assembly.DecideAdapter.execute)
    assert '_executor.execute(action)' in dsrc


# ==================== ③ 覆盖点 reconcile ====================

def test_reconcile_matches_clear_and_mismatch_evidences() -> None:
    """一致 → 清账;不一致 → 留证(mismatch 分类按 kind:merge_group →
    模型错;标量 → op 函数 bug)。"""
    s = _session_with_board()
    register_expected(s, ExpectedEntry(
        path='tracked_bench_chars[9]', value='卡芙卡@2★',
        produced_by='t', at_round='p1-r4', kind='tracked'))
    register_expected(s, ExpectedEntry(
        path='merge_chain[卡芙卡:2->3]', value='落点=bench:2',
        produced_by='t', at_round='p1-r4', kind='merge_group'))
    # 一致:实读含期望身份 → 清账
    diffs = reconcile_expected(s, 'prep_obs',
                               {'tracked_bench_chars[9]': ('卡芙卡@2★|希儿', True)})
    assert diffs == []
    assert 'tracked_bench_chars[9]' not in s.expected_state
    # 不一致:merge 组条目 → 合成落点/星级模型错分类,留证后清账
    diffs = reconcile_expected(s, 'prep_obs',
                               {'merge_chain[卡芙卡:2->3]': ('落点=bench:9', True)})
    assert len(diffs) == 1
    assert diffs[0]['diff_class'] == DIFF_MERGE_MODEL


def test_reconcile_trust_gate_and_confirm_point() -> None:
    """可信门(F5)+ 条目绑覆盖点(F7):gold 关态不可信 → 条目保留;
    shop_wave_top 条目在 prep_obs 覆盖点透传不清账。"""
    s = _session_with_board()
    register_expected(s, ExpectedEntry(
        path='gold', value='+6', produced_by='t', at_round='p1-r4',
        kind='gold', confirm_point='shop_wave_top'))
    # prep_obs 点:confirm_point 不符 → 透传(不因 gold 不可信误清)
    assert reconcile_expected(s, 'prep_obs', {}) == []
    assert 'gold' in s.expected_state
    # shop_wave_top 点:gold 可信读 → 到账清账(delta 条目不 diff,精确金对账
    # 归 spend 账本既有通道)
    diffs = reconcile_expected(s, 'shop_wave_top', {'gold': (56, True)})
    assert diffs == []
    assert 'gold' not in s.expected_state


def test_reconcile_pending_value_clears_without_diff() -> None:
    """到账登记(待实读)条目:可信读即清账不 diff;实读 None = 不评保留。"""
    s = _session_with_board()
    register_expected(s, ExpectedEntry(
        path='pending_reward', value='球×2(待实读)', produced_by='t',
        at_round='p1-r4', kind='pending_reward'))
    assert reconcile_expected(s, 'prep_obs',
                              {'pending_reward': (None, True)}) == []
    assert 'pending_reward' in s.expected_state
    assert reconcile_expected(s, 'prep_obs',
                              {'pending_reward': ('gone', True)}) == []
    assert 'pending_reward' not in s.expected_state


def test_reconcile_scalar_mismatch_classified_op_effect() -> None:
    """非 tracked/merge 标量条目不一致 → op 函数实现错分类(与模型错分立,
    §5 第二类)。"""
    s = _session_with_board()
    register_expected(s, ExpectedEntry(
        path='owned[和平手枪]', value='+1', produced_by='t',
        at_round='p1-r4', kind='owned'))
    diffs = reconcile_expected(s, 'prep_obs',
                               {'owned[和平手枪]': ('+9', True)})
    assert diffs and diffs[0]['diff_class'] == DIFF_OP_EFFECT


# ==================== ④ 结算屏资产读口(结算覆盖点输入) ====================

def test_parse_settlement_assets_win_frame_forms() -> None:
    """win 帧亲读形态(EXPECTED_STATE §1 引):存量=当前金;Lv.5 4/20。"""
    from sr_od.application.currency_war.obs.cw_settlement_obs import (
        parse_settlement_assets,
    )
    out = parse_settlement_assets(
        ['挑战成功', '小队生命值20', '金币总览', '10', '存量 60',
         'Lv.5', '4/20', '继续挑战'])
    assert out == {'gold': 60, 'level': 5, 'xp_cur': 4, 'xp_next': 20}


def test_parse_settlement_assets_loss_page_forms() -> None:
    """败局链读数口径(05-battle §1):轮败页无等级/经验 → 对应键 None;
    金币右上存量可读。"""
    from sr_od.application.currency_war.obs.cw_settlement_obs import (
        parse_settlement_assets,
    )
    out = parse_settlement_assets(['挑战结束', '-22', '挑战进度', '存量 30',
                                   '前往结算'])
    assert out['gold'] == 30
    assert out['level'] is None and out['xp_cur'] is None
    # 全不可读 = 诚实未知(不冒认)
    assert parse_settlement_assets(['挑战成功', '继续挑战']) == {
        'gold': None, 'level': None, 'xp_cur': None, 'xp_next': None}
