"""假游戏状态机骨架(T-120 批 0;方案 §2.2 的 FakeMatch 单一对象)。

**骨架范围(批 1 补全)**:状态容器(真 GameState + 画面身份 + 浮层栈)
+ 动作转移唯一入口 ``apply``(直调 ``cw_state.simulate`` 单一源)+
战斗结算直调(coarse 主路径 + Δ池)+ 四股随机流与确定性契约。
收入/装备发放/位面继承的规则模块、真 op 跑通归批 1+(方案 §6.2)。

**单一源纪律(本文件的存在理由)**:动作转移**只经**
``cw_state.simulate`` 直调——假游戏不内联任何动作转移(sim-design §2.1
双源禁令在假游戏侧同样生效;方案 §2.2 商店动作结算行)。刷新重抽、
牌池 take/ret 属「规则外效应」,是假游戏规则层职责(RefreshShop 在
simulate 侧只扣金不模拟牌,``cw_state.simulate`` 的 RefreshShop 分支
注释在案)。

**确定性契约**:同 seed + 同环境指纹 → 逐位可复现(方案 §2.2 确定性行;
sim-testing「重放 = seed + 池指纹」契约的假游戏侧扩形)。随机流 = 主
种子派生四股(日程/抽店/战斗/发放),股间互不串扰——某域加消费不位移
他域的流位置。真值来源全部是 kernel/sim 真码直调,本文件零平行实现。

**Δ池源显式 snapshot**:本骨架固定 ``resolve_pool('snapshot')``(主仓
提交快照,零本地产物依赖)——不用 'auto'(读生产 replay 目录 = 测试
真实副作用,违反测试零副作用纪律);缺源大声报错纪律由 pool 自带。
方案出处 = `.debug/temp/currency_war/t120_sim_redesign/方案.md` §2.2
(**易失产物**,ADR 落点待 T-120 退役批分配,后续批回填指针)。
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any

from sr_od.application.currency_war.cw_game_ports import ExecResult
from sr_od.application.currency_war.kernel import cw_state
from sr_od.application.currency_war.kernel.cw_battle_calib import (
    _deployable_depth,
    _settle_rung,
    node_delta,
    sample_node_sequence,
)
from sr_od.application.currency_war.kernel.cw_coarse_battle import (
    sample_battle_delta,
)
from sr_od.application.currency_war.kernel.cw_opening_hp import (
    OPENING_HP_BASE,
)
from sr_od.application.currency_war.kernel.cw_state import (
    Action,
    GameState,
)
from sr_od.application.currency_war.sim.pool import (
    _Pool,
    live_delta_for,
    resolve_pool,
)

#: 假游戏规则层版本位。语义 = 方案 §2.2 LEVEL_CAP 裁决的申报载体:假游戏
#: 按游戏真值(lv10 禁购)建模,不继承 engine_p1 ``LEVEL_CAP=9`` sim-only
#: 冻结——lv10 真值封顶由 simulate 自带(cw_state.py:1512 ``s.level < 10``),
#: 本骨架直调即继承。环境指纹含本位,跨版本对照禁裸串比(与池指纹同纪律)。
FAKE_GAME_ENV_VERSION: int = 1

# ---- 画面身份词表(方案 §2.2:词表 = screen_info 画面档名,外循环
# ---- dispatch 消费同名;骨架只列核心推进档,浮层档随批 2/3 词汇扩展。
# ---- 单一源 = assets/game_data/screen_info/<screen_id>.yml 的 screen_name)----
PHASE_PREP: str = '货币战争-备战'
PHASE_PREP_SHOP_OPEN: str = '货币战争-备战-开商店'
PHASE_BATTLE: str = '货币战争-战斗'
PHASE_SETTLE: str = '货币战争-战斗结算'
PHASE_PLANE_TRANSITION: str = '货币战争-位面过渡'
PHASE_LOBBY: str = '货币战争-大厅'

#: 开局 hp 缺省(骨架便捷值)——单一源 = kernel/cw_opening_hp.
#: OPENING_HP_BASE(ADR-0559 初值表:A8/108 基础 82 零方差;import 非复写,
#: 初值表重校准自动跟随,落地审 L1 修后口径)。仅免「hp=None 无法结算」
#: 的样板,非环境保真申报面——开局词缀/难度对 hp 的影响归批 1 规则模块。
DEFAULT_OPENING_HP: int = OPENING_HP_BASE

#: 开局 xp 进度缺省:level 1 无门槛表键,回退缺省门槛 4(同 simulate 的
#: ``XP_TO_NEXT_LEVEL.get(level, 4)`` 回退口径,单一源 = cw_state)。
_DEFAULT_XP_NEED: int = 4


@dataclass
class OverlayFrame:
    """待处理浮层(kind + 选项载荷;方案 §2.2 浮层栈行)。

    ``kind`` = pick 族词表键(invest/supply/encounter/...);``payload``
    = 选项载荷(元素形状随 kind,同端口 ``overlay_options`` 的契约——
    不折叠结构)。
    """

    kind: str
    payload: list[Any] = field(default_factory=list)


@dataclass
class ObservationRecord:
    """一次观察调用的留痕(方案 §2.3 契约二则:读屏次数语义保留)。

    观察注入换掉的是读图,不是「观察」这个语义事件——读屏节奏类判读
    (如刷新终结→重观察结构)在假环境靠本留痕审计。
    """

    seq: int
    # [索引定义] 坐标系: observation_log 列表下标(1 起,append-only)
    #             取值时机: 生成期=执行期恒稳(只追加,不删改)
    method: str   # 端口方法名(screen_identity/observe_prep/...)
    arg: str | None   # 方法主参(observe_prep=阶段键 / overlay_options=kind)
    clock: int    # 留痕时点的逻辑时钟(FakeMatch.clock,语义事件序非真实时间)


@dataclass
class BattleSettlement:
    """一次节点结算的回执(骨架最小面)。

    ``delta`` 极性与产线一致 = hp 变化量(方案 §4-4:killed/胜负语义
    同产线——killed 判定读 ``hp_after <= 0``,streak/遥测行归批 1)。
    """

    node: str
    delta: int      # hp 变化量(采样原值,未含 hp 下钳)
    hp_after: int   # 钳制后 hp(≥0 = 假游戏死亡态)


class FakeMatch:
    """一局假游戏的状态机(方案 §2.2「单一对象 FakeMatch」)。

    状态槽:对局态 = 真 ``GameState``(零平行结构);画面身份 =
    ``phase``(screen_info 画面档名);节点日程 = ``node_sequence``
    (剧本注入或 ``sample_node_sequence`` 真码采样);牌池 = ``_Pool``
    真码;浮层栈 = ``overlay_stack``;随机流 = 主种子派生四股。
    """

    def __init__(self, seed: int, *,
                 node_sequence: list[str] | None = None,
                 initial_hp: int = DEFAULT_OPENING_HP) -> None:
        self.seed: int = seed
        # 随机流:主种子派生四股(getrandbits 派生,股间互不串扰——
        # 某域新增 rng 消费不位移他域流位置,重放对账的分流前提)
        _master = random.Random(seed)
        self._rng_schedule: random.Random = random.Random(_master.getrandbits(64))
        self._rng_draw: random.Random = random.Random(_master.getrandbits(64))
        self._rng_battle: random.Random = random.Random(_master.getrandbits(64))
        self._rng_grant: random.Random = random.Random(_master.getrandbits(64))
        # 节点日程:剧本注入(确定性测试)优先,否则真码采样
        self.node_sequence: list[str] = (
            list(node_sequence) if node_sequence is not None
            else sample_node_sequence(self._rng_schedule))
        self._node_idx: int = 0
        # Δ池:显式 snapshot 源(确定性 + 零本地产物依赖,见模块头注)
        self._delta_pool_map, self.delta_pool_fingerprint, _ = resolve_pool(
            'snapshot')
        self.shop_pool: _Pool = _Pool(self._rng_draw)
        self.overlay_stack: list[OverlayFrame] = []
        self.observation_log: list[ObservationRecord] = []
        self.clock: int = 0
        self.phase: str = PHASE_PREP
        self.state: GameState = GameState(
            plane=1,
            round_num=1,
            node_type=self.node_sequence[0],
            gold=0,
            level=1,
            xp_progress=(0, _DEFAULT_XP_NEED),
            hp=initial_hp,
        )

    # ---- 观察留痕(契约二则:读屏次数语义保留)----

    def record_observation(self, method: str, arg: str | None) -> None:
        """记录一次观察调用并推进逻辑时钟(端口假实现统一经此留痕)。"""
        self.clock += 1
        self.observation_log.append(ObservationRecord(
            seq=len(self.observation_log) + 1, method=method, arg=arg,
            clock=self.clock))

    # ---- 浮层栈 ----

    def push_overlay(self, kind: str, payload: list[Any]) -> None:
        """压栈一个待处理浮层(状态机按日程推进压栈,方案 §2.2)。"""
        self.overlay_stack.append(OverlayFrame(kind=kind,
                                               payload=list(payload)))

    def pop_overlay(self) -> OverlayFrame | None:
        """弹栈顶浮层(被测 op 消费后调用);空栈返回 None。"""
        return self.overlay_stack.pop() if self.overlay_stack else None

    def top_overlay(self, kind: str | None = None) -> OverlayFrame | None:
        """栈顶匹配浮层(``kind`` None = 不筛);无匹配返回 None。"""
        for frame in reversed(self.overlay_stack):
            if kind is None or frame.kind == kind:
                return frame
        return None

    # ---- 动作转移(唯一入口)----

    def apply(self, action: Action) -> ExecResult:
        """动作转移唯一入口(方案 §2.2「转移规则唯一入口 apply」)。

        动作语义 = ``cw_state.simulate`` 单一源直调(经模块属性访问,
        测试可 spy 断言接线);规则外效应(牌池 take/ret、刷新重抽)只在
        **applied** 时一次落定。判定语义(落地审 B1/B2 修后口径,出处 =
        cw_state v2 动作契约「拒绝记录进账本」冻结 invariant +
        ``_log_action`` 条目形 ``{'action','result',...}``):

        - **规则性拒绝**(SellBench/SellDeployed expect 守卫、DeployMove
          重名、SwapDeploy、CompTransaction 整体拒):simulate 返回
          「原状态 + rejected 日志条目」——状态整体不等**不能**当
          applied;判据 = 本次调用的日志增量含 ``result=='rejected'``
          (对全部 simulate 分支统一成立)。拒绝时不落任何规则外效应
          (不 ret/不 take/不重抽),账本条目照常入档(可见性 invariant)。
        - **no-op 路径**(空槽卖出/lv10 升级/满栏非合成拒买):无日志、
          状态原样副本 → 状态不等为 False → applied=False。
        - **合成买入**(满栏 merge-buy,ADR-0453):simulate 按 k 张下架 +
          k×cost 扣金;牌池 take 次数 = 店内下架数(普通买 1/合成买 k)。
        """
        self.clock += 1
        before = self.state
        log_base = len(before.action_log)
        after = cw_state.simulate(before, action)
        rejected = any(e.get('result') == 'rejected'
                       for e in after.action_log[log_base:])
        applied = (not rejected) and after != before
        # 拒绝条目也入档(账本可见性 invariant;拒绝态其余字段与原态零差)
        self.state = after
        if not applied:
            return ExecResult(applied=False, observed=after.copy())
        income: int | None = None
        verification: dict = {}
        if isinstance(action, cw_state.BuyCard):
            # 牌池规则外效应:下架几张取走几张(真机制;普通买 1、
            # 合成买 k——k 由 simulate 的下架数承载,不二算 merge_buy_k)
            taken = len(before.shop) - len(after.shop)
            for _ in range(max(1, taken)):
                self.shop_pool.take(action.card.name)
            verification['shop_slot'] = action.card.x
        elif isinstance(action, (cw_state.SellBench, cw_state.SellDeployed)):
            # 卖出回执:income = 金变化量(执行点真值,免复算 sell_refund
            # 链——金变化就是回金的落地面);卖出的副本回池(真机制),
            # 非牌池角色名(如开拓者)不回池
            income = after.gold - before.gold
            _sold = self._sold_char(before, action)
            if _sold is not None and _sold.char_id in self.shop_pool.copies:
                self.shop_pool.ret(_sold.char_id)
        elif isinstance(action, cw_state.RefreshShop):
            # 刷新重抽 = 假游戏规则层(simulate 只扣金不模拟牌);
            # probs 非空 = 轮岗翻倍后的概率表(ADR-0286,GameState 概率条
            # 真值同构),None = 基线 REFRESH_PROB
            self.state.shop = self.shop_pool.draw_shop(
                self.state.level, probs=self.state.refresh_probs)
            verification['dealt'] = len(self.state.shop)
        # DeployMove/SwapDeploy/CompTransaction/LevelUp:转移语义全部在
        # simulate 内,无规则外效应(装备发放归批 1 规则模块)
        return ExecResult(applied=True, income=income,
                          verification=verification,
                          observed=self.state.copy())

    @staticmethod
    def _sold_char(before: GameState,
                   action: Action) -> cw_state.BenchChar | None:
        """卖出动作的目标角色(投影前快照取,供回池;取不到返回 None)。"""
        if isinstance(action, cw_state.SellBench):
            if 0 <= action.bench_idx < len(before.bench):
                return before.bench[action.bench_idx]
            return None
        if isinstance(action, cw_state.SellDeployed):
            if 0 <= action.deployed_idx < len(before.deployed):
                return before.deployed[action.deployed_idx]
        return None

    # ---- 战斗结算(coarse 主路径 + Δ池直调)----

    def settle_battle(self, node: str | None = None) -> BattleSettlement:
        """节点战斗结算(方案 §2.2 战斗结算行;F7 主从口径:coarse 主路径)。

        - battle/encounter/boss → ``sample_battle_delta``(coarse 查表
          主路径,engine_p1.py:2022-2029 现行口径随迁);
        - reward/supply → Δ池直接采样(``live_delta_for``,桶键 =
          ``_deployable_depth`` 单一源);池缺回退 ``node_delta`` 单一源;
        - 采样键单一源直调(``_settle_rung``/``_deployable_depth``,
          cw_battle_calib;同 engine_p1 先例)。

        结算把 hpΔ 直接落到 ``state.hp``(下钳 0 = 死亡态;上界钳制/
        streak 结算观测回路归批 1 随遥测同构补全——骨架申报面)。
        """
        self.clock += 1
        _node = node or self.state.node_type or 'battle'
        st = self.state
        if _node in ('battle', 'encounter', 'boss'):
            delta = sample_battle_delta(
                _node, _settle_rung(st), st.hp if st.hp is not None else 0,
                self._rng_battle,
                difficulty=st.enemy_difficulty, plane=st.plane)
        elif _node in ('reward', 'supply'):
            _ld = live_delta_for(_node, _deployable_depth(st),
                                 self._rng_battle,
                                 pool_map=self._delta_pool_map,
                                 plane=st.plane)
            # 池缺 → node_delta 回退(reward/supply 桶缺回退 = 恒 +2 档,
            # EARLY_WIN_DELTA,单一源在 node_delta 内)
            delta = _ld if _ld is not None else node_delta(
                _node, st.round_num, st.round_num, self._rng_battle,
                plane=st.plane)
        else:
            delta = node_delta(_node, st.round_num, st.round_num,
                               self._rng_battle, plane=st.plane)
        hp_after = max(0, (st.hp if st.hp is not None else 0) + delta)
        st.hp = hp_after
        return BattleSettlement(node=_node, delta=delta, hp_after=hp_after)

    # ---- 日程推进(骨架最小实现)----

    def advance_node(self) -> str:
        """推进到下一节点(方案 §2.2 节点日程/位面推进行的骨架面)。

        最小实现:节点位前移 → 轮次/节点类型随日程 → 画面身份切备战。
        战斗等待/结算画面的编排细节归批 1,位面过渡后的 P2 进场继承归
        批 3(现只表态:日程耗尽 → 画面身份切位面过渡,节点位不回绕)。
        """
        self.clock += 1
        self._node_idx += 1
        if self._node_idx >= len(self.node_sequence):
            self.phase = PHASE_PLANE_TRANSITION
            return self.phase
        self.state.round_num = self._node_idx + 1
        self.state.node_type = self.node_sequence[self._node_idx]
        self.phase = PHASE_PREP
        return self.phase

    # ---- 环境指纹(重放三元之「环境指纹」)----

    def env_fingerprint(self) -> dict[str, str | int]:
        """环境指纹 = 规则层版本 + Δ池指纹(方案 §2.2 确定性行:同 seed +
        同环境指纹 → 逐位可复现;跨版本对照禁裸串比)。"""
        return {'env_version': FAKE_GAME_ENV_VERSION,
                'delta_pool': self.delta_pool_fingerprint}
