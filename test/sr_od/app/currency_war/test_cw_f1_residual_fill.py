# -*- coding: utf-8 -*-
"""F1 病理(围栏拦空槽部署)修复回归锁(4 条;ADR-0473)。

出处:围栏互斥辖域收窄设计(裁决1「显式>围栏,同轮互斥」的轮级禁运
收窄为「通道级+保留集」)+ 命题 P24(docs/game/currency_war/research/
proofs/p24-residual-fill-dominance.md:C=I=0 下残余补部署严格支配
整轮禁运)。病理:skip 轮轮末整轮禁运部署,演进换阵/3合1 吞副本
造成的板面空槽连续过夜,欠载打仗掉血(seed 640247 r5-r7 缩退
6→3→2 实证)。锁面:
1. 补部署锁(skip 轮轮末 deployed 回填+账本行在);
2. 保留集锁(3合1 素材副本+locked 持有名单件不被补部署);
3. 支配性形状锁(B−A 的 deployed 差=补上件数,零支出);
4. 扩窗锁(check_deploy_fills_cap 轮窗 r2-r9,r6-r7 短缺可报)。
"""
from __future__ import annotations

from sr_od.application.currency_war.kernel.cw_intention import HoardTarget
from sr_od.application.currency_war.kernel.cw_state import (
    BenchChar,
    GameState,
    bench_occupied,
    iter_occupied_deployed,
)
from sr_od.application.currency_war.sim.cw_sim import (
    _residual_fill_deploy,
    simulate_p1,
)
from sr_od.application.currency_war.sim.cw_sim_checks import (
    check_deploy_fills_cap,
    check_skip_fence_pairing,
)


def _st(level: int, deployed: list[BenchChar],
        bench: list[BenchChar]) -> GameState:
    """构造帧:deployed/bench 紧缩表,board=仙舟计数由调用方对齐。"""
    return GameState(level=level, deployed=list(deployed),
                     bench=list(bench), board={}, gold=20)


def _bc(cid: str, faction: str = '?', star: int = 1,
        pos: str = 'back') -> BenchChar:
    return BenchChar(slot=0, char_id=cid, faction=faction, star=star,
                     position_pref=pos)


def _sess_locked_hoard(names: tuple[str, ...]) -> object:
    """带 locked 持有名单的 session 桩( finals 买而不上件的持有面)。"""

    class _S:
        v3_hoard: HoardTarget = HoardTarget(
            frozenset(names), frozenset(), 'locked')

    return _S()


# ---------- 锁 1:补部署锁 ----------

def test_residual_fill_deploys_into_vacancy() -> None:
    """skip 轮残余补部署:applied 显式动作轮轮末,围栏认可件回填空槽。

    成对件(仙舟,board 已有 1 → bench 2 张凑 ≥2)必须被补上场;
    零支出断言:金不变、bench 只减(上阵)不卖。
    """
    st = _st(4, [_bc('爻光', '仙舟')],
             [_bc('三月七', '仙舟'), _bc('停云', '仙舟'),
              _bc('乙', '仙舟'), _bc('乙', '仙舟')])
    st.board = {'仙舟': 1}
    up, held, _lag = _residual_fill_deploy(
        st, object(), frozenset(), frozenset(), frozenset(), frozenset())
    dep_n = sum(1 for _ in iter_occupied_deployed(st.deployed))
    assert dep_n == 1 + up and up >= 2, (up, held, dep_n)
    assert st.gold == 20, '补部署零支出'
    assert bench_occupied(st.bench) == 4 - up


