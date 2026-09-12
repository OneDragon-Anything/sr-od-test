"""投资环境经济估值锁 E1/E2(design.md §2.7 经济锁表)。

出处(持久索引):
- docs/develop/sr_od/application/currency_war/changes/2026-09-12-invest-env/design.md
  §2.2.2(EnvEconomyEffect schema)/§2.2.3(env_economy_value 价值函数)/
  §2.2.4(fail-closed 门,参数级定义)/§2.7(E1/E2 锁表行);
- ADR-0144 决策 3(六条防一次性错装点名);
- docs/develop/sr_od/application/currency_war/changes/2026-09-12-invest-env/
  details/env-value-models.md §2.2.2(基线取卡基数 K=3,效果原文序数)。

注入口径(design §2.7 E2 行「构造 = 注入 CI 含 0 的参数,不依赖落地序的
注册表现值」):位面到达参数一律 monkeypatch.setitem 注入
ENV_ECONOMY_ESTIMATES——3.3 数据批落表后本文件不改即绿(注入覆盖现值)。
"""
import pytest

from sr_od.application.currency_war.kernel import cw_investments as inv
from sr_od.application.currency_war.kernel.cw_board_state import (
    BoardState,
    Field,
    NodeKey,
)
from sr_od.application.currency_war.kernel.cw_env_economy import (
    ENV_ECONOMY_ESTIMATES,
    XP_GOLD_RATE,
    EconomyEstimate,
    env_economy_value,
)
from sr_od.application.currency_war.kernel.cw_investments import (
    ENV_ECONOMY,
    INVESTMENT_ENVS,
)


def _est(value: float, lo: float, hi: float) -> EconomyEstimate:
    """注入用估算参数(CI = [lo, hi];source/cutoff 为测试申报占位)。"""
    return EconomyEstimate(value=value, ci=(lo, hi),
                           source='test-inject', cutoff='1970-01-01')


def _bs(plane: int | None = None, round_num: int = 1, held: int = 0) -> BoardState:
    """合成决策帧(Field 帧替换构造;node None = 开局桩形,局首语义)。"""
    bs = BoardState(schema_version=1)
    if plane is not None:
        bs.node = Field(value=NodeKey(plane=plane, round_num=round_num))
    if held:
        bs.active_strategies = Field(value=['测试策略'] * held)
    return bs


def test_env_economy_whitelist_and_wiring() -> None:
    """ENV_ECONOMY 白名单结构 + economy 挂载(design §2.2.2;3.2 = A 类四条)。

    值域 = 效果原文直读的登记门:红 = 效果原文变(版本漂移)或建模错装,
    对账源 = plaza id(增发货币 103/蓝海 113/成功经验 138/策略大师 147,
    cw_invest_data.py 效果原文)。白名单制:表外环境 economy 恒 None
    (faction 型结构性无经济通道,design §2.2.1 注)。
    """
    assert set(ENV_ECONOMY) == {'增发货币', '蓝海', '成功经验', '策略大师'}
    assert ENV_ECONOMY['增发货币'].gold_per_plane_start == (6, 8, 12)
    assert ENV_ECONOMY['蓝海'].gold_instant == 6
    assert ENV_ECONOMY['成功经验'].xp_after_level == (8, 3, 12)
    assert ENV_ECONOMY['策略大师'].gold_per_strategy_coef == 2
    for _n, _eff in ENV_ECONOMY.items():
        assert INVESTMENT_ENVS[_n].economy is _eff
    assert INVESTMENT_ENVS['狼狩概念股'].economy is None
    assert INVESTMENT_ENVS['彩虹时代'].economy is None


