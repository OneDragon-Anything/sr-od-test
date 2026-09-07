"""P82 支A 兑现链谓词收敛锁(ADR-0592;方案 v3 §3.3 落码规格,
命题族 = math_proofs P82-a/c 行[单篇候证明批入册,草案见方案 §3.2];
判废锚 = [33] 精确化裁定 2026-09-01,user_playstyle.md)。

锁清单(方案 §6.3 落码批执行面):
- P82-a 带内等价引理单帧锁:闸带内 ⟺ (g mod 10) ≥ s+2ρ(ρ=Σ预留
  同函数同参恒同值),带内只看档内余量;s+2ρ ≥ 10 ⟹ 带内通过集空、
  推迟目标 = 不动点 F = g*+s+2ρ(ρ∈{1,2} ⟹ F 离散两值);
- 收敛谓词本体锁:∃x 量词(arm1「任一共享」≠ 支A「候选件资格」)、
  纯冗余排除、域外件、同名排除、cap 缺读 fail-closed;
- RECIPE_WAITING_MODE 显式参数锁(C1 候裁挂账,翻常量即切:
  gap[缺省,口径 B]/ignition[口径 b]/board[口径 c]);
- 五消费位单一源对拍锁(E5):kernel ①臂/ΔV_pop 指示项/criteria
  委托位/引擎披露键/检查器镜像同判;
- statefn 重定向位边界对拍锁(ARM1 sink 单一源守卫,ADR-0516 先例)。
锁结构/回显,不锁分布数值(sr-od-test README 第 8 条)。
"""
from __future__ import annotations

from types import SimpleNamespace

