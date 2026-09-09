"""假局 harness(T-120 sim 重设计 批 1;方案 §7.1 测试仓「cw_harness」行)。

职责 = 把「真 op 跑在假环境」的装配一次性收口,测试只编排不碰装配细节:

- **端口安装**:构建 ``FakeMatch`` + ``FakeCwObserver``/``FakeActionSink``
  后 ``install_game_ports`` 显式接通(方案 §3.3 装配纪律;teardown 卸载);
- **档案根接通**:遥测写根三槽同点接指假局档案根(tmp_path 下)——
  recorder 落盘根槽(``telemetry.state.set_recorder_replay_dir``,F4)
  + journal 根槽(``op_journal.set_journal_dir``,T-129/T-130 混流注记
  的写端隔离)+ 决策帧落盘根槽(``decision_frame_hooks.
  set_decision_frame_dir``,三审二波 F2:原为无槽第三根,靠私函数
  monkeypatch 兜)——假局遥测全链落生产 schema、零触真实 .debug 根;
- **真策略对局**:`MandateV1Strategy().create_session` 冷建(与生产
  run_buy_waves match=None 分支同源,ADR-0583 唯一冷建口)——被测对象
  含真策略器,决策非桩;
- **读图域桩**(识别/执行缺陷面结构性为零的申报面,方案 §4-6):截图
  旋转亮度帧、``new_bench_slots`` pixel-diff 读数按假局 bench 真值差分、
  stdlib sleep 桩(段顶 settle/刷新稳定门等待零信息量,先例 =
  test_cw_shop_refresh 同款);
- **局终收口**:逐节点 outcome 行(生产 ``record_outcome`` schema 形状,
  真值位恒真)+ 局终 run summary(经生产 ``state.record_run_summary``;
  Δ池局终再生钩在 harness 内桩化——它是读实机档案并重写池快照的
  真实副作用,测试零副作用纪律要求整链桩化,测试纪律 4)。

方案出处 = ``.debug/temp/currency_war/t120_sim_redesign/方案.md``
§6.2 批 1 行(**易失产物**,ADR 落点待退役批分配,后续批回填)。
"""
from __future__ import annotations

import contextlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np

from fixtures.cw_fake_game.fake_match import FakeMatch
from fixtures.cw_fake_game.fake_ports import FakeActionSink, FakeCwObserver
from sr_od.application.currency_war import cw_game_ports
from sr_od.application.currency_war.cw_game_ports import install_game_ports
from sr_od.application.currency_war.operations import decision_frame_hooks as dfh
from sr_od.application.currency_war.strategies.impl.cw_strategy import (
    CurrencyWarMatch,
)
from sr_od.application.currency_war.telemetry import op_journal, recorder
from sr_od.application.currency_war.telemetry import state as tel_state

if TYPE_CHECKING:
    from collections.abc import Iterator

    from test.conftest import SrTestContext


@dataclass
class FakeRoundOutcome:
    """假局节点结算的 outcome 行载荷(生产 ``record_outcome`` 消费的
    属性面;字段名 = cw_performance.RoundOutcome 对齐,recorder 按
    属性读取)。真值位:``hp_confidence=1.0``(状态机真值,非 OCR)。
    """

    round_num: int
    plane: int
    node_type: str
    comp_tag: str = ''
    intentional_fold: bool = False
    hp_after: int = 0
    hp_confidence: float = 1.0
    enemy_hp_after: int | None = None
    damage_dealt: int | None = None
    killed: bool = False
    progress_delta: int | None = None
    streak: int | None = None


@dataclass
class FakeP1Result:
    """一局假 P1 的全程轨迹(确定性对拍与保真度统计的载体)。

    ``rounds[r]`` 键 = 位面内轮次(1 起);每轮含收入分解/动作账/结算
    回执——全部来自生产链路的返回值与状态机真值,零测试侧再计算。
    ``launched`` = 本局发射面真实发生(策略出战出口或达标臂真链;
    批 2 发射面判定位,逐轮任一即置位)。
    """

    seed: int
    rounds: dict[int, dict[str, Any]] = field(default_factory=dict)
    launched: bool = False
    armed_evaluated: bool = False

    @property
    def gold_trajectory(self) -> list[int]:
        """逐备战期期初金(收入入账后、开店前;与 runs summary 采样点
        同语义域——决策时点金)。"""
        return [r['gold_after_income'] for r in self.rounds.values()]

    @property
    def hp_trajectory(self) -> list[int]:
        """逐节点结算后 hp(下钳 0/上界 HP_UPPER_BOUND 后真值)。"""
        return [r['settlement'].hp_after for r in self.rounds.values()]

    def trajectory(self) -> dict[int, tuple[float | None, float | None]]:
        """逐轮 (期初金, 结算后 hp) 视图(保真度对拍件的输入形)。"""
        out: dict[int, tuple[float | None, float | None]] = {}
        for r, row in self.rounds.items():
            stl = row['settlement']
            out[r] = (row['gold_after_income'],
                      None if stl is None else float(stl.hp_after))
        return out


def bands_from_trajectories(
        games: list[dict[int, tuple[float | None, float | None]]],
) -> dict[int, dict[str, tuple[float, float] | tuple[None, None]]]:
    """逐轮基线带((中位, p90);保真度对拍件统计单一源)。

    假局批与实机档案批共用本 helper(离线 runner 同 import)——红 = 对拍
    统计口径分叉。输入 = 每局「轮 → (期初金, 结算后 hp)」视图。
    """
    import statistics

    slots: dict[int, dict[str, list[float]]] = {}
    for game in games:
        for r, (gold, hp) in game.items():
            slot = slots.setdefault(r, {'gold': [], 'hp': []})
            if gold is not None:
                slot['gold'].append(float(gold))
            if hp is not None:
                slot['hp'].append(float(hp))

    def _band(vals: list[float]) -> tuple[float, float] | tuple[None, None]:
        if not vals:
            return None, None
        ordered = sorted(vals)
        p90 = ordered[min(int(len(ordered) * 0.9), len(ordered) - 1)]
        return statistics.median(vals), p90

    return {r: {'gold': _band(v['gold']), 'hp': _band(v['hp'])}
            for r, v in sorted(slots.items())}


