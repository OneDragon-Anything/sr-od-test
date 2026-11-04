"""sim 固定理财+ 位面段双腿 walk 测试(镜像 src = sim/cw_sim_backend.py 的
apply_strategy_plane_refire_xp 选卡拍补发腿 + _apply_strategy_plane_start_xp
位面首节点窗腿 + 呈现闩 + kernel 双桥经真实推进链;先例 =
test_strategy_pick_gudinglicai.py 姊妹形态参数化 +本卡)。

测试面依据 = 迭代设计 designs/T-183-gudinglicai-plus.md §4(锁 4 位面段
行为锁)+ 用户裁定书 T-182 节同判(2026-11-01 拍定:中途拿卡时当前已
开始的位面,其位面段奖励照常发放〔全额〕,后续位面照常——两卡一次拍定):
- (1,3) 拿卡局:拿卡拍 = 即时段(xp_instant +6/burst +3)+ 位面段补发
  (+6/+3,P1 已开始)双发各独立 evidence 笔;后续 (2,1)/(3,1) 位面
  开始照常(刷新支 kernel 桥 +3/位面、XP 支 sim 窗腿 +6/位面);
- (3,2) 拿卡局:拿卡前位面开始未持卡零发放(表外卡零写面),全程仅拿
  卡拍双发(补发恰覆盖 P3 段;其后无位面开始)。
- 重放防双发:呈现闩机制为姊妹同代码路径已锁(共享闩,同持多卡单腿独
  立),本文件不重复姊妹的重放 walk(两条测同一件事 = 冗余)。

路径选卡卫生:驱动途中逢 offer 一律定向落「淘金客」(无 burst/刷新字段
——防日程槽自动选卡采到 burst 卡污染 free_refresh 断言;首槽目标卡用例
另行定向)。复用声明:引擎驱动助手 import 自 test_p3_win_terminal.
_drive_step(位面过渡屏在其分派表内,达 P2/P3 必经)与
sim/test_sim_backend._SIG 族(在册超限拆分债文件,禁追加,只 import
复用不改;先例 = 姊妹文件同款复用)。
"""
from __future__ import annotations

from types import SimpleNamespace

from test.sr_od.application.currency_war.sim.cw_sim_backend.test_p3_win_terminal import (
    _drive_step,
)
from test.sr_od.application.currency_war.sim.test_sim_backend import (
    _SIG,
    _SIG_OBS,
)

from sr_od.application.currency_war.kernel.cw_action_report import (
    report_action_pick_invest_strategy_param,
)
from sr_od.application.currency_war.kernel.cw_economy import (
    XP_TO_NEXT_LEVEL,
    xp_apply_amount,
)
from sr_od.application.currency_war.kernel.cw_node_schedule import (
    node_sequence_of,
)
from sr_od.application.currency_war.kernel.cw_world_decl import WorldDecl
from sr_od.application.currency_war.sim import cw_sim_ports
from sr_od.application.currency_war.sim.cw_sim_backend import (
    NODE_XP_BY_TYPE,
    SCREEN_BRIEFING,
    SCREEN_INVEST_STRATEGY,
    SCREEN_PREP,
    SimBackend,
    install_backend,
    uninstall_backend,
)
from sr_od.application.currency_war.sim.cw_sim_run_config import RunConfig

_EV_REFIRE = 'sim:engine:xp:strategy_plane_refire:固定理财+'
# 填充卡前提申报(T-311-r1 裁决 a:只修注释、卡不换——换卡位移种子轨迹,
# 明令禁止):淘金客现役 xp_per_refresh=2(cw_investments.py 注册行),
# 刷新 XP 世界腿已接入调用(T-311)——「无刷新字段」旧注失实(burst/
# 位面字段仍为零);本卡作填充的安全性前提 = 本目录 sim 链驱动器
# (_drive_step)商店屏一律直接关店、零付费刷新帧 → XP 分支零开火,
# 落卡零扰目标断言;未来引入付费刷新驱动须先换无 XP 字段填充卡或显式
# 预算 XP 推进对。
_SAFE_FILLER = '淘金客'
_SAFE_OPTS = ['淘金客', '躺平', '买断制']


