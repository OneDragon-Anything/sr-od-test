"""sim 选卡落地具名装备全链锁(小复制+,镜像 src = kernel/cw_gain_effects.py
的 ``PICK_INVEST_EFFECTS`` 直书登记行「小复制+」经获得链 + sim 选卡分派;
按被测方法拆目录规范落位——test_sim_backend.py 超线冻结禁追加,
新锁落本拆目录,链形先例 = test_sim_backend.py 无害垃圾行 sim 全链锁
(族内逐卡具名函数形),harness 装配先例 = 同目录
test_strategy_pick_gongsi_junhuo_yin.py)。

测试面依据 = 迭代 2026-09-23-invest-effects-calc designs/
T-169-xiaofuzhi-plus.md(定稿)§4 锁 7:播种 offer 含本卡 → 落地 equips
恰 +2 员工投影仪(世界真值,具名确定发放零采样);同 seed 同流重放一致;
金腿 13 金 = instant_gold 在册计分、发放写端 = 族级缺口(T-112,sim 金面
锁不住,维持观察——金腿零锁申报);bench/deployed 零变化(板面零建模 =
既有边界申报)。双持语义(姊妹小复制同局)= 表行驱动自然覆盖,零专锁。

复用声明:信号助手 import 自 sim/test_sim_backend.py(在册超限拆分债
文件,禁追加,只 import 复用不改)。
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

_CARD = '小复制+'
_ITEM = '员工投影仪'


def _backend(seed: int = 7) -> SimBackend:
    """构造 + 装配(调用方负责 uninstall;装配形态先例 =
    test_sim_backend._backend)。"""
    b = SimBackend(seed=seed, cfg=RunConfig(
        selected_difficulty='A8', enemy_difficulty=108))
    install_backend(b)
    return b


def test_pick_chain_named_equip_grant_xiaofuzhi_plus() -> None:
    """获得链断言(小复制+):选本卡 → equips 恰 +2 员工投影仪(具名
    确定发放,双端同链,sim 世界写入即容器写)+ bench/deployed 零变化
    (板面零建模);同 seed 重放 equips 逐位一致。"""
    def _run_once() -> tuple:
        b = _backend(7)
        try:
            b._handle_click_source(SCREEN_BRIEFING, '按钮-下一步')
            b._maybe_finish_wait()
            gs = b.gs
            equips_before = list(gs.equips.value or [])

            def _bench_ids() -> list:
                return [s.unit.char_id if s is not None and s.kind == 'unit'
                        else None for s in gs.bench.value.slots]

            bench_before = _bench_ids()
            deployed_before = gs.deployed.value
            gs.write_logic(gs.invest_strategy_opts,
                           [_CARD, '躺平', '淘金客'],
                           produced_by='Test', evidence='t:opts', sig=_SIG)
            out = report_action_pick_invest_strategy_param(
                gs, SimpleNamespace(norm_name=_CARD), _SIG,
                session=SimpleNamespace())
            assert out.applied
            assert _CARD in gs.active_strategies.value
            assert list(gs.equips.value) == equips_before + [_ITEM, _ITEM], \
                f'装备腿恰 2 件入栏(sim 世界真值): {gs.equips.value}'
            assert _bench_ids() == bench_before, 'bench 零变化(板面零建模)'
            assert gs.deployed.value == deployed_before, \
                'deployed 零变化(板面零建模)'
            return tuple(gs.equips.value)
        finally:
            uninstall_backend()

    assert _run_once() == _run_once(), '同 seed 重放确定性(equips 逐位同)'
