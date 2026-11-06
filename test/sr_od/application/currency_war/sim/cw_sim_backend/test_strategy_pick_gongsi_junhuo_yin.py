"""sim 选卡落地随机简易装备全链锁(公司军火更新·银,镜像 src = kernel/
cw_gain_effects.py 泛化随机装备表 '公司军火更新·银' 行经获得链 + sim 选卡
分派;按被测方法拆目录规范落位——test_sim_backend.py 超线冻结禁追加,
新锁落本拆目录,harness 装配先例 = 同目录 test_strategy_pick_hp.py;
链形先例 = test_sim_backend.py 买彩票星徽行 sim 全链锁)。

测试面依据 = 迭代 2026-09-23-invest-effects-calc designs/
T-138-gongsi-junhuo-gengxin-yin.md(定稿)§4 锁 7:播种 offer 含本卡 →
落地 equips +1(状态副本里的值,名 ∈ 简易池);同 seed 同流键重放一致;
变异面 sim 零建模 = 变换族既定边界(sim 不反映每节点物品栏变异,
公司人才流动同判在码),不设断言(负向申报,notes 面)。

复用声明:引擎驱动助手 import 自 sim/test_sim_backend.py(已登记超限
拆分债文件,禁追加,只 import 复用不改)。
"""
from __future__ import annotations

from types import SimpleNamespace

from test.sr_od.application.currency_war.sim.test_sim_backend import (
    _SIG,
)

from sr_od.application.currency_war.kernel.cw_action_report import (
    report_action_pick_invest_strategy_param,
)
from sr_od.application.currency_war.sim.cw_sim_backend import (
    SCREEN_BRIEFING,
    SimBackend,
    install_backend,
    uninstall_backend,
)
from sr_od.application.currency_war.sim.cw_sim_run_config import RunConfig
from sr_od.application.currency_war.sim.cw_sim_streams import stream_rng

_STREAM_KEY = 'M11/pick/random-simple-equip-junhuo-yin'


def _backend(seed: int = 7) -> SimBackend:
    """构造 + 装配(调用方负责 uninstall;装配形态先例 =
    test_sim_backend._backend)。"""
    b = SimBackend(seed=seed, cfg=RunConfig(
        selected_difficulty='A8', enemy_difficulty=108))
    install_backend(b)
    return b


def test_pick_chain_random_simple_equip_grant() -> None:
    """获得链断言(公司军火更新·银,简易行):选本卡 → 简易池均匀采样
    1 件入栏(采样效果子链;rng 注入流键,sim 采样即状态副本里的值,零新增
    接入调用);同 seed 同流键重放 equips 逐位一致。"""
    from sr_od.application.currency_war.kernel.cw_gain_effects import (
        roll_random_equip,
    )
    from sr_od.application.currency_war.kernel.cw_investments import (
        equips_by_category,
    )

    def _run_once() -> tuple:
        b = _backend(7)
        try:
            b._handle_click_source(SCREEN_BRIEFING, '按钮-下一步')
            b._maybe_finish_wait()
            gs = b.gs
            before = list(gs.equips.value or [])
            pick = roll_random_equip(stream_rng(7, _STREAM_KEY), '简易')
            gs.write_logic(gs.invest_strategy_opts,
                           ['公司军火更新·银', '躺平', '淘金客'],
                           produced_by='Test', evidence='t:opts', sig=_SIG)
            out = report_action_pick_invest_strategy_param(
                gs, SimpleNamespace(norm_name='公司军火更新·银'), _SIG,
                rng=stream_rng(7, _STREAM_KEY))
            assert out.applied
            assert '公司军火更新·银' in gs.active_strategies.value
            assert pick in equips_by_category('简易'), '预验证:采样值 ∈ 池'
            assert list(gs.equips.value) == before + [pick], \
                f'equips 恰 +1 且名 = 流键采样值: {gs.equips.value} vs {pick}'
            return tuple(gs.equips.value)
        finally:
            uninstall_backend()

    assert _run_once() == _run_once(), '同 seed 重放确定性(equips 逐位同)'