def _backend(seed: int = 37) -> SimBackend:
    """装配后端至 P1r1 备战屏(调用方负责 uninstall;装配形态先例 =
    姊妹文件同款;seed = 对拍定向种子——全程可达 P3,防途局 hp 归零
    中断驱动)。"""
    b = SimBackend(seed=seed, cfg=RunConfig(
        selected_difficulty='A8', enemy_difficulty=108))
    install_backend(b)
    b._handle_click_source(SCREEN_BRIEFING, '按钮-下一步')
    b._maybe_finish_wait()
    assert b.screen_identity() == SCREEN_PREP
    return b


def _pick(b: SimBackend, name: str, opts: list[str]) -> WorldDecl:
    """定向选卡落地(直写 opts 定卡 + 上报 + 声明喂入;先例 =
    姊妹文件同款)。"""
    gs = b.gs
    gs.write_logic(gs.invest_strategy_opts, opts,
                   produced_by='Test', evidence='t:opts', sig=_SIG)
    out = report_action_pick_invest_strategy_param(
        gs, SimpleNamespace(norm_name=name), _SIG, session=SimpleNamespace())
    assert out.applied
    cw_sim_ports.declare_world(out.world_decl)
    return out.world_decl


def _drive_with_safe_picks(b: SimBackend, pred, limit: int = 512) -> None:
    """步进驱动至谓词成立;途中逢策略 offer 定向落安全 filler(防自动
    选卡采到 burst 卡污染刷新面断言),其余屏交 _drive_step 分派。
    超限响错防死循环。"""
    for _ in range(limit):
        if pred():
            return
        if b.screen_identity() == SCREEN_INVEST_STRATEGY:
            _pick(b, _SAFE_FILLER, _SAFE_OPTS)
            continue
        _drive_step(b, 43)
    raise AssertionError('驱动步数超限,谓词未达成')


def _drive_to_offer(b: SimBackend, plane: int, round_num: int) -> None:
    """驱动至指定位面的策略 offer 呈现(呈现即置各落地腿闩;途中 offer
    安全 filler 化,保到达槽为首个未被消费的日程槽)。"""

    def _at_offer() -> bool:
        node = b.gs.node.value
        return (b.screen_identity() == SCREEN_INVEST_STRATEGY
                and node is not None and node.plane == plane
                and node.round_num == round_num)
    _drive_with_safe_picks(b, _at_offer)


def _drive_steps_tolerant(b: SimBackend, steps: int) -> None:
    """有界步进(局败容忍):驱动至多 steps 步,局败回大厅(seed 路径
    可能途局 hp 归零)即停——本腿断言面是「无后续位面开始零增发」,
    局败属合法终局非驱动故障。"""
    for _ in range(steps):
        if b.screen_identity() == '货币战争-大厅':
            return
        _drive_step(b, 43)


def _seed_level_xp(gs, level: int, cur: int) -> None:
    """等级/经验观察直种(先例 = 姊妹文件同款)。"""
    gs.observe(gs.level, level, sig=_SIG_OBS)
    gs.observe(gs.xp, (cur, XP_TO_NEXT_LEVEL[level]), sig=_SIG_OBS)


