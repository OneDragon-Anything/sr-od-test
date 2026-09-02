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

from sr_od.application.currency_war.sim.engine_p1 import _residual_fill_deploy, simulate_p1

from sr_od.application.currency_war.sim.checks.ledger import check_deploy_fills_cap, check_skip_fence_pairing


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

        def decide_shop_screen(self, sess, screen):  # noqa: ARG002
            st = sess.shop_state_frame
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


# ---------- 锁 2b:单趟遗留锁(W718 第五波自捕 seed 640576) ----------

def test_seed_640576_no_residual_lag_after_fill() -> None:
    """取证局锁:skip 轮补部署后不得残留「围栏认可件未上」(lag>0)。

    640576 r5-r7 在单趟 fill 实现(补部署首版)下 dep 5/7 停滞、
    lag=2 连续三轮:补部署自身上场改变 board 阵营计数后,成对/点火
    判据对尚未上场的件翻转达标,单趟不再重判。修法=不动点循环
    (上场后重跑围栏至 up 空)。本锁钉该形态:全部 skip 轮 lag 恒 0。
    pool='snapshot'(W718 跑批时指纹 6400d5d8edeaf68d+eqg1;F6 语料
    治理后快照随库前移,本锁钉的是围栏语义形态而非池内容——取证
    形态消失则按锁纪律换锁帧,不机械跟绿)。
    """
    res = simulate_p1(640576, pool='snapshot', planes=2)
    bad = [(int(r.get('round_num') or 0),
            int((r.get('sim') or {}).get('deploy_lag_units') or 0))
           for r in res.ledger
           if (r.get('sim') or {}).get('fence_skipped')]
    assert bad, '取证形态应在该 seed 出现(否则换锁帧)'
    assert all(n == 0 for _, n in bad), bad
    # 补部署确实发生过(非「无事可补」的假绿)
    assert any(int((r.get('sim') or {}).get('residual_deployed') or 0) >= 2
               for r in res.ledger)


def test_seed_643567_fence_held_not_flagged() -> None:
    """W767 取证局锁:换阵重摆期补部署无残余(全部 skip 轮 lag=0)。

    643567 r5-r8:演进换阵每轮把板面拆回 2 人,补部署按围栏(生产
    同源)回填配方/核心 2 件;bench 残余 = 在场同名素材(dedup)+
    跨线散牌(配方底线合法 held)——fill lag=0 = 围栏认可件全部
    上完,属合法过渡形态(W755/W767 同型)。检查器「有货」口径已
    收敛到 lag(见 check_deploy_fills_cap),本局不得再报。
    """
    from sr_od.application.currency_war.sim.checks.ledger import (
        check_deploy_fills_cap,
    )

    res = simulate_p1(643567, pool='snapshot', planes=2)
    fills = [(int(r.get('round_num') or 0),
              int((r.get('sim') or {}).get('deploy_lag_units') or 0))
             for r in res.ledger
             if (r.get('sim') or {}).get('fence_skipped')]
    assert fills, '取证形态应在该 seed 出现(否则换锁帧)'
    assert all(n == 0 for _, n in fills), fills
    assert check_deploy_fills_cap(res.ledger) == []


# ---------- 锁 2:保留集锁 ----------

def test_reserved_pieces_not_deployed() -> None:
    """显式保留集(final 买而不上件)不被补部署;素材副本交围栏 dedup。

    W748 收窄裁决(ADR-0473 增补):保留集 ① 原「同名同星全场 ≥2
    即保留」把 bench 同名对(无在场同名)也整对扣下——3合1 合并域是
    全场,部署一对之一不破坏合成,生产围栏 dedup 只拦「在场同名」,
    保留 bench 对 = 过宽,642763/642795 实证 dep 停滞 4/7、5/7(本波
    F1 重现根因)。收窄后:保留集只剩 locked/forced 持有名单([21]
    窗口语义);与在场同名的素材副本由围栏 dedup 自然 held。
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
    # W748 回归面:bench 同名对的一张照常补上(部署不破全场域合成)
    assert '乙' in dep_names, dep_names
    # final 买而不上件(locked 持有名单)仍被保留
    assert '甲' not in dep_names and held == 1, (up, held)
    assert {'三月七', '停云'} <= dep_names


def test_deployed_name_material_copies_held() -> None:
    """与在场同名(deployed)的素材副本不被补部署(5.1.7 在场唯一,
    围栏 dedup 自然 held)——首版保留集删去后的等价面锁。"""
    st = _st(6, [_bc('爻光', '仙舟'), _bc('停云', '仙舟')],
             [_bc('爻光', '仙舟'), _bc('停云', '仙舟'),
              _bc('三月七', '仙舟'), _bc('乙', '仙舟')])
    st.board = {'仙舟': 2}
    up, _held, lag = _residual_fill_deploy(
        st, object(), frozenset(), frozenset(), frozenset(), frozenset())
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
        st, object(), frozenset(), frozenset(), frozenset(), frozenset())
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
