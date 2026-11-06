"""开源节流条件息顶满 sim 全链测试(镜像 src = sim/cw_sim_backend.py 的
_begin_node_window 载体消费 + apply_round_start_income floor 透传;新锁
落拆目录新文件,命名随 test_strategy_*_sim_chain 家族)。

测试面依据 = 迭代设计 designs/T-295-kaiyuan-jieru.md §4 锁 4 + REVIEW-
T295 §3.3 裁决点 1/2(条件金腿 = 利息分量顶满;tick 捕获→窗口消费):
- 上节点未花费 → 下窗收入息分量顶满至 resolved 帽 9(金 25 自然息 2
  显影)+ 载体消费清零 + prev_node_spent 滚回 False;
- **S2 回归红线用例**:上节点已花费(prev 直写 True 测试缝;置位通道
  本体 = 存款回报批四花费通道接入调用锁)→ 无顶满,息 = min(gold//10, 9)
  ——若 tick 闸内捕获被移到滚位后,捕获读恒 False → 载体 = 帽 → 本例
  息分量变 9 即红(kernel 侧同型序锁 =
  kernel/cw_game_state/test_interest_topup_capture.py);
- 未持卡局零漂移 = 现役收入用例全数零红申报(缺省 floor=0,零新增用例)。

路径选卡卫生:驱动途中逢 offer 一律定向落「淘金客」(无 burst/刷新
字段,防自动选卡污染息面断言;先例 =
test_strategy_pick_gudinglicai._drive_with_safe_picks)。复用声明:
引擎驱动助手 import 自 test_p3_win_terminal._drive_step(位面过渡屏在
其分派表内)与 sim/test_sim_backend._SIG 族(已登记超限拆分债文件,禁
追加,只 import 复用不改)。
"""
from __future__ import annotations

from types import SimpleNamespace

from test.sr_od.application.currency_war.sim.cw_sim_backend.test_p3_win_terminal import (
    _drive_step,
)
from test.sr_od.application.currency_war.sim.test_sim_backend import (
    _SIG,
)

from sr_od.application.currency_war.kernel.cw_action_report import (
    report_action_pick_invest_strategy_param,
)
from sr_od.application.currency_war.kernel.cw_effect_inventory import (
    CounterKey,
)
from sr_od.application.currency_war.kernel.cw_investments import (
    STRATEGY_EFFECTS,
)
from sr_od.application.currency_war.kernel.cw_world_decl import WorldDecl
from sr_od.application.currency_war.sim import cw_sim_ports
from sr_od.application.currency_war.sim.cw_sim_backend import (
    SCREEN_BRIEFING,
    SCREEN_INVEST_STRATEGY,
    SCREEN_PREP,
    SimBackend,
    install_backend,
    uninstall_backend,
)
from sr_od.application.currency_war.sim.cw_sim_run_config import RunConfig

_CARD = '开源节流'
# 填充卡前提申报(T-311-r1 裁决 a:只修注释、卡不换——换卡位移种子轨迹,
# 明令禁止):淘金客现役 xp_per_refresh=2(cw_investments.py 注册行),
# 刷新 XP 把结果写进状态副本的实现分支已接入调用(T-311);本卡作填充的安全性前提 = 本目录
# sim 链驱动器(_drive_step)商店屏一律直接关店、零付费刷新帧 → XP
# 分支零开火,落卡零扰目标断言;未来引入付费刷新驱动须先换无 XP 字段
# 填充卡或显式预算 XP 推进对。
_SAFE_FILLER = '淘金客'
_SAFE_OPTS = ['淘金客', '躺平', '买断制']
_SPEC_ID = STRATEGY_EFFECTS[_CARD].id


def _backend(seed: int = 37) -> SimBackend:
    """装配后端至 P1r1 备战屏(调用方负责 uninstall;装配形态先例 =
    test_strategy_pick_gudinglicai._backend,seed = 其对拍定向种子——
    全程可达,防途局 hp 归零中断驱动)。"""
    b = SimBackend(seed=seed, cfg=RunConfig(
        selected_difficulty='A8', enemy_difficulty=108))
    install_backend(b)
    b._handle_click_source(SCREEN_BRIEFING, '按钮-下一步')
    b._maybe_finish_wait()
    assert b.screen_identity() == SCREEN_PREP
    return b