class FakeP1Run:
    """一局假 P1 的装配与驱动(用法见 :func:`fake_p1_run`)。"""

    def __init__(self, ctx: SrTestContext, seed: int, *,
                 node_sequence: list[str] | None = None,
                 initial_hp: int | None = None,
                 initial_gold: int | None = None) -> None:
        self.ctx: SrTestContext = ctx
        self.seed: int = seed
        kw: dict[str, Any] = {'seed': seed}
        if node_sequence is not None:
            kw['node_sequence'] = list(node_sequence)
        if initial_hp is not None:
            kw['initial_hp'] = initial_hp
        self.match: FakeMatch = FakeMatch(**kw)
        # 剧本注金(场景注入,同 sim 投资剧本的注入语义:环境事实由
        # 测试编排给定,非策略可见的特殊通道);None = 环境开局金缺省
        # (DEFAULT_OPENING_GOLD=5,保真校准后的机制真值,锚注见
        # fake_match 模块)
        if initial_gold is not None:
            self.match.state.gold = initial_gold
        # 真策略对局(与生产 run_buy_waves 的 match=None 冷建分支同源;
        # 被测对象含真策略器,方案 §2.1「策略器=被测对象」)。壳 =
        # 生产注册面 MandateV1Live(strategies/mandate_v1_strategy.py):
        # 装配缝(_assemble_turn)在其上覆写注入,prep 决策入口
        # decide_prep_screen 消费装配链——直接实例化 impl 基类会在
        # 装配缝哨兵处显式拒绝(桥壳哨兵语义,非缺陷)。
        config = self._config()
        from sr_od.application.currency_war.strategies.mandate_v1_strategy import (
            MandateV1Live,
        )
        _def = MandateV1Live()
        self.cw_match: CurrencyWarMatch = CurrencyWarMatch(
            _def, _def.create_session(config))
        # 节点序列供给(实机信息通道的假环境对位;缺它 = 策略器节点感知
        # 判据族在假环境恒盲——M3 节点感知升级②(b) fail-open 不发射、
        # 保连胜门读 node_type_current 恒空、r_remaining/schedule_of
        # 储蓄视界退先验,属「环境结构性无机会」面,保真校准申报):四通道
        # 各对位实机写点——①节点台账 ledger(cw_state.ledger_node_type
        #   消费;实机写点 = 位面详情采集,source 同名通道)②plane_node_table
        #   (cw_plane_table.r_remaining 消费;实机写点 = 备战开局帧槽序)
        #   ③逐轮 node_type_current 在 run_p1 决策前写(引擎对位 = engine_p1
        #   决策前写 session.node_type_current,engine_p1.py:827 同位)
        #   ④plane_lengths_seen(schedule_of 消费,见下)。
        _session = self.cw_match.session
        from sr_od.application.currency_war.kernel.cw_state import (
            ledger_update_plane,
        )
        ledger_update_plane(_session, 1, list(self.match.node_sequence),
                            source='plane_detail')
        _session.plane_node_table = list(self.match.node_sequence)
        _session.plane_node_table_plane = 1
        # ④位面长度序列(schedule_of 视界消费面;实机写点 = cw_screen_prep
        # 每位面首帧 append(len(seq)),引擎对位 = engine_p1 进场补记同形)
        if _session.plane_lengths_seen is None:
            _session.plane_lengths_seen = []
        _session.plane_lengths_seen.append(len(self.match.node_sequence))
        # 真被测 op 壳(run_buy_waves 的宿主;动作执行不点真坐标——
        # 执行步经端口改道,sink 承接)
        from sr_od.application.currency_war.operations.cw_op.cw_op_buy_cards import (
            CwOpBuyCards,
        )
        self.op: Any = CwOpBuyCards(ctx)
        # 访问前 bench 槽键快照(槽 → (char_id, star)):M2 修后口径 =
        # **逐槽差分**(像素 diff 的「槽变了」语义对位),非身份值集差分
        self._bench_pre_slots: dict[int, tuple[str, int]] = {}
        self._shot_i: int = 0
        # —— 批 2(prep 域实体化)状态 ——
        # 逐动作落点审计(方案批 2 验收②):每次执行缝落地记录
        # (动作键/applied/pre-post 真值摘要),链相邻衔接断言的载体。
        self.prep_audit: list[dict[str, Any]] = []
        # 商店访问产出捕获(visit_open_shop → run_buy_waves 的 outcome,
        # 经模块attr捕获桩直传,run_prep_phase 消费)
        self.last_shop_outcome: Any = None
        # monkeypatch 引用(fake_p1_run 存入;run_p1 无参调用的既有测试
        # 契约保持,prep 相位补丁内部取用)
        self._monkeypatch: Any = None

    def _config(self) -> Any:
        from sr_od.application.currency_war.currency_war_config import (
            CurrencyWarConfig,
        )
        return CurrencyWarConfig(self.ctx.current_instance_idx)

    # ---- 桩面(读图域;方案 §4-6「识别/执行缺陷面结构性为零」)----

    def _install_stubs(self, monkeypatch: Any) -> None:
        """读图域桩集合(全部 monkeypatch,teardown 自动还原)。

        决策帧留证目录不在此列:落盘根走三槽接线(fake_p1_run 同点
        ``set_decision_frame_dir``),不再 monkeypatch 私函数 ``_out_dir``
        (三审二波 F2:私函数改道是不经机制的调用侧自觉,正式槽接线
        后该补桩形态退役)。
        """
        from sr_od.application.currency_war.operations.cw_op import (
            cw_op_buy_cards as buy_mod,
        )
        from sr_od.application.currency_war.telemetry import defects

        # stdlib sleep 桩:段顶 settle 0.3s/刷新稳定门 0.25s 步进等在替身
        # 帧上零信息量(先例 = test_cw_shop_refresh:403 同款;monkeypatch
        # 挂 stdlib time 模块属性,teardown 还原)
        monkeypatch.setattr(buy_mod.time, 'sleep', lambda *_a: None)
        # 截图桩:旋转亮度真 ndarray(pixel-diff/裁片通道做矩阵切片,
        # 需要合法形状;亮度翻转让「帧变化」语义可见)
        def _shot() -> np.ndarray:
            self._shot_i += 1
            v = 40 if self._shot_i % 2 else 200
            return np.full((1080, 1920, 3), v, dtype=np.uint8)

        monkeypatch.setattr(self.op, 'screenshot', _shot)
        monkeypatch.setattr(self.op, 'park_cursor', lambda *a, **k: None)
        monkeypatch.setattr(self.op, 'save_screenshot',
                            lambda *a, **k: '<stub-shot>')
        # pixel-diff 落位读数桩(落地审 M2 修后口径):**逐槽差分**——
        # 生产 reader 的计数语义 = 「槽变了」不认方向(bench_buy_count_ok
        # docstring 在案:卖出/合并的槽变化也计入,留证级),故桩按槽键
        # 对比占用身份(空→占/占→空/换人/换星都算变),与生产对同一
        # 执行事实的计数对齐。旧「身份值集差分」在回购同名(值集去重
        # 漏计)与合并换星(新值 +1 素材下架交织)形态必漂——批 1 档案
        # 35 行桩伪影的根因,已废。桩输出继续喂 bench_slot_map 与占位
        # 逻辑路径;其 defect 行经下方过滤豁免(见 M2 豁免注)。
        def _fake_new_bench_slots(_ctx: Any, _before: Any,
                                  _after: Any) -> list[int]:
            cur = self._bench_identity()
            changed = [slot for slot in set(cur) | set(self._bench_pre_slots)
                       if cur.get(slot) != self._bench_pre_slots.get(slot)]
            return sorted(changed)

        monkeypatch.setattr(buy_mod, 'new_bench_slots', _fake_new_bench_slots)
        # bench 落位 audit 结构性豁免(落地审 M2 备选路线,登记):该
        # audit 检出的是「点击落空」,其输入域 = 真实像素帧——假环境
        # 结构性不存在(执行失败面=零的申报面,方案 §2.4/§4-6①)。
        # 槽键差分桩与生产 reader 计数对齐后,残余行是 audit 自身
        # 「设计申报的留证级误报」(卖出/合并计入,生产对同一动作序
        # 也会发),不是假环境缺陷——按「如实无数据」豁免该族行,其余
        # defect 族照常入档。
        real_record_defect = defects.record_defect

        def _filtered_defect(*a: Any, **k: Any) -> None:
            if k.get('reader_source') == 'bench_buy_pixel_diff':
                return
            real_record_defect(*a, **k)

        monkeypatch.setattr(defects, 'record_defect', _filtered_defect)
        # Δ池局终再生钩桩化:它读实机档案并重写池快照数据文件(真实
        # 副作用;recorder.record_run_summary 尾部无条件调用)——测试
        # 零副作用纪律要求沿调用链整链桩化,不是「我没调 summary」式回避
        monkeypatch.setattr(recorder, '_regenerate_delta_pool_after_run',
                            lambda: None)
        # 缺陷台账复现计数按局清零(模块全局;测试纪律 4)
        monkeypatch.setattr(tel_state, '_defect_seen', {})
        monkeypatch.setattr(tel_state, '_defect_seen_run', '')
        # 本局 run_id(session 全局槽;先例 = 既有 CW 测试同款)
        monkeypatch.setattr(tel_state, '_CURRENT_RUN_ID', f'fake_{self.seed}')
        monkeypatch.setattr(self.ctx, 'cw_match', self.cw_match)

    def _bench_identity(self) -> dict[int, tuple[str, int]]:
        """假局 bench 占用身份表(槽位 → (char_id, star))。"""
        from sr_od.application.currency_war.kernel.cw_state import (
            iter_occupied,
        )
        return {b.slot: (b.char_id, b.star)
                for b in iter_occupied(self.match.state.bench)}

    # ---- 批 2:prep 域实体化(方案 §6.2 批 2 行;围栏代理退役)----

    def _seed_tracked_from_truth(self) -> None:
        """tracked 账真值播种(实机「入口 heavy 读屏重建 tracked」的假环境
        对位,每轮备战访问前同节拍):实机每节点备战环入口重读重建跟踪账
        (ADR-0517 决策 8「入口观察即对账」);假环境零读图,tracked 若停
        在冷建空账,守卫 guard_expected_vs_tracked 会把观察帧真值 bench
        误判「识别幻影」拒发首动作。真值直拨零识别(观察 = 状态机快照,
        与端口同语义),形状经 pad 单一源归一。"""
        from dataclasses import replace

        from sr_od.application.currency_war.kernel.cw_exec_state import (
            exec_state_of,
        )
        from sr_od.application.currency_war.kernel.cw_state import (
            pad_bench,
            pad_deployed,
        )
        st = self.match.state
        ex = exec_state_of(self.cw_match.session)
        ex.tracked_bench_chars[:] = [
            replace(b) if b is not None else None for b in st.bench]
        pad_bench(ex.tracked_bench_chars)
        ex.tracked_deployed[:] = [
            replace(d) if d is not None else None for d in st.deployed]
        pad_deployed(ex.tracked_deployed)

    def _truth_digest(self) -> dict[str, Any]:
        """状态机真值摘要(逐动作审计的 pre/post 载体):bench 物理槽 →
        (身份, 星, 物品槽位)/ deployed 槽位表全槽 → (身份, 星)/ 金。"""
        return {
            'bench': {b.slot: (b.char_id, b.star, bool(b.is_item_slot))
                      for b in self.match.state.bench if b is not None},
            'deployed': {i: ((d.char_id if d is not None else None),
                             (d.star if d is not None else None))
                         for i, d in enumerate(self.match.state.deployed)},
            'gold': self.match.state.gold,
        }

    def _flush_shop_window(self) -> None:
        """商店审计窗口闭合(开→收一段落一个边界项;链轴跨窗连续)。"""
        pre = getattr(self, '_shop_window_pre', None)
        if pre is None:
            return
        self._shop_window_pre = None
        self.prep_audit.append({'action': 'ShopVisit(env)',
                                'applied': True, 'pre': pre,
                                'post': self._truth_digest(),
                                'node': self._audit_node_tag()})

    def _audit_node_tag(self) -> str:
        """审计项的回合标签(跨回合收入段为域外金动,链断言按组内)。"""
        return str(getattr(self.cw_match.session, 'node_type_current', '')
                   or self.match.state.node_type or '')

    def prep_landing(self, action: Any) -> tuple[bool, str, bool]:
        """备战动作执行缝的假环境落点(执行器机械半边的替换面)。

        语义:真 op 的 wrapper 半边(S1 清键门/装备闩/期望态推进/W209j
        刹车,PrepActionExecutor.execute 内联)保持生产码执行,本方法只
        承接「点击/拖拽/验证读」的机械半边——动作落假游戏状态机
        (:meth:`FakeMatch.apply_prep`;RunDeploy 走会话语境完整装配,见
        :meth:`_run_deploy_with_context`)+ 逐动作审计 + tracked 真值重播
        (与商店 sink 同语义)。回执 ``(progressed, detail, landed)``:
        applied 即落地(规则性拒绝两域同判,架构设计 §6.3);detail 带
        假环境显影前缀,与裸 STATUS 常量永不相等(F1b 同款纪律)。
        """
        from sr_od.application.currency_war.kernel.cw_prep_actions import (
            RunDeploy,
            action_key,
        )
        self._flush_shop_window()
        pre = self._truth_digest()
        if isinstance(action, RunDeploy):
            res = self._run_deploy_with_context()
        else:
            res = self.match.apply_prep(action)
        post = self._truth_digest()
        self.prep_audit.append({
            'action': action_key(action), 'applied': bool(res.applied),
            'pre': pre, 'post': post, 'node': self._audit_node_tag()})
        if res.applied:
            # tracked 真值重播(实机对位 = 执行器 tracked 随动;漏同步 =
            # 期望态 vs tracked 双账守卫炸「投影建模 bug」假象)
            self._seed_tracked_from_truth()
        mark = '✓(fake)' if res.applied else '✗(fake-rejected)'
        return (bool(res.applied), f'{type(action).__name__} {mark}',
                bool(res.applied))

    def _run_deploy_with_context(self) -> Any:
        """RunDeploy 完整装配(会话语境版)。

        选人/围栏/排序单一源 = kernel ``select_deployments_reasoned``;
        输入装配与生产 CwOpDeploy dd-037 同源(deploy_target_sets/
        deployed_bond_counts/locked_faction_scope/
        locked_line_recipe_floor_conflict 全 kernel 函数,零第二推导)。
        身份/站位真值 = 注册表直查(假环境无 SIFT;position_pref 与
        comp.char_positions 覆盖两规则随迁,ADR-0139 同款);单步转移经
        :meth:`FakeMatch.apply` 的 DeployMove simulate 分支,本方法零
        直接落位。
        """
        from sr_od.application.currency_war.cw_game_ports import ExecResult
        from sr_od.application.currency_war.data.cw_chars import CHARACTERS
        from sr_od.application.currency_war.kernel import cw_deploy_logic
        from sr_od.application.currency_war.kernel.cw_state import (
            DeployMove,
            iter_occupied_deployed,
        )
        from sr_od.application.currency_war.kernel.cw_strategy_session import (
            strategy_state_of,
        )

        m = self.match
        st = m.state
        occ = [b for b in st.bench if b is not None]
        if not occ:
            return ExecResult(applied=False, observed=st.copy())
        cap = st.max_units()
        if cap is None:
            return ExecResult(applied=False, observed=st.copy())
        _ss = strategy_state_of(self.cw_match.session)
        _tgt, _fw = cw_deploy_logic.deploy_target_sets(
            getattr(_ss, 'target_comp', None),
            getattr(_ss, 'transition_framework', ''))
        _cores = list(getattr(getattr(_ss, 'target_comp', None),
                              'core_chars', None) or [])
        from sr_od.application.currency_war.kernel.cw_intention import (
            locked_faction_scope,
            locked_line_recipe_floor_conflict,
        )
        _locked = locked_faction_scope(
            getattr(_ss, 'v3_intention', None)) or frozenset()
        _rf = locked_line_recipe_floor_conflict(
            getattr(_ss, 'v3_intention', None))
        dep_occ = list(iter_occupied_deployed(st.deployed))
        dep_cids = {d.char_id for d in dep_occ if d.char_id}
        dep_fac = cw_deploy_logic.deployed_bond_counts(dep_cids)
        # 站位装配:命途默认 + comp 特定覆盖(覆盖语义随生产两规则)
        bench_pos: dict[int, str] = {}
        for i, b in enumerate(occ):
            bench_pos[i] = b.position_pref or 'back'
        _tc = getattr(_ss, 'target_comp', None)
        if _tc is not None and getattr(_tc, 'char_positions', None):
            for i, b in enumerate(occ):
                if b.char_id in _tc.char_positions:
                    bench_pos[i] = _tc.char_positions[b.char_id]
        _up_rel, _held, _reasons = cw_deploy_logic.select_deployments_reasoned(
            occ,
            deployed_cids=dep_cids,
            deployed_fac=dict(dep_fac),
            board=dict(st.board or {}),
            cap=cap,
            target_factions=_tgt,
            target_cores=set(_cores),
            fw_carry=_fw,
            locked_factions=_locked,
            recipe_floor_lock_exempt=_rf,
        )
        n_up = 0
        for i in _up_rel:
            if i >= len(occ):
                continue
            bc = occ[i]
            bench_idx = st.bench.index(bc)
            ch = CHARACTERS.get(bc.char_id)
            row = bench_pos.get(i, 'back')
            faction = bc.faction or (
                (ch.factions or ['?'])[0] if ch is not None else '?')
            res = m.apply(DeployMove(bench_idx=bench_idx, to_row=row,
                                     faction=faction))
            if res.applied:
                n_up += 1
        return ExecResult(applied=n_up > 0, verification={'up': n_up},
                          observed=st.copy())

    @staticmethod
    def fence_up_slots_for(match: Any) -> list[int]:
        """围栏单一源直调(批 2 验收③对拍的期望半边;非执行通路)。

        与 :meth:`FakeMatch._run_deploy_basic` 同输入构造(无会话语境
        基干),返回 up 集对应的 bench 物理槽位号(1 基)——消费方 =
        迁移等价锁(直调期望 vs 真链落地),流程内零调用。
        """
        from sr_od.application.currency_war.data.cw_chars import CHARACTERS
        from sr_od.application.currency_war.kernel import cw_deploy_logic
        from sr_od.application.currency_war.kernel.cw_state import (
            iter_occupied_deployed,
        )
        st = match.state
        occ_idx = [i for i, b in enumerate(st.bench) if b is not None]
        cap = st.max_units()
        if not occ_idx or cap is None:
            return []
        dep_occ = list(iter_occupied_deployed(st.deployed))
        dep_fac: dict[str, int] = {}
        for d in dep_occ:
            ch = CHARACTERS.get(d.char_id)
            if ch is not None and ch.factions:
                dep_fac[ch.factions[0]] = dep_fac.get(ch.factions[0], 0) + 1
        up_idx, _held = cw_deploy_logic.select_deployments(
            [st.bench[i] for i in occ_idx],
            deployed_cids={d.char_id for d in dep_occ if d.char_id},
            deployed_fac=dep_fac,
            board=dict(st.board or {}),
            cap=cap,
        )
        return [st.bench[occ_idx[i]].slot for i in up_idx
                if i < len(occ_idx) and st.bench[occ_idx[i]] is not None]

    def _inject_equips_truth(self) -> None:
        """m7 发射门输入的假环境对位(session.last_owned_equips = 状态机
        库存真值直拨;实机写点 = 识别链装备读,与节点序列四通道同先例:
        实机信息通道的假环境对位,非策略可见特殊通道)。"""
        self.cw_match.session.last_owned_equips = list(
            self.match.state.equips or [])

    # ---- prep 相位驱动(真 op 全链;方案批 2 内容行)----

    def run_prep_phase(self, monkeypatch: Any, *,
                       max_visits: int = 6) -> dict[str, Any]:
        """一个备战期的真 op 驱动(批 2 载体;围栏代理退役的承接面)。

        逐 visit = 真 ``CwScreenPrep``(端口观察 → 实机策略器单动作环 →
        执行缝落假游戏);OpenShop 动作走生产流程层编排(_open_shop_phase
        → visit_open_shop → run_buy_waves,批 1 商店域链)。出口判定:
        策略出战出口(StartBattle 落地)= 本相位发射;空批/验证失败收敛
        → 达标臂真链(:meth:`_try_armed_launch`)。返回相位摘要。
        """
        from sr_od.application.currency_war.operations.cw_screen.cw_screen_prep import (
            CwScreenPrep,
        )

        self._install_prep_patches(monkeypatch)
        self._inject_equips_truth()
        visits = 0
        launched = False
        armed_evaluated = False
        d0 = self._truth_digest()
        self.prep_audit.append({'action': 'PhaseStart(env)', 'applied': True,
                                'pre': d0, 'post': d0,
                                'node': self._audit_node_tag()})
        while visits < max_visits:
            audit_before = len(self.prep_audit)
            prep = CwScreenPrep(self.ctx)
            self._stub_prep_op(prep, monkeypatch)
            rr = prep.run()
            visits += 1
            new_acts = self.prep_audit[audit_before:]
            if any(e['action'] == 'StartBattle' and e['applied']
                   for e in new_acts):
                launched = True
                break
            if rr is None or not getattr(rr, 'is_success', True):
                break   # 策略异常/执行异常 = fail-stop(留证,交编排方)
            status = getattr(rr, 'status', '') or ''
            if not new_acts and ('空批' in status or '验证失败' in status
                                 or '参数非法' in status):
                break   # 收敛:无动作可发,交达标臂
        armed_fired = False
        armed_evaluated = False
        if not launched:
            armed_evaluated, armed_fired = self._try_armed_launch()
        d1 = self._truth_digest()
        self.prep_audit.append({'action': 'PhaseEnd(env)', 'applied': True,
                                'pre': d1, 'post': d1,
                                'node': self._audit_node_tag()})
        return {'visits': visits, 'launched': launched,
                'armed_launched': armed_fired,
                'armed_evaluated': armed_evaluated,
                'outcome': self.last_shop_outcome}

    def _stub_prep_op(self, prep: Any, monkeypatch: Any) -> None:
        """实例级区域原语桩(画面原语层的环境承接;批 1 run_visit 同族)。

        - find_and_click:开店/收起按钮 = 环境规则承接(match.open/close_
          shop 相位迁移),其余探针 miss(清场注册表/未知弹层结构性无);
        - find_area:收起锚随相位、备战双锚(发射核屏态复验消费)在备战
          相位命中;
        - ocr/存档帧/画面判定桩同族;sleep 已由 _install_stubs 全局桩。
        """
        from fixtures.cw_fake_game.fake_match import (
            PHASE_PREP,
            PHASE_PREP_SHOP_OPEN,
        )

        def _shot() -> Any:
            self._shot_i += 1
            v = 40 if self._shot_i % 2 else 200
            return np.full((1080, 1920, 3), v, dtype=np.uint8)

        class _Res:
            def __init__(self, ok: bool) -> None:
                self.is_success: bool = ok
                self.status: str = '成功' if ok else '未命中'

        def _click(screen: Any, screen_name: str, area: str,
                   **k: Any) -> _Res:
            if area == '按钮-商店' and self.match.phase == PHASE_PREP:
                self.match.open_shop()
                self._bench_pre_slots = dict(self._bench_identity())
                # 审计链窗口标记(不落项):开店后商店域金/席动走 sink、
                # 不经 prep 审计——窗口以单一边界项闭合(见收店臂),
                # 维持链相邻衔接的完整真值轴
                self._shop_window_pre = self._truth_digest()
                return _Res(True)
            if (area == '按钮-收起'
                    and self.match.phase == PHASE_PREP_SHOP_OPEN):
                self._flush_shop_window()
                self.match.close_shop()
                return _Res(True)
            return _Res(False)

        def _find(screen: Any, screen_name: str, area: str, **k: Any) -> _Res:
            if area == '按钮-收起':
                return _Res(self.match.phase == PHASE_PREP_SHOP_OPEN)
            if area in ('备战标识-购买经验', '按钮-出战'):
                return _Res(self.match.phase == PHASE_PREP)
            return _Res(False)

        def _cur_screen(screen: Any, screen_name_list: Any) -> str:
            if self.match.phase == PHASE_PREP:
                return '货币战争-备战'
            if self.match.phase == PHASE_PREP_SHOP_OPEN:
                return '货币战争-备战-开商店'
            return (screen_name_list[0] if screen_name_list else '')

        monkeypatch.setattr(prep, 'screenshot', _shot)
        monkeypatch.setattr(prep, 'park_cursor', lambda *a, **k: None)
        monkeypatch.setattr(prep, 'save_screenshot',
                            lambda *a, **k: '<stub-shot>')
        monkeypatch.setattr(prep, 'round_by_find_and_click_area', _click)
        monkeypatch.setattr(prep, 'round_by_find_area', _find)
        monkeypatch.setattr(prep, 'round_by_ocr', lambda *a, **k: _Res(False))
        monkeypatch.setattr(prep, 'check_and_update_current_screen',
                            _cur_screen)
        # 恢复原语的控制器原语桩(try_recovery 失败路径消费;MockController
        # 无 mouse_move——失败路径本身合法,桩只清噪声)
        monkeypatch.setattr(self.ctx.controller, 'mouse_move',
                            lambda *a, **k: None, raising=False)

    def _install_prep_patches(self, monkeypatch: Any) -> None:
        """模块级补桩(批 2 prep 相位;全部 monkeypatch,teardown 还原)。

        - 执行缝类级替换(机械半边 → prep_landing;wrapper 半边真码);
        - finalize/节点探针读屏喂真值(批 1 run_visit 同族,读屏桩只
          换来源不造值);
        - run_buy_waves 透传捕获(outcome 直传 harness,零语义变更)。
        """
        from fixtures.cw_fake_game.fake_ports import FakeCwObserver
        from sr_od.application.currency_war.obs import cw_observation as cwo
        from sr_od.application.currency_war.operations.cw_op import (
            cw_op_buy_cards as buy_mod,
        )
        from sr_od.application.currency_war.prep_actions import (
            PrepActionExecutor,
        )

        monkeypatch.setattr(PrepActionExecutor, '_execute_dispatch',
                            lambda ex, action: self.prep_landing(action))

        def _gold_truth(*a: Any, **k: Any) -> int:
            return self.match.state.gold

        monkeypatch.setattr(cwo, 'read_gold_settled', _gold_truth)
        monkeypatch.setattr(cwo, 'read_gold', _gold_truth)
        monkeypatch.setattr(
            cwo, 'read_game_state',
            lambda ctx, shot, phase=None:
                FakeCwObserver(self.match).observe_prep(ctx, phase).state)
        monkeypatch.setattr(cwo, 'read_node_sequence', lambda *a, **k: None)

        real_rbw = buy_mod.run_buy_waves

        def _rbw_capture(op: Any, match: Any, hp: Any, hr: Any,
                         ht: Any) -> Any:
            rr, outcome = real_rbw(op, match, hp, hr, ht)
            self.last_shop_outcome = outcome
            return rr, outcome

        monkeypatch.setattr(buy_mod, 'run_buy_waves', _rbw_capture)

    def _launch_host_stub(self) -> Any:
        """发射核宿主桩(消费面 = screenshot/备战双锚;测试与达标臂共用)。"""
        return _LaunchHostStub(self)

    def _try_armed_launch(self) -> tuple[bool, bool]:
        """达标臂真链(kernel armed 判据 → cw_loop.readiness_battle_launch
        → launch_prepared_battle 发射核;方案批 2「发射帧走真备战分支」)。

        armed 单一源 = kernel ``readiness_launch_decision``(与 engine_p1
        :1297 同参形态;质量闸 defer 短路 = cw_loop 消费序同款);发射核
        的 RunDeploy/StartBattle 经类级执行缝落假游戏。host op = 最小桩
        (发射核消费面 = screenshot/备战双锚,屏态复验在备战相位恒过)。
        返回 ``(evaluated, fired)``:evaluated = armed 判据核已消费
        (会话语据在位);fired = 真发射核已执行出战。
        """
        from sr_od.application.currency_war.kernel.cw_launch_admission import (
            readiness_launch_decision,
        )
        from sr_od.application.currency_war.kernel.cw_strategy_session import (
            strategy_state_of,
        )
        from sr_od.application.currency_war.operations import cw_loop
        from sr_od.application.currency_war.strategies.impl.mandate_v1.statefn.predicates import (
            line_members,
        )

        sess = self.cw_match.session
        st = getattr(sess, 'last_state', None)
        tc = getattr(strategy_state_of(sess), 'target_comp', None)
        if st is None or tc is None:
            return False, False
        core = readiness_launch_decision(st, tc, line_members=line_members)
        if not core.get('armed'):
            return True, False
        _q = core.get('quality')
        if _q is not None and _q.get('defer_by_quality'):
            return True, False   # 质量闸关闸帧(达标准入消费序同款)
        host = _LaunchHostStub(self)
        ok, _detail = cw_loop.readiness_battle_launch(host, self.ctx)
        return True, bool(ok)

    # ---- P1 段驱动 ----

    def run_p1(self, *, settle: bool = True) -> FakeP1Result:
        """驱动假 P1 全段:逐节点「收入 → 真 op 备战全链(部署/收球/
        开箱/装备/开店访问/出战)→ 结算 → 推进」(批 2 载体)。

        每步的编排 = harness 承担的环境事件序(真环境的回合推进由游戏
        本体承载,假环境由状态机规则 + 本编排表达);备战期本体 = 生产
        ``CwScreenPrep`` 生命周期全链(实机策略器决策 + 执行缝落假游戏,
        OpenShop 内联生产商店编排 = 批 1 已验证链)——批 1 的手工商店
        编排(收入→开店→run_buy_waves→收店)与部署围栏代理随批 2
        退役(方案 §6.2 批 2 行「围栏自动部署代理退役」)。

        ``settle=False`` 时跳过战斗结算(商店域单轮测试用)。
        """
        from fixtures.cw_fake_game import rules
        from sr_od.application.currency_war.telemetry import recorder as rec

        result = FakeP1Result(seed=self.seed)
        for r, node in enumerate(list(self.match.node_sequence), start=1):
            self._bench_pre_slots = dict(self._bench_identity())
            # 节点类型供给(决策前写,引擎同位 engine_p1.py:827;消费 =
            # 保连胜门/节点感知判据,见 __init__ 节点序列供给注)
            self.cw_match.session.node_type_current = node
            # tracked 真值播种(实机入口 heavy 读屏重建的同节拍对位,
            # 见方法注;先于备战访问,防首动作守卫误判)
            self._seed_tracked_from_truth()
            self.last_shop_outcome = None
            inc = self.match.apply_income()
            gold_after_income = self.match.state.gold
            # 奖励节点带球(环境事件,rng 归发放股;参数账见 rules)
            if node == 'reward':
                self.match.spawn_balls(rules.BALLS_PER_REWARD_NODE)
            # 备战期 = 真 op 全链(实机策略器决策;部署由策略 RunDeploy
            # 发射经执行缝落地——决策帧携带板满态的时序由真链自持)
            phase = self.run_prep_phase(self._monkeypatch)
            outcome = phase['outcome']
            if outcome is not None:
                gold_open = outcome.gold_open
                gold_close = self.match.state.gold
                counters = {
                    'total_buy': outcome.total_buy,
                    'total_level': outcome.total_level,
                    'total_refresh': outcome.total_refresh,
                    'total_sell': outcome.total_sell,
                    'total_sell_income': outcome.total_sell_income,
                    'spend_executed': outcome.spend_executed,
                }
            else:
                # 本备战期策略未开店(合法态):无商店窗口,金账连续
                gold_open = None
                gold_close = self.match.state.gold
                counters = dict.fromkeys(('total_buy', 'total_level', 'total_refresh', 'total_sell', 'total_sell_income', 'spend_executed'), 0)
            row: dict[str, Any] = {
                'node': node,
                'income': inc,
                'gold_after_income': gold_after_income,
                'gold_open': gold_open,
                'gold_close': gold_close,
                'deployed_up': sum(
                    1 for d in self.match.state.deployed if d is not None),
                'prep_visits': phase['visits'],
                'launched': phase['launched'] or phase['armed_launched'],
                **counters,
            }
            settlement = None
            if settle:
                settlement = self.match.settle_battle(node)
                rec.record_outcome(FakeRoundOutcome(
                    round_num=r, plane=self.match.state.plane,
                    node_type=node, hp_after=settlement.hp_after,
                    streak=self.match.state.streak))
            row['settlement'] = settlement
            result.rounds[r] = row
            if row['launched']:
                result.launched = True
            if phase['armed_evaluated']:
                result.armed_evaluated = True
            self.match.advance_node()
        # 局终收口(生产 schema;Δ池再生钩已在桩面截停)
        tel_state.record_run_summary(
            'completed', plane_reached=self.match.state.plane,
            rounds_survived=len(result.rounds),
            final_hp=int(self.match.state.hp or 0))
        return result

    def run_visit(self, monkeypatch: Any, tmp_path: Path) -> tuple[bool, str,
                                                                   dict[str, Any]]:
        """假局单轮的 visit_open_shop 驱动(落地审 M1 补锁;方案批 1 行
        「真 op(run_buy_waves 单动作循环/visit_open_shop)」的第二入口形)。

        驱动的生产链 = visit_open_shop 全函数:入口观察(端口)→
        run_buy_waves 单动作循环(端口)→ close_shop 点击壳(区域原语桩:
        点收起=命中、复验=已消失,壳逻辑真跑)→ finalize_buy_phase
        (三处 gold 读喂**假局真值**:金差值对拍在真值下恒过,冲突行
        缺失=如实无数据;读屏桩仅替换读图,不造值)→ 节点探针(零序列
        跳过)。事件序 = 0n 店已开形态:收入入账 → 开店 → visit 收店。

        返回 (ok, detail, info);info = 访问账(金/动作计数,断言用)。
        """
        from fixtures.cw_fake_game.fake_ports import FakeCwObserver
        from sr_od.application.currency_war.obs import cw_observation as cwo
        from sr_od.application.currency_war.operations.cw_screen.cw_screen_prep import (
            CwScreenPrep,
        )

        self._bench_pre_slots = dict(self._bench_identity())
        # tracked 真值播种(run_p1 同款,见方法注;开局 bench 非空后,
        # 冷建空 tracked 会被首动作守卫误判「识别幻影」)
        self._seed_tracked_from_truth()
        self.match.apply_income()
        self.match.open_shop()
        prep = CwScreenPrep(self.ctx)

        def _shot() -> np.ndarray:
            self._shot_i += 1
            v = 40 if self._shot_i % 2 else 200
            return np.full((1080, 1920, 3), v, dtype=np.uint8)

        monkeypatch.setattr(prep, 'screenshot', _shot)
        monkeypatch.setattr(prep, 'park_cursor', lambda *a, **k: None)
        monkeypatch.setattr(prep, 'save_screenshot',
                            lambda *a, **k: '<stub-shot>')

        # 关店壳区域原语桩:find_and_click=命中成功且**环境承接**(收起
        # 点击的假局规则效果 = close_shop 相位迁移,与 run_p1 编排同源);
        # 复验 find=按钮已消失(= 真转移信号,close_shop 的 fail-closed
        # 验证门以「消失」通过)
        class _Res:
            def __init__(self, ok: bool) -> None:
                self.is_success: bool = ok
                self.status: str = '成功' if ok else '未命中'

        def _click_collapse(*a: Any, **k: Any) -> _Res:
            self.match.close_shop()
            return _Res(True)

        monkeypatch.setattr(prep, 'round_by_find_and_click_area',
                            _click_collapse)
        monkeypatch.setattr(prep, 'round_by_find_area',
                            lambda *a, **k: _Res(False))
        # finalize 三处 gold 读(落地审 M1 点名):全部喂假局真值
        def _gold_truth(*a: Any, **k: Any) -> int:
            return self.match.state.gold

        monkeypatch.setattr(cwo, 'read_gold_settled', _gold_truth)
        monkeypatch.setattr(cwo, 'read_gold', _gold_truth)
        monkeypatch.setattr(
            cwo, 'read_game_state',
            lambda ctx, shot, phase=None:
                FakeCwObserver(self.match).observe_prep(ctx, phase).state)
        # 节点探针零序列(离线无模板装配;与既有 op 流测试同款)
        monkeypatch.setattr(cwo, 'read_node_sequence', lambda *a, **k: [])

        _gold_open = self.match.state.gold
        ok, detail = prep.visit_open_shop(self.match.state.hp, True, True)
        info: dict[str, Any] = {
            'gold_open': _gold_open,
            'gold_close': self.match.state.gold,
            'phase': self.match.phase,
        }
        return ok, detail, info