def test_skip_round_ledger_row_and_pairing_intact() -> None:
    """集成锁:skip_fence 账本行仍在(配对锁不破),residual 字段披露。"""
    from sr_od.application.currency_war.kernel.cw_state import SellDeployed

    class _Stub:
        fired = False

        def update_target(self, st, sess, screen) -> None:  # noqa: ARG002
            pass

        def decide_prep(self, st, sess, screen):  # noqa: ARG002
            occ = [i for i, d in enumerate(st.deployed) if d is not None]
            if not self.fired and occ:
                self.fired = True
                return [SellDeployed(occ[0], reason='f1_lock_stub')]
            return []

    stub = _Stub()
    res = simulate_p1(7, strategy=stub, pool='fallback')
    assert stub.fired and res.fence_skips == 1
    fired = [r for r in res.ledger
             if any(a.get('__type__') == 'SellDeployed'
                    for a in r.get('actions') or [])]
    assert len(fired) == 1
    row = fired[0]
    skips = [a for a in row.get('actions') or []
             if a.get('__type__') == 'skip_fence']
    assert len(skips) == 1 and skips[0].get('reason')
    sim = row.get('sim') or {}
    assert 'residual_deployed' in sim and 'residual_held' in sim
    if sim.get('residual_deployed'):
        assert skips[0]['reason'].endswith('+residual_fill')
    assert check_skip_fence_pairing(res.ledger) == []


# ---------- 锁 2:保留集锁 ----------

def test_reserved_pieces_not_deployed() -> None:
    """显式保留集两成员均不被补部署(residual_held 计数)。

    ① 3合1 素材副本:bench 同名同星 ×2 且全场无 deployed 同名——
    围栏 fill_mode 本会上一张,保留集必须扣下(锁 ADR-0323 修法一的
    素材囤积语义);② final 买而不上件:v3_hoard locked 模式
    char_targets 成员(锁 [21] 窗口语义)。同帧的成对件照常补上。
    """
    st = _st(6, [_bc('爻光', '仙舟')],
             [_bc('乙', '仙舟'), _bc('乙', '仙舟'),
              _bc('甲', '仙舟'),
              _bc('三月七', '仙舟'), _bc('停云', '仙舟')])
    st.board = {'仙舟': 1}
    sess = _sess_locked_hoard(('甲',))
    up, held, _lag = _residual_fill_deploy(
        st, sess, frozenset(), frozenset(), frozenset(), frozenset())
    dep_names = {d.char_id for d in iter_occupied_deployed(st.deployed)
                 if d.char_id}
    assert '乙' not in dep_names and '甲' not in dep_names, dep_names
    assert held == 3, (up, held)
    assert {'三月七', '停云'} <= dep_names


# ---------- 锁 3:支配性形状锁 ----------

def test_fill_dominates_forbidden_shape() -> None:
    """P24 行为面:同一帧,A(禁运)与 B(补部署)的 deployed 数差
    = 补上件数,且 B ≥ A、金/bench 守恒(B 的 bench 减少=上场数)。
    锁形状不锁分布数值。"""
    st = _st(6, [_bc('爻光', '仙舟')],
             [_bc('三月七', '仙舟'), _bc('停云', '仙舟'),
              _bc('乙', '仙舟'), _bc('乙', '仙舟')])
    st.board = {'仙舟': 1}
    dep_a = sum(1 for _ in iter_occupied_deployed(st.deployed))
    up, _held, _lag = _residual_fill_deploy(
        st, object(), frozenset(), frozenset(), frozenset(), frozenset())
    dep_b = sum(1 for _ in iter_occupied_deployed(st.deployed))
    assert dep_b - dep_a == up and up >= 0
    assert st.gold == 20, 'B 臂零支出(C=I=0)'


# ---------- 锁 4:扩窗锁 ----------

def _short_row(rn: int) -> dict:
    return {
        'plane': 1, 'round_num': rn,
        'state': {'deployed': [{'char_id': f'x{k}'} for k in range(2)],
                  'cap': 6,
                  'bench': [{'char_id': f'y{k}'} for k in range(5)]},
    }


def test_window_extended_to_r9_reports_late_shortfall() -> None:
    """扩窗锁:r6-r7 连续短缺必须报(旧窗 r2-r4 对此帧恒静默——
    W714 F1 三例全在窗外);r2-r3 对照仍报(窗口未缩)。"""
    assert check_deploy_fills_cap([_short_row(6), _short_row(7)]), \
        'r6-r7 连续短缺应报(扩窗语义)'
    assert check_deploy_fills_cap([_short_row(2), _short_row(3)])
    assert not check_deploy_fills_cap([_short_row(5), _short_row(7)]), \
        '非连续轮不报(连续 2 轮门不变)'