def test_pick_plus_p1r3_refire_then_later_planes_normal() -> None:
    """(1,3) 拿卡局:拿卡拍双发(即时段 + 补发段,P1 已开始)→
    (2,1)/(3,1) 位面开始照常(刷新 +3/位面、XP +6/位面)。"""
    b = _backend(seed=37)
    try:
        gs = b.gs
        _drive_to_offer(b, 1, 3)
        _seed_level_xp(gs, 5, 0)
        _pick(b, '固定理财+', ['固定理财+', '躺平', _SAFE_FILLER])
        # 拿卡拍:即时段 +6(xp_instant)与补发段 +6(xp_per_plane)两笔
        # 独立 evidence,后笔 = 补发腿;刷新 = burst 3 + 补发 3 = 6。
        assert gs.xp.value == (12, XP_TO_NEXT_LEVEL[5]), \
            f'拿卡拍 +12(6 即时 + 6 补发): {gs.xp.value}'
        assert gs.xp.evidence == _EV_REFIRE, \
            f'后笔 = 补发腿 evidence: {gs.xp.evidence}'
        assert gs.free_refresh_left.value == 6, 'burst 3 + 补发 3'
        # 后续位面开始照常:(1,3) 之后至 P1 末各节点推进 XP(出节点结算,
        # 序列表折叠)+ (2,1) 窗腿 +6。
        seq1 = node_sequence_of(1, gs.node_seq_by_plane.value)
        lvl, cur = 5, 12
        for kind in seq1[2:]:   # 出 (1,3)..(1,末) 各节点的结算经验
            lvl, cur = xp_apply_amount(lvl, cur, NODE_XP_BY_TYPE[kind])
        lvl2, cur2 = xp_apply_amount(lvl, cur, 6)
        _drive_with_safe_picks(
            b, lambda: gs.xp.evidence == 'sim:engine:xp:strategy_plane:p2')
        assert gs.xp.value == (cur2, XP_TO_NEXT_LEVEL[lvl2]), \
            f'(2,1) 窗腿 +6: {gs.xp.value}'
        assert gs.free_refresh_left.value == 9, '位面开始桥 +3'
        # (3,1) 照常:刷新第三笔 +3,XP 窗腿 evidence 换 p3(值面含中途
        # 节点/选卡干扰写,不作精确断言,evidence 转移即证)。
        _drive_with_safe_picks(
            b, lambda: gs.xp.evidence == 'sim:engine:xp:strategy_plane:p3')
        assert gs.free_refresh_left.value == 12, '第三笔位面开始 +3'
    finally:
        uninstall_backend()


def test_pick_plus_p3r2_late_pick_refire_only() -> None:
    """(3,2) 拿卡局:P3 开始在拿卡前(未持卡零发,表外卡零写面),其后
    无位面开始——全程仅拿卡拍双发,补发恰覆盖 P3 段;此前位面开始拍
    零增量。"""
    b = _backend(seed=37)
    try:
        gs = b.gs
        _drive_to_offer(b, 1, 3)
        _pick(b, _SAFE_FILLER, _SAFE_OPTS)
        # 首两段位面开始(P2/P3)未持目标卡:零刷新发放、零位面 XP 笔。
        _drive_with_safe_picks(
            b, lambda: gs.node.value is not None
            and (gs.node.value.plane, gs.node.value.round_num) >= (3, 1))
        assert gs.free_refresh_left.value is None, \
            '未持卡位面开始零刷新发放'
        assert not str(gs.xp.evidence or '').startswith(
            'sim:engine:xp:strategy_plane:'), '未持卡零位面 XP 笔'
        _drive_to_offer(b, 3, 2)
        _seed_level_xp(gs, 5, 0)
        _pick(b, '固定理财+', ['固定理财+', '躺平', _SAFE_FILLER])
        assert gs.xp.value == (12, XP_TO_NEXT_LEVEL[5]), \
            f'拿卡拍 +12: {gs.xp.value}'
        assert gs.xp.evidence == _EV_REFIRE
        assert gs.free_refresh_left.value == 6, 'burst 3 + 补发 3'
        # 其后无位面开始:继续驱动(局败容忍),刷新恒稳(无后续位面开始
        # 桥增发;XP evidence 被途经节点经验笔覆盖属预期,不断言其稳定)。
        _drive_steps_tolerant(b, 40)
        assert gs.free_refresh_left.value == 6, '无后续位面开始零增量'
    finally:
        uninstall_backend()