class _LaunchHostStub:
    """达标臂发射核的宿主桩(消费面最小:screenshot + 备战双锚 find_area)。

    生产宿主 = CwLoop 实例;发射核(readiness_battle_launch/
    launch_prepared_battle)对宿主的消费面 = 屏态复验两锚与
    ``PrepActionExecutor(op, ctx)`` 构造(执行器只消费 ctx + 类级执行缝
    已拦截机械半边)——桩满足消费面即真链可达,零点击真发。
    """

    def __init__(self, run: Any) -> None:
        self.ctx: Any = run.ctx
        self._run: Any = run
        self._shot_i: int = 0

    def screenshot(self) -> Any:
        self._shot_i += 1
        v = 40 if self._shot_i % 2 else 200
        return np.full((1080, 1920, 3), v, dtype=np.uint8)

    def round_by_find_area(self, screen: Any, screen_name: str, area: str,
                           **k: Any) -> Any:
        from fixtures.cw_fake_game.fake_match import PHASE_PREP

        class _Res:
            pass

        r = _Res()
        r.is_success = (self._run.match.phase == PHASE_PREP
                        and area in ('备战标识-购买经验', '按钮-出战'))
        r.status = '成功' if r.is_success else '未命中'
        return r


@contextlib.contextmanager
def fake_p1_run(ctx: SrTestContext, monkeypatch: Any, tmp_path: Path,
                seed: int, *,
                node_sequence: list[str] | None = None,
                initial_hp: int | None = None,
                initial_gold: int | None = None,
                archive_dir_name: str = 'fake_p1') -> Iterator[FakeP1Run]:
    """装配 + 驱动 + 全链 teardown 的假局上下文(测试唯一入口形)。

    装配序 = 方案 §3.3 装配纪律:构建 ctx 后、跑 op 前 install;
    档案根 = ``tmp_path/<archive_dir_name>/``(recorder 原生流 +
    op_journal.jsonl 同根——写端隔离,假局行零触 live 根)。
    teardown = 端口卸载 + run 态簇复位(``tel_state.reset_run_state``)
    + 三根槽复位(进程全局槽残留防线,teardown 必达,不依赖
    monkeypatch 覆盖所有槽)。
    """
    root = tmp_path / archive_dir_name
    run = FakeP1Run(ctx, seed, node_sequence=node_sequence,
                    initial_hp=initial_hp, initial_gold=initial_gold)
    run._monkeypatch = monkeypatch   # prep 相位补桩的延迟取用(批 2)
    # 根槽接通(生产形 API;先于任何 recorder 构造/写点)。三写根同点
    # 接指同一档案根(recorder/journal/决策帧;第三槽 = 三审二波 F2
    # 修复,漏接一件即部分隔离)。
    tel_state.set_recorder_replay_dir(root)
    op_journal.set_journal_dir(root)
    dfh.set_decision_frame_dir(root)
    install_game_ports(FakeCwObserver(run.match), FakeActionSink(run.match))
    try:
        run._install_stubs(monkeypatch)
        yield run
    finally:
        cw_game_ports.uninstall_game_ports()
        # run 态簇复位(出处:.debug/temp/currency_war/attacks/
        # three_review_20260908/三审报告-第二波.md F1,易失产物待 ADR
        # 回填;ensure 门语义见 ADR-0588)——局终 record_run_summary 裸写
        # _RUN_CLOSED=True 不在任何 monkeypatch 清单内,散点补桩随簇扩员
        # 会再漏,统一走 state 正规复位入口(teardown 必达档,同三根槽)。
        tel_state.reset_run_state()
        tel_state.set_recorder_replay_dir(None)
        op_journal.set_journal_dir(None)
        dfh.set_decision_frame_dir(None)