def test_anti_misinstall_six_entries() -> None:
    """ADR-0144 决策 3 六条防一次性错装对账(构建闸 _validate_env_economy
    的同语义测试面;构建闸炸 import,本锁给可读的红)。

    六条点名环境(增发货币/成功经验/二手市场/长线利好/策略大师/劳务派遣
    合同)的效果全是分期/条件/触发形态:凡在表,禁装成 gold_instant 单通道;
    劳务派遣合同(出售/合成触发金)无对应通道字段,禁登记。
    """
    _six = ('增发货币', '成功经验', '二手市场', '长线利好', '策略大师', '劳务派遣合同')
    for _n in _six:
        _eff = ENV_ECONOMY.get(_n)
        if _eff is not None:
            assert _eff.gold_instant == 0, f'{_n} 被一次性错装'
    assert '劳务派遣合同' not in ENV_ECONOMY


def test_e1_instant_and_xp_channels() -> None:
    """E1:蓝海 6 / 成功经验 36(design §2.7 E1 行;零参数通道,精确)。

    期望值由注册表通道值 × XP_GOLD_RATE 现算(数值锁推导锚定);36 钉住
    折算率裁定 4(1:1 暂定)的现值。
    """
    _bs0 = _bs()
    assert env_economy_value('蓝海', _bs0) == (6.0, True)
    _xp = ENV_ECONOMY['成功经验'].xp_after_level
    assert _xp is not None
    _expect = _xp[1] * _xp[2] * XP_GOLD_RATE
    assert _expect == 36.0
    assert env_economy_value('成功经验', _bs0) == (_expect, True)


def test_e1_plane_start_full_horizon(monkeypatch: pytest.MonkeyPatch) -> None:
    """E1:增发货币全期期望(design §2.7 E1 行「注入到达参数」)。

    开局帧(node 缺读 = 局首语义):Σ = 6×1 + 8×P2 + 12×P3;期望值由
    注册表通道值 × 注入参数现算,26 钉住全达成锚点。
    """
    _p2, _p3 = _est(1.0, 0.9, 1.0), _est(1.0, 0.9, 1.0)
    monkeypatch.setitem(ENV_ECONOMY_ESTIMATES, 'plane_arrival_p2', _p2)
    monkeypatch.setitem(ENV_ECONOMY_ESTIMATES, 'plane_arrival_p3', _p3)
    _g = ENV_ECONOMY['增发货币'].gold_per_plane_start
    _expect = _g[0] * 1.0 + _g[1] * _p2.value + _g[2] * _p3.value
    assert _expect == 26.0
    _v, _ok = env_economy_value('增发货币', _bs())
    assert _v == pytest.approx(_expect)
    assert _ok is True


def test_e1_plane_start_remaining(monkeypatch: pytest.MonkeyPatch) -> None:
    """E1:剩余期望(剩余价值口径,design §2.2.3「局内重发环境 = 剩余期望」)。

    - P2 r1 帧:P2 开局发放可领(当前位面轮次 ≤ 1,权 1)+ P3 参数权;
    - P2 r3 帧:P2 开局已过 → 只剩 P3 参数项;既往位面发放恒不计。
    """
    _p3 = _est(0.9, 0.8, 1.0)
    monkeypatch.setitem(ENV_ECONOMY_ESTIMATES, 'plane_arrival_p3', _p3)
    _g = ENV_ECONOMY['增发货币'].gold_per_plane_start
    _v, _ok = env_economy_value('增发货币', _bs(2, 1))
    assert _v == pytest.approx(_g[1] * 1.0 + _g[2] * _p3.value)
    assert _ok is True
    _v, _ok = env_economy_value('增发货币', _bs(2, 3))
    assert _v == pytest.approx(_g[2] * _p3.value)
    assert _ok is True


