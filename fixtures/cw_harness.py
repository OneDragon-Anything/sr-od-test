"""假局 harness(T-120 sim 重设计 批 1;方案 §7.1 测试仓「cw_harness」行)。

职责 = 把「真 op 跑在假环境」的装配一次性收口,测试只编排不碰装配细节:

- **端口安装**:构建 ``FakeMatch`` + ``FakeCwObserver``/``FakeActionSink``
  后 ``install_game_ports`` 显式接通(方案 §3.3 装配纪律;teardown 卸载);
- **档案根接通**:recorder 落盘根槽(``telemetry.state.
  set_recorder_replay_dir``,F4)+ journal 根槽(``op_journal.
  set_journal_dir``,T-129/T-130 混流注记的写端隔离)同点接指假局档案
  根(tmp_path 下)——假局遥测全链落生产 schema、零触真实 .debug 根;
- **真策略对局**:`MandateV1Strategy().create_session` 冷建(与生产
  run_buy_waves match=None 分支同源,ADR-0583 唯一冷建口)——被测对象
  含真策略器,决策非桩;
- **读图域桩**(识别/执行缺陷面结构性为零的申报面,方案 §4-6):截图
  旋转亮度帧、``new_bench_slots`` pixel-diff 读数按假局 bench 真值差分、
  决策帧留证目录重定向 tmp_path、stdlib sleep 桩(段顶 settle/刷新稳定
  门等待零信息量,先例 = test_cw_shop_refresh 同款);
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
from sr_od.application.currency_war.strategies.impl.cw_strategy import (
    CurrencyWarMatch,
)
from sr_od.application.currency_war.strategies.impl.mandate_v1.bridge import (
    MandateV1Strategy,
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
    """

    seed: int
    rounds: dict[int, dict[str, Any]] = field(default_factory=dict)

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
        # 被测对象含真策略器,方案 §2.1「策略器=被测对象」)
        config = self._config()
        _def = MandateV1Strategy()
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

    def _config(self) -> Any:
        from sr_od.application.currency_war.currency_war_config import (
            CurrencyWarConfig,
        )
        return CurrencyWarConfig(self.ctx.current_instance_idx)

    # ---- 桩面(读图域;方案 §4-6「识别/执行缺陷面结构性为零」)----

    def _install_stubs(self, monkeypatch: Any, tmp_path: Path) -> None:
        """读图域桩集合(全部 monkeypatch,teardown 自动还原)。"""
        from sr_od.application.currency_war.operations import (
            decision_frame_hooks as dfh,
        )
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
        # 决策帧留证目录 → tmp_path(假环境本就落结构化 JSON,见
        # decision_frame_hooks 端口分支;目录也不得触真实 .debug)
        monkeypatch.setattr(dfh, '_out_dir',
                            lambda run_id: tmp_path / 'dframes' / run_id)
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

    # ---- 部署围栏代理(保真校准面)----

    def _seed_tracked_from_truth(self) -> None:
        """tracked 账真值播种(实机「入口 heavy 读屏重建 tracked」的假环境
        对位,每轮开店前同节拍):实机每节点备战环入口重读重建跟踪账
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

    def _deploy_fence_pass(self) -> int:
        """备战期部署的环境承接代理(与引擎 sim 同款:围栏纯函数单一源)。

        **为什么环境层代跑部署**:实机部署 = 策略器在备战期发 RunDeploy
        (prep 域 op,方案 §6.2 归批 2 完整实体化);批 1 假环境只有商店域
        编排 → deployed 恒空,连锁 = 板深 0(Δ池最凶掉血桶,假局 hp 比
        实机崩得快的主因)+ M3 升级触发信号 arm1_existence(板满∧bench
        有候补)构造性不可达(策略器停升的「环境结构性无机会」面)。
        引擎对同一缺口的对位 = sim 层围栏代理(engine_p1 围栏趟注释
        「deployed 代理 = deploy_bench 真实围栏逻辑,与 CwOpDeploy op
        生产语义对齐」)——本代理与其同构:同一纯函数
        ``cw_deploy_logic.select_deployments`` 直调,零平行围栏语义。
        target 语境参数传空(意向驱动优先归批 2 部署域;围栏的 cap 填空/
        成对点火/板空保底主干不依赖 target)。

        调用时机 = 商店访问后、战斗结算前(本备战期部署当轮生效)。
        返回上场件数(对拍留证用)。
        """
        from sr_od.application.currency_war.data.cw_chars import CHARACTERS
        from sr_od.application.currency_war.kernel import cw_deploy_logic
        from sr_od.application.currency_war.kernel.cw_battle_calib import (
            _board_counts_of,
        )
        from sr_od.application.currency_war.kernel.cw_state import (
            deployed_place,
            iter_occupied_deployed,
        )
        st = self.match.state
        occ_idx = [i for i, b in enumerate(st.bench) if b is not None]
        if not occ_idx:
            return 0
        cap = st.max_units()
        if cap is None:
            return 0
        dep_occ = list(iter_occupied_deployed(st.deployed))
        dep_fac: dict[str, int] = {}
        for d in dep_occ:
            ch = CHARACTERS.get(d.char_id)
            if ch is not None and ch.factions:
                dep_fac[ch.factions[0]] = dep_fac.get(ch.factions[0], 0) + 1
        up_idx, _held = cw_deploy_logic.select_deployments(
            [b for b in st.bench if b is not None],
            deployed_cids={d.char_id for d in dep_occ if d.char_id},
            deployed_fac=dep_fac,
            board=dict(st.board or {}),
            cap=cap,
        )
        n_up = 0
        # up_idx 是紧缩占用序下标 → 回映射物理槽(引擎围栏趟同构;
        # ADR-0316 槽位表,ADR-0271 上阵即出 bench)
        for i in up_idx:
            if i < len(occ_idx):
                bc = st.bench[occ_idx[i]]
                if bc is not None:
                    deployed_place(st.deployed, bc)
                    st.bench[occ_idx[i]] = None
                    n_up += 1
        if n_up:
            st.board = _board_counts_of(st.deployed)
            # 跟踪账随动(实机对位 = 执行器 _track_move_deployed 的
            # tracked 同步;漏同步 = 期望态 vs tracked 双账守卫炸出
            # 「投影建模 bug」假象)——真值重播,与 sink 账本位随动同语义
            self._seed_tracked_from_truth()
        return n_up

    # ---- P1 段驱动 ----

    def run_p1(self, *, settle: bool = True) -> FakeP1Result:
        """驱动假 P1 全段:逐节点「收入 → 开店 → 真 op 商店访问 → 收店
        → 结算 → 推进」。

        每步的编排 = harness 承担的环境事件序(真环境的回合推进由游戏
        本体承载,假环境由状态机规则 + 本编排表达);商店访问本体 =
        生产 ``run_buy_waves`` 全链(入口观察经端口、决策真策略器、动作
        执行经 sink)。

        ``settle=False`` 时跳过战斗结算(商店域单轮测试用)。
        """
        from sr_od.application.currency_war.operations.cw_op.cw_op_buy_cards import (
            run_buy_waves,
        )
        from sr_od.application.currency_war.telemetry import recorder as rec

        result = FakeP1Result(seed=self.seed)
        for r, node in enumerate(list(self.match.node_sequence), start=1):
            self._bench_pre_slots = dict(self._bench_identity())
            # 节点类型供给(决策前写,引擎同位 engine_p1.py:827;消费 =
            # 保连胜门/节点感知判据,见 __init__ 节点序列供给注)
            self.cw_match.session.node_type_current = node
            # tracked 真值播种(实机入口 heavy 读屏重建的同节拍对位,
            # 见方法注;先于开店,防首动作守卫误判)
            self._seed_tracked_from_truth()
            inc = self.match.apply_income()
            gold_after_income = self.match.state.gold
            # 备战期部署趟(决策前;实机 actions 序 RunDeploy 先于
            # OpenShop——决策帧须携带板满态,M3 升级的 arm1 判据
            # 「板满∧bench 有候补」才可达)
            row_deployed_up = self._deploy_fence_pass()
            self.match.open_shop()
            _rr, outcome = run_buy_waves(self.op, self.cw_match,
                                         None, False, False)
            if _rr is not None or outcome is None:
                raise AssertionError(
                    f'假局 P1 r{r}({node})商店访问未收工:'
                    f'{getattr(_rr, "status", None)}')
            self.match.close_shop()
            row: dict[str, Any] = {
                'node': node,
                'income': inc,
                'gold_after_income': gold_after_income,
                'gold_open': outcome.gold_open,
                'gold_close': self.match.state.gold,
                'total_buy': outcome.total_buy,
                'total_level': outcome.total_level,
                'total_refresh': outcome.total_refresh,
                'total_sell': outcome.total_sell,
                'total_sell_income': outcome.total_sell_income,
                'spend_executed': outcome.spend_executed,
                'deployed_up': row_deployed_up,
            }
            settlement = None
            if settle:
                # 买后补部署趟(引擎围栏主趟在动作循环后的同位;当轮
                # 买的牌同备战期上板,战斗结算消费)
                row['deployed_up'] += self._deploy_fence_pass()
                settlement = self.match.settle_battle(node)
                rec.record_outcome(FakeRoundOutcome(
                    round_num=r, plane=self.match.state.plane,
                    node_type=node, hp_after=settlement.hp_after,
                    streak=self.match.state.streak))
            row['settlement'] = settlement
            result.rounds[r] = row
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
    + 两根槽复位(进程全局槽残留防线,teardown 必达,不依赖
    monkeypatch 覆盖所有槽)。
    """
    root = tmp_path / archive_dir_name
    run = FakeP1Run(ctx, seed, node_sequence=node_sequence,
                    initial_hp=initial_hp, initial_gold=initial_gold)
    # 根槽接通(生产形 API;先于任何 recorder 构造/写点)
    tel_state.set_recorder_replay_dir(root)
    op_journal.set_journal_dir(root)
    install_game_ports(FakeCwObserver(run.match), FakeActionSink(run.match))
    try:
        run._install_stubs(monkeypatch, tmp_path)
        yield run
    finally:
        cw_game_ports.uninstall_game_ports()
        # run 态簇复位(出处:.debug/temp/currency_war/attacks/
        # three_review_20260908/三审报告-第二波.md F1,易失产物待 ADR
        # 回填;ensure 门语义见 ADR-0588)——局终 record_run_summary 裸写
        # _RUN_CLOSED=True 不在任何 monkeypatch 清单内,散点补桩随簇扩员
        # 会再漏,统一走 state 正规复位入口(teardown 必达档,同两根槽)。
        tel_state.reset_run_state()
        tel_state.set_recorder_replay_dir(None)
        op_journal.set_journal_dir(None)