from sr_od.application.currency_war.kernel import cw_waiting_piece
from sr_od.application.currency_war.kernel.cw_economy import (
    clicks_to_next_level,
    interest,
    saturation_line,
    xp_click_cost,
)
from sr_od.application.currency_war.kernel.cw_state import (
    BenchChar,
    GameState,
)
from sr_od.application.currency_war.kernel.cw_waiting_piece import (
    recipe_waiting,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.criteria import (
    levelup as crit_levelup,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.criteria import (
    refresh as crit_refresh,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.statefn import (
    predicates as statefn_predicates,
)

_KM = ('姬子·启行', '三月七', '花火', '瓦尔特')   # 列车同行 core∪shared


def _bc(name: str, star: int = 1, slot: int = 1) -> BenchChar:
    return BenchChar(slot=slot, char_id=name, star=star)


def _state(gold: int, level: int, *, xp: tuple[int, int] = (0, 6),
           bench: list | None = None,
           deployed: list | None = None) -> GameState:
    st = GameState(gold=gold, level=level, round_num=6, hp=60)
    st.level_readable = True
    st.plane = 1
    st.node_type = 'battle'
    st.xp_progress = xp
    st.level_up_cost = 4
    st.shop = []
    st.bench = list(bench) if bench is not None else []
    st.deployed = list(deployed) if deployed is not None else []
    st.refresh_probs = {5: 0}
    return st


def _lv_action(realize: bool, *, legacy: bool = False) -> dict:
    """引擎 LevelUp 披露行(现役权威键 dec_recipe_waiting;legacy=True
    附旧谓词形态键模拟跨版本账本)。"""
    a = {'__type__': 'LevelUp', 'cost': 8, 'auth': 'm3_batch:arm1',
         'dec_recipe_waiting': realize}
    if legacy:
        a['dec_board_full'] = True
        a['dec_bench_2star'] = realize
    return a


def _gate(st: GameState, bench: list, deployed: list,
          clicks: int) -> tuple[bool, str]:
    return crit_levelup.levelup_budget_gate(
        st, None, st.gold, 5, _KM, bench, deployed, clicks,
        xp_click_cost(st))


def _dep_board() -> list[BenchChar]:
    """板面(4 件 2★,cap=4 板满):列车同行 3 件在场使 bench 三月七
    恒 dup-外(不在板面)且其档饱和(支A 不触发,闸判定保持纯 (3a));
    三月七/花火 至多一件在场,保证 km 合格集非空(ρ ∈ {1,2},
    E13 合格集空例外支不触发)。"""
    return [_bc('姬子·启行', star=2, slot=1),
            _bc('花火', star=2, slot=2),
            _bc('瓦尔特', star=2, slot=3),
            _bc('阮·梅', star=2, slot=4)]


class TestP82aInBandEquivalence:
    """P82-a 带内等价引理单帧锁(推导全从注册表单一源现算,禁手抄数)。"""

    def test_inband_passable_domain_xp_cur_ge2(self):
        """带内可过域(xp_cur≥2 分域,F7 反例支):lv4→5、xp_cur=2
        ⟹ clicks=⌈(6−2)/4⌉=1、s=4;s+2ρ ≤ 9 ⟹ 带内可过——
        g=10k+r_pass 过、r_pass−1 拒,且 r_pass 同值跨档位 k 皆过
        (带内闸只看档内余量,与绝对金位无关)。"""
        bench = [_bc('三月七', star=1, slot=1)]
        deployed = _dep_board()
        st = _state(0, 4, xp=(2, 6), bench=bench, deployed=deployed)
        clicks = clicks_to_next_level(st)
        cost = xp_click_cost(st)
        s = clicks * cost
        rho = crit_refresh.r2_card_reserve(_KM, bench, deployed, st)
        assert rho == 1, 'ρ 形态失准(重推合格集最低费卡价,非手抄)'
        r_pass = s + 2 * rho
        assert r_pass <= 9, \
            f'带内可过域前提失准(s+2ρ={r_pass} ≥ 10):重推 xp_cur 分域帧'
        for k in (3, 4):
            g_ok = 10 * k + r_pass
            st.gold = g_ok
            ok, why = _gate(st, bench, deployed, clicks)
            assert ok is True and why == '', f'g={g_ok} 带内应过'
            st.gold = g_ok - 1
            ok2, why2 = _gate(st, bench, deployed, clicks)
            assert ok2 is False, f'g={g_ok - 1} 贴线应拒(τ={interest(g_ok - 1, 5)})'
        # 支A 与该帧无涉(bench 三月七所在档板面已饱和):
        # 闸判定即纯 (3a),引理锁不被兑现链旁路污染
        assert not crit_levelup._realize_chain_ready(st, bench, deployed)

    def test_inband_unreachable_fixed_point_two_values(self):
        """带内不可达 + 不动点 F = g*+s+2ρ 离散两值(ρ∈{1,2}):
        lv4→5、xp_cur=0 ⟹ s=8;s+2ρ ∈ {10,12} ≥ 10 ⟹ 带内 20..49
        全拒(带内通过集空);g*=saturation_line(5),F−1 拒、F 过
        (τ 定格 cap,推迟目标不动点)。"""
        deployed = _dep_board()
        bench1 = [_bc('三月七', star=1, slot=1)]      # ρ=1(1费合格,非2★)
        st = _state(0, 4, xp=(0, 6), bench=bench1, deployed=deployed)
        clicks = clicks_to_next_level(st)
        s = clicks * xp_click_cost(st)
        rho1 = crit_refresh.r2_card_reserve(_KM, bench1, deployed, st)
        assert rho1 == 1, 'ρ 两值形态失准(重推合格集最低费卡价)'
        g_star = saturation_line(5)
        for g in range(20, g_star):
            st.gold = g
            ok, _ = _gate(st, bench1, deployed, clicks)
            assert ok is False, f'g={g} 带内应全拒(s+2ρ={s + 2 * rho1} ≥ 10)'
        f1 = g_star + s + 2 * rho1
        st.gold = f1 - 1
        ok, _ = _gate(st, bench1, deployed, clicks)
        assert ok is False, 'F−1 应拒(τ 已定格息帽,贴线敏感)'
        st.gold = f1
        ok, why = _gate(st, bench1, deployed, clicks)
        assert ok is True and why == '', f'不动点 F={f1} 应放行'
        # ρ=2 形态(三月七 2★ 入板 → 合格集退到 2费花火;花火 bench
        # 与板面零共享键,支A 不触发,闸判定仍纯 (3a)):F 抬到第二离散值
        deployed2 = [_bc('姬子·启行', star=2, slot=1),
                     _bc('三月七', star=2, slot=2),
                     _bc('瓦尔特', star=2, slot=3),
                     _bc('阮·梅', star=2, slot=4)]
        bench2 = [_bc('花火', star=1, slot=1)]
        rho2 = crit_refresh.r2_card_reserve(_KM, bench2, deployed2, st)
        assert rho2 == rho1 + 1, 'ρ 两值形态失准(重推合格集最低费卡价)'
        f2 = g_star + s + 2 * rho2
        st.gold = f2 - 1
        ok, _ = _gate(st, bench2, deployed2, clicks)
        assert ok is False
        st.gold = f2
        ok, why = _gate(st, bench2, deployed2, clicks)
        assert ok is True and why == '', f'不动点第二离散值 F={f2} 应放行'


class TestConvergedPredicate:
    """收敛谓词本体(P82-c 双向差分 + E1/E2 边界)。"""

    def test_exists_quantifier_stricter_than_arm1_share(self):
        """∃x 量词锁:arm1「bench 任一成员与板面共享键」为真,但该成员
        所在档全饱和(纯冗余)+ 其余件域外 ⟹ 支A 不放行——
        「有共享件」≠「有资格候选件」(谓词规格 arm1_existence ∧ ∃x
        qualifies 的严格化面,方案 v3 §3.3)。"""
        dep = [_bc('姬子·启行', star=2, slot=1),
               _bc('三月七', star=2, slot=2),
               _bc('阮·梅', star=1, slot=3),
               _bc('卡芙卡', star=1, slot=4)]     # 列车同行 2 = 档饱和
        bench = [_bc('瓦尔特', star=1, slot=1),   # 共享{列车同行}全饱和
                 _bc('白厄', star=1, slot=2)]     # 无羁绊键(域外)
        from sr_od.application.currency_war.strategies.impl.mandate_v1.statefn.predicates import (
            arm1_existence,
        )
        assert arm1_existence(4, ['瓦尔特', '白厄'],
                              [d.char_id for d in dep], 4)
        assert not recipe_waiting(dep, bench, 4)

    def test_cap_none_fail_closed(self):
        """cap 缺读恒 False(生产谓词 fail-closed,ADR-0589 同款;
        arm1_existence 函数内 DEPLOYED_CAPACITY 兜底仅其直调面保留,
        收敛谓词不继承该兜底)。"""
        dep = [_bc('姬子·启行', star=1, slot=1)]
        bench = [_bc('三月七', star=1, slot=1)]
        assert not recipe_waiting(dep, bench, None)

    def test_unknown_name_no_evidence(self):
        """未注册名无羁绊证据:不参与域/缺口判定(保守向,不凭空
        放行旁路)。"""
        dep = [_bc('姬子·启行', star=1, slot=1),
               _bc('花火', star=1, slot=2),
               _bc('阮·梅', star=1, slot=3),
               _bc('卡芙卡', star=1, slot=4)]
        bench = [_bc('未识别件', star=2, slot=1)]
        assert not recipe_waiting(dep, bench, 4)


class TestWaitingModeParameter:
    """RECIPE_WAITING_MODE 显式参数锁(C1 候裁挂账:候裁行 = 进度账本
    T-139,翻常量即切;ADR-0590 REDEPLOY_TRANSITION_ENABLED 同款)。"""

    def _frame(self) -> tuple[list, list, list]:
        # 仙舟板面计数 1 < 基础档 3(gap 真、ignition 假的分域帧:
        # 1+1=2 ∉ tiers (3,5,7,10) 不点火)
        dep = [_bc('停云', star=1, slot=1),
               _bc('阮·梅', star=1, slot=2),
               _bc('卡芙卡', star=1, slot=3),
               _bc('白厄', star=1, slot=4)]
        bench = [_bc('彦卿', star=1, slot=1)]     # 共享{仙舟}(狼狩/减益不在板面)
        return dep, bench, [d.char_id for d in dep]

    def test_default_is_gap(self):
        assert cw_waiting_piece.RECIPE_WAITING_MODE == 'gap'

    def test_flip_switches_behavior(self, monkeypatch):
        dep, bench, _ = self._frame()
        assert recipe_waiting(dep, bench, 4)          # gap:缺口真
        monkeypatch.setattr(cw_waiting_piece, 'RECIPE_WAITING_MODE',
                            'ignition')
        assert not recipe_waiting(dep, bench, 4)      # 1+1=2 不达激活档
        monkeypatch.setattr(cw_waiting_piece, 'RECIPE_WAITING_MODE',
                            'board')
        assert recipe_waiting(dep, bench, 4)          # 纯板面域无缺口排除

    def test_ignition_fires_on_tier_crossing(self, monkeypatch):
        dep = [_bc('姬子·启行', star=1, slot=1),
               _bc('阮·梅', star=1, slot=2),
               _bc('卡芙卡', star=1, slot=3),
               _bc('白厄', star=1, slot=4)]           # 列车同行 1
        bench = [_bc('瓦尔特', star=1, slot=1)]       # 共享{列车同行}
        monkeypatch.setattr(cw_waiting_piece, 'RECIPE_WAITING_MODE',
                            'ignition')
        assert recipe_waiting(dep, bench, 4)          # 1+1=2 ∈ tiers(2,4,6)


class TestFiveSiteSingleSourceParity:
    """五消费位单一源对拍锁(E5;改谓词多处同改的旧登记面已随收敛
    批改为单一源委托,本锁防任何消费位残留平行实现)。"""

    def _frames(self) -> list[tuple[list, list, int]]:
        dep_gap = [_bc('姬子·启行', star=1, slot=1),
                   _bc('花火', star=1, slot=2),
                   _bc('阮·梅', star=1, slot=3),
                   _bc('卡芙卡', star=1, slot=4)]
        dep_sat = [_bc(m, star=2, slot=i + 1) for i, m in enumerate(_KM)]
        return [
            (dep_gap, [_bc('三月七', star=1, slot=1)], 4),    # 1★ 缺口件
            (dep_sat, [_bc('阮·梅', star=2, slot=1)], 4),     # 线外 2★(收窄)
            (dep_sat, [], 4),                                  # 无候选件
            ([], [_bc('三月七', star=2, slot=1)], 4),          # 未板满
        ]

    def test_criteria_delegation_parity(self):
        for dep, bench, cap in self._frames():
            st = SimpleNamespace(max_units=lambda cap=cap: cap)
            expect = recipe_waiting(dep, bench, cap)
            assert crit_levelup._realize_chain_ready(st, bench, dep) \
                == expect, 'criteria 委托位与单一源失偶'

    def test_checker_consumes_authoritative_key(self):
        """检查器按击真值优先级:dec_recipe_waiting(现役权威)压过
        旧谓词形态键与行末近似(ADR-0589/ADR-0592 三级优先)。"""
        from sr_od.application.currency_war.sim.checks.ledger import (
            check_levelup_budget_gate,
        )
        dep = [{'char_id': m, 'star': 2} for m in _KM]

        def _row(actions: list[dict], bench: list[dict]) -> dict:
            return {
                'plane': 1, 'round_num': 6, 'gold': 32,
                'target_comp': '列车同行',
                'state': {'level': 4, 'cap': 4,
                          'bench': bench, 'deployed': dep},
                'sim': {'node': 'battle',
                        'shop_waves': [{'gold': 40}],
                        'spend': {'levelup': 8}},
                'actions': actions,
            }

        # 权威键 True 压过「行末无资格件」(t133 当帧上板形态)+旧键 False:
        # 按击豁免
        rows = [_row([_lv_action(True, legacy=True)],
                     bench=[{'char_id': '白厄', 'star': 1}])]
        assert check_levelup_budget_gate(rows) == []
        # 权威键 False 压过旧键 True(旧键存在不放宽豁免):
        rows_shut = [_row([_lv_action(False, legacy=True)],
                          bench=[{'char_id': '阮·梅', 'star': 2}])]
        assert len(check_levelup_budget_gate(rows_shut)) == 1


class TestStatefnRedirectParity:
    """statefn 重定向位边界对拍锁(ARM1 sink 单一源守卫,ADR-0516
    先例:重定向位若被改回独立实现,边界格漂移即红)。"""

    def test_boundary_grid_parity(self):
        dep_gap = ['姬子·启行', '花火', '阮·梅', '卡芙卡']
        cases: list[tuple[int, list[str], list[str], int | None]] = [
            (0, [], [], None),
            (10, ['三月七'], ['姬子·启行'], None),      # cap=None 兜底 10
            (15, ['三月七'], ['姬子·启行'] * 15, 15),   # cap>10 封顶
            (4, ['三月七'], dep_gap, 4),
            (4, [], dep_gap, 4),
            (4, ['未知件'], dep_gap, 4),                 # 未注册名跳过
            (3, ['瓦尔特'], ['姬子·启行', '花火', '瓦尔特'], 3),  # 全 dup 域
        ]
        for count, bench_names, dep_names, cap in cases:
            assert statefn_predicates.arm1_existence(
                count, bench_names, dep_names, cap) \
                == cw_waiting_piece.arm1_existence(
                    count, bench_names, dep_names, cap), \
                f'重定向位失偶: {(count, bench_names, dep_names, cap)}'
