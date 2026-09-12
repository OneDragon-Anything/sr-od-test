"""F1 病理(围栏拦空槽部署)修复回归锁(4 条;ADR-0473)。

出处:围栏互斥辖域收窄设计(裁决1「显式>围栏,同轮互斥」的轮级禁运
收窄为「通道级+保留集」)+ 命题 P24(docs/game/currency_war/research/
proofs/p24-residual-fill-dominance.md:C=I=0 下残余补部署严格支配
整轮禁运)。病理:skip 轮轮末整轮禁运部署,演进换阵/3合1 吞副本
造成的板面空槽连续过夜,欠载打仗掉血(seed 640247 r5-r7 缩退
6→3→2 实证)。锁面:
1. 补部署锁(skip 轮轮末 deployed 回填+账本行在);
2. 同名 dedup 锁(与在场同名的素材副本不被补部署——保留集投影已随
   v3_hoard 通道退役删除后唯一存留面);
3. 支配性形状锁(B−A 的 deployed 差=补上件数,零支出);
4. 扩窗锁(check_deploy_fills_cap 轮窗 r2-r9,r6-r7 短缺可报)。
"""
from __future__ import annotations

from sr_od.application.currency_war.kernel.cw_state import (
    BenchChar,
    GameState,
    bench_occupied,
    iter_occupied_deployed,
)
from sr_od.application.currency_war.sim.checks.ledger import (
    check_deploy_fills_cap,
    check_skip_fence_pairing,
)
from sr_od.application.currency_war.sim.engine_p1 import (
    _residual_fill_deploy,
    simulate_p1,
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
        st, frozenset(), frozenset(), frozenset(), frozenset())
    dep_n = sum(1 for _ in iter_occupied_deployed(st.deployed))
    assert dep_n == 1 + up and up >= 2, (up, held, dep_n)
    assert st.gold == 20, '补部署零支出'
    assert bench_occupied(st.bench) == 4 - up


def test_skip_round_ledger_row_and_pairing_intact() -> None:
    """集成锁:skip_fence 账本行仍在(配对锁不破),residual 字段披露。"""
    from sr_od.application.currency_war.kernel.cw_state import SellDeployed

    class _Stub:
        fired = False

        def decide_shop_screen(self, sess, screen):  # noqa: ARG002
            # 决策后读帧断言改容器读(W6 波 4 迁移约定 2:黑板槽退役)。
            from sr_od.application.currency_war.kernel.cw_board_state import (
                board_state_of,
                deployed_slots_of,
            )
            slots = deployed_slots_of(board_state_of(sess))
            occ = [i for i, d in enumerate(slots) if d is not None]
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


# (锁 2b 取证帧锁 test_seed_640576 / test_seed_643567 已随 decision_v2
# 基线臂退役删除——取证形态不可复现;dd-038 检查点② / commit b94e9cfb,
# 2026-09-04 用户裁定清理。)


# (保留集锁 test_reserved_pieces_not_deployed 已随 v3_hoard 通道退役
# 删除——保留集投影恒空(A6 裁决 / dd-038 统一迁移批,2026-09-04
# 用户裁定清理);同名 dedup 存留面由下一锁承载。)


def test_deployed_name_material_copies_held() -> None:
    """与在场同名(deployed)的素材副本不被补部署(5.1.7 在场唯一,
    围栏 dedup 自然 held)——保留集投影退役后唯一存留的 held 面。"""
    st = _st(6, [_bc('爻光', '仙舟'), _bc('停云', '仙舟')],
             [_bc('爻光', '仙舟'), _bc('停云', '仙舟'),
              _bc('三月七', '仙舟'), _bc('乙', '仙舟')])
    st.board = {'仙舟': 2}
    up, _held, lag = _residual_fill_deploy(
        st, frozenset(), frozenset(), frozenset(), frozenset())
    dep_names = {d.char_id for d in iter_occupied_deployed(st.deployed)
                 if d.char_id}
    assert dep_names == {'爻光', '停云', '三月七', '乙'}, dep_names
    assert lag == 0


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
        st, frozenset(), frozenset(), frozenset(), frozenset())
    dep_b = sum(1 for _ in iter_occupied_deployed(st.deployed))
    assert dep_b - dep_a == up and up >= 0
    assert st.gold == 20, 'B 臂零支出(C=I=0)'


# ---------- 锁 4:扩窗锁 ----------

def _short_row(rn: int) -> dict:
    return {
        'plane': 1, 'round_num': rn,
        'state': {'deployed': [{'char_id': f'x{k}'} for k in range(2)],
                  'cap': 6},
        'sim': {'deploy_lag_units': 2},
    }


def test_window_extended_to_r9_reports_late_shortfall() -> None:
    """扩窗锁:r6-r7 连续短缺必须报(旧窗 r2-r4 对此帧恒静默——
    W714 F1 三例全在窗外);r2-r3 对照仍报(窗口未缩)。"""
    assert check_deploy_fills_cap([_short_row(6), _short_row(7)]), \
        'r6-r7 连续短缺应报(扩窗语义)'
    assert check_deploy_fills_cap([_short_row(2), _short_row(3)])
    assert not check_deploy_fills_cap([_short_row(5), _short_row(7)]), \
        '非连续轮不报(连续 2 轮门不变)'