def test_e1_strategy_master(monkeypatch: pytest.MonkeyPatch) -> None:
    """E1:策略大师按取卡结构(design §2.7 E1 行;Σ_k coef×(k−1)×P(k))。

    开局帧 held=0:剩余取卡序 k=1..3,位面权 = (1, 1, P2)(取卡结构表
    _STRATEGY_PICK_PLANES:开局/P1 中段/P2 前段,出处见模块头);held=2 后
    只剩 k=3(全部剩余期望参数依赖——E2 翻转构造的承重帧);held≥3 基线
    取卡取尽 → 剩余期望 0 → fail-closed(消费端退裸分,等价行为)。
    """
    _p2 = _est(0.9, 0.8, 1.0)
    monkeypatch.setitem(ENV_ECONOMY_ESTIMATES, 'plane_arrival_p2', _p2)
    _coef = ENV_ECONOMY['策略大师'].gold_per_strategy_coef
    _v, _ok = env_economy_value('策略大师', _bs())
    assert _v == pytest.approx(_coef * 1 * 1.0 + _coef * 2 * _p2.value)
    assert _ok is True
    _v, _ok = env_economy_value('策略大师', _bs(held=2))
    assert _v == pytest.approx(_coef * 2 * _p2.value)
    assert _ok is True
    assert env_economy_value('策略大师', _bs(held=3)) == (0.0, False)


def test_e2_unmapped_and_missing_params(monkeypatch: pytest.MonkeyPatch) -> None:
    """E2:未入模恒 (0, False);估算参数缺失 → resolved=False(design §2.7 E2)。

    零参数通道(蓝海/成功经验)不缺参、持续 resolved——对照锁。
    """
    monkeypatch.delitem(ENV_ECONOMY_ESTIMATES, 'plane_arrival_p2', raising=False)
    monkeypatch.delitem(ENV_ECONOMY_ESTIMATES, 'plane_arrival_p3', raising=False)
    assert env_economy_value('狼狩概念股', _bs()) == (0.0, False)
    assert env_economy_value('不存在环境名', _bs()) == (0.0, False)
    assert env_economy_value('增发货币', _bs()) == (0.0, False)
    assert env_economy_value('策略大师', _bs()) == (0.0, False)
    assert env_economy_value('蓝海', _bs()) == (6.0, True)
    assert env_economy_value('成功经验', _bs()) == (36.0, True)


def test_e2_ci_flip_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    """E2:CI 翻转 → resolved=False(design §2.7「注入 CI 含 0 的参数」)。

    承重帧 = 策略大师 held=2(唯一剩余取卡 k=3 在位面 2,剩余期望全部
    参数依赖):P2 CI 下端 0 → 端点重算 0 → 方向翻转 → fail-closed;
    正对照 = CI 下端 0.5(方向闭合)→ resolved。参数级门的结构语义
    (带参数无关分量的帧不会被单参数 0 端点翻转——方向被确定分量钉住)
    见 env_economy_value docstring,与 §2.2.4「金期望的 CI 含 0」口径一致。
    """
    monkeypatch.setitem(ENV_ECONOMY_ESTIMATES, 'plane_arrival_p2', _est(0.9, 0.0, 0.95))
    assert env_economy_value('策略大师', _bs(held=2)) == (0.0, False)
    monkeypatch.setitem(ENV_ECONOMY_ESTIMATES, 'plane_arrival_p2', _est(0.9, 0.5, 0.95))
    _coef = ENV_ECONOMY['策略大师'].gold_per_strategy_coef
    _v, _ok = env_economy_value('策略大师', _bs(held=2))
    assert _v == pytest.approx(_coef * 2 * 0.9)
    assert _ok is True


def test_bc_channel_stub_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    """B/C 通道在表而估值公式未落(3.3 数据批)→ fail-closed。

    依据 = landing §3.2「B/C 参数 3.3 落表前按 resolved=False 消化缺参」;
    构造 = 注入带 B 类字段的表条目(不依赖 3.3 落表现值)——禁静默零值
    当 resolved(消费端按无经济通道处理,退裸分)。
    """
    _eff = inv.EnvEconomyEffect(gold_after_refreshes=(20, 30))
    _env = inv.InvestmentEnv(name='测试B类环境', category='经济', effect='',
                             source='test', economy=_eff)
    monkeypatch.setitem(inv.ENV_ECONOMY, '测试B类环境', _eff)
    monkeypatch.setitem(inv.INVESTMENT_ENVS, '测试B类环境', _env)
    assert env_economy_value('测试B类环境', _bs()) == (0.0, False)