def _pick(b: SimBackend, name: str, opts: list[str]) -> WorldDecl:
    """定向选卡落地(直写 opts 定卡 + 上报 + 声明喂入;先例 =
    test_strategy_pick_gudinglicai._pick)。"""
    gs = b.gs
    gs.write_logic(gs.invest_strategy_opts, opts,
                   produced_by='Test', evidence='t:opts', sig=_SIG)
    out = report_action_pick_invest_strategy_param(
        gs, SimpleNamespace(norm_name=name), _SIG, session=SimpleNamespace())
    assert out.applied
    cw_sim_ports.declare_world(out.world_decl)
    return out.world_decl


def _drive_with_safe_picks(b: SimBackend, pred, limit: int = 512) -> None:
    """步进驱动至谓词成立;途中逢策略 offer 定向落安全 filler,其余屏交
    _drive_step 分派;超限响错防死循环(先例 =
    test_strategy_pick_gudinglicai._drive_with_safe_picks)。"""
    for _ in range(limit):
        if pred():
            return
        if b.screen_identity() == SCREEN_INVEST_STRATEGY:
            _pick(b, _SAFE_FILLER, _SAFE_OPTS)
            continue
        _drive_step(b, 43)
    raise AssertionError('驱动步数超限,谓词未达成')


def _carrier(gs) -> int:
    return gs.effects.counter(_SPEC_ID, CounterKey.INTEREST_TOPUP)


def _drive_to_offer(b: SimBackend, plane: int, round_num: int) -> None:
    """驱动至指定位面的策略 offer 呈现(呈现一次性标志位置位;途中 offer 安全
    filler 化,先例同上)。"""

    def _at_offer() -> bool:
        node = b.gs.node.value
        return (b.screen_identity() == SCREEN_INVEST_STRATEGY
                and node is not None and node.plane == plane
                and node.round_num == round_num)
    _drive_with_safe_picks(b, _at_offer)


def test_unspent_prev_tops_interest_and_carrier_consumed() -> None:
    """上节点未花费 → 下窗息分量顶满 9(锁 4 主用例):金 25 种子压低
    自然息(min(2, 9)=2)使顶满显影;息累计账增量恰 = 9(收入应用单
    口 = record_interest_earned 计 row.interest,四分支同源);载体窗开
    消费清零 + prev 滚回 False。"""
    b = _backend()
    try:
        gs = b.gs
        _drive_to_offer(b, 1, 3)
        _pick(b, _CARD, [_CARD, '躺平', _SAFE_FILLER])
        gs.write_logic(gs.gold, 25, produced_by='Test', evidence='t:gold',
                       sig=_SIG)
        before = gs.effects.interest_earned
        # 拿卡窗后首个开窗即消费窗(谓词 = 息账首笔落账,一步一窗不跨档)
        _drive_with_safe_picks(b, lambda: gs.effects.interest_earned > before)
        assert gs.effects.interest_earned == before + 9, \
            (f'息分量顶满至 resolved 帽: '
             f'{before} -> {gs.effects.interest_earned}')
        assert _carrier(gs) == 0, '载体窗开消费清零'
        assert gs.prev_node_spent.value is False, '滚位照常'
    finally:
        uninstall_backend()


def test_spent_prev_no_topup_s2_redline() -> None:
    """上节点已花费 → 无顶满(锁 4 **S2 回归红线用例**):息 = 自然值
    min(25//10, 9)=2;tick 闸内捕获先于滚位的现值下,捕获读 True 载体 0
    ——若捕获被移到滚位后,读恒 False 载体 = 帽 → 本例息变 9 即红
    (防「tick 先滚位」回归;置位通道本体归存款回报批,直写测试缝)。"""
    b = _backend()
    try:
        gs = b.gs
        _drive_to_offer(b, 1, 3)
        _pick(b, _CARD, [_CARD, '躺平', _SAFE_FILLER])
        gs.write_logic(gs.gold, 25, produced_by='Test', evidence='t:gold',
                       sig=_SIG)
        gs.write_logic(gs.prev_node_spent, True,
                       produced_by='Test', evidence='t:spent', sig=_SIG)
        before = gs.effects.interest_earned
        _drive_with_safe_picks(b, lambda: gs.effects.interest_earned > before)
        assert gs.effects.interest_earned == before + 2, \
            (f'无顶满,息 = 自然值 2(顶满恒发回归即变 9): '
             f'{before} -> {gs.effects.interest_earned}')
        assert _carrier(gs) == 0, '已花费捕获置 0'
        assert gs.prev_node_spent.value is False, '滚位照常(捕获毕滚位)'
    finally:
        uninstall_backend()
