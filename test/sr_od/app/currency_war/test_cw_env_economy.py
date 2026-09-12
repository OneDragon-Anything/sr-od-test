"""投资环境经济估值锁 E1/E2 + 3.3 数据批增锁(design.md §2.7 经济锁表)。

出处(持久索引):
- docs/develop/sr_od/application/currency_war/changes/2026-09-12-invest-env/design.md
  §2.2.2(EnvEconomyEffect schema)/§2.2.3(env_economy_value 价值函数)/
  §2.2.4(估算注册表与 fail-closed 门,参数级定义)/§2.7(E1/E2 锁表行);
- ADR-0144 决策 3(六条防一次性错装点名);
- docs/develop/sr_od/application/currency_war/changes/2026-09-12-invest-env/
  details/env-value-models.md §2.2.2(基线取卡基数 K=3,效果原文序数);
- 同目录 details/data-batch-estimates.md(3.3 估算注册表数据批口径:样本/
  滤波/区间方法)。

注入口径(design §2.7 E2 行「构造 = 注入 CI 含 0 的参数,不依赖落地序的
注册表现值」):估算参数一律 monkeypatch.setitem 注入 ENV_ECONOMY_ESTIMATES
(注入覆盖现值);依赖注册表现参的锁(二手市场 resolved 行/落表结构行)
由注册表参数现算期望,不硬锁数据值,重采改参后照常可跑。
"""
import pytest

from sr_od.application.currency_war.kernel import cw_env_economy
from sr_od.application.currency_war.kernel import cw_investments as inv
from sr_od.application.currency_war.kernel.cw_env_economy import (
    ECON_VALUE_NORM,
    ENV_ECONOMY_ESTIMATES,
    ENV_ECONOMY_PENDING_MODELING,
    ENV_ECONOMY_PENDING_VERIFICATION,
    XP_GOLD_RATE,
    EconomyEstimate,
    env_economy_value,
)
from sr_od.application.currency_war.kernel.cw_game_state import (
    Field,
    GameState,
    NodeKey,
)
from sr_od.application.currency_war.kernel.cw_investments import (
    ENV_ECONOMY,
    INVESTMENT_ENVS,
)


def _est(value: float, lo: float, hi: float) -> EconomyEstimate:
    """注入用估算参数(CI = [lo, hi];source/cutoff 为测试申报占位)。"""
    return EconomyEstimate(value=value, ci=(lo, hi),
                           source='test-inject', cutoff='1970-01-01')


def _bs(plane: int | None = None, round_num: int = 1, held: int = 0) -> GameState:
    """合成决策帧(Field 帧替换构造;node None = 开局桩形,局首语义)。"""
    bs = GameState(schema_version=1)
    if plane is not None:
        bs.node = Field(value=NodeKey(plane=plane, round_num=round_num))
    if held:
        bs.active_strategies = Field(value=['测试策略'] * held)
    return bs


def test_env_economy_whitelist_and_wiring() -> None:
    """ENV_ECONOMY 白名单结构 + economy 挂载(design §2.2.2;A 类四条 + 3.3
    数据批补 B 类两条/C 类两条 = §2.2.1 通道分类全量)。

    值域 = 效果原文直读的登记门:红 = 效果原文变(版本漂移)或建模错装,
    对账源 = plaza id(增发货币 103/蓝海 113/成功经验 138/策略大师 147/
    长线利好 120/二手市场 106/经济过热 105/经济严重过热 119,cw_invest_data.py
    效果原文)。白名单制:表外环境 economy 恒 None(faction 型结构性无经济
    通道,design §2.2.1 注);轮岗/人才下沉无通道可装 → 「待建模」在册
    (test_pending_modeling_registered)。
    """
    assert set(ENV_ECONOMY) == {'增发货币', '蓝海', '成功经验', '策略大师',
                                '长线利好', '二手市场',
                                '经济过热', '经济严重过热'}
    assert ENV_ECONOMY['增发货币'].gold_per_plane_start == (6, 8, 12)
    assert ENV_ECONOMY['蓝海'].gold_instant == 6
    assert ENV_ECONOMY['成功经验'].xp_after_level == (8, 3, 12)
    assert ENV_ECONOMY['策略大师'].gold_per_strategy_coef == 2
    # B 类:游戏定义结构值(design §2.2.1 公式;付费/总分型经 refresh_cost_after
    # 在场判,阈值载体 = paid/total_refresh_count 计数字段)
    assert ENV_ECONOMY['长线利好'].gold_after_refreshes == (30, 20)
    assert ENV_ECONOMY['长线利好'].refresh_cost_after == (30, 1)
    assert ENV_ECONOMY['二手市场'].gold_after_refreshes == (20, 30)
    assert ENV_ECONOMY['二手市场'].refresh_cost_after is None
    # C 类:通道在场哨兵(真值+CI 在估算注册表,变体分键)
    assert ENV_ECONOMY['经济过热'].reward_node_bonus == 1.0
    assert ENV_ECONOMY['经济严重过热'].reward_node_bonus == 1.0
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


def test_bc_channel_missing_param_fail_closed(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """B/C 通道带字段而注册表缺对应参数 → fail-closed(design §2.2.4)。

    3.2 期「估值公式未落」桩位的后继口径:3.3 公式已落,缺参消化改由参数
    查询承载——构造 = 注入带 B 类字段但阈值未落参的表条目(阈值 50 无
    对应 refresh_*_ge50_p,不依赖哪些阈值已落),禁静默零值当 resolved
    (消费端按无经济通道处理,退裸分)。
    """
    _eff = inv.EnvEconomyEffect(gold_after_refreshes=(50, 30))
    _env = inv.InvestmentEnv(name='测试B类环境', category='经济', effect='',
                             source='test', economy=_eff)
    monkeypatch.setitem(inv.ENV_ECONOMY, '测试B类环境', _eff)
    monkeypatch.setitem(inv.INVESTMENT_ENVS, '测试B类环境', _env)
    assert env_economy_value('测试B类环境', _bs()) == (0.0, False)


def test_bc_estimates_registry_landed() -> None:
    """3.3 估算注册表落表结构锁(design §2.2.4;landing §3.3 判据①)。

    落参键 = 值/CI/来源/截止四元组齐备,CI 包住点值、概率参数 CI ⊆ [0,1];
    零样本/零有效估计的参数**不落**(禁拍值):长线利好条件后继期望
    (条件子样本 n=0)与 C 类扑满化增益(遥测无战利品独立字段)——缺位 =
    对应通道 fail-closed,补数据落参即自动恢复。值本身不硬锁(重采演化面,
    来源/截止随行申报),结构漂移先红。
    """
    _landed = ('plane_arrival_p2', 'plane_arrival_p3',
               'refresh_total_ge20_p', 'refresh_paid_ge30_p')
    for _k in _landed:
        _e = ENV_ECONOMY_ESTIMATES.get(_k)
        assert _e is not None, f'估算参数缺位:{_k}'
        assert _e.ci[0] <= _e.value <= _e.ci[1], _k
        assert _e.source and _e.cutoff, _k
    for _k in _landed:
        if _k.startswith(('plane_', 'refresh_')) and _k.endswith('_p'):
            assert ENV_ECONOMY_ESTIMATES[_k].ci[0] >= 0.0, _k
            assert ENV_ECONOMY_ESTIMATES[_k].ci[1] <= 1.0, _k
    for _k in ('refresh_paid_after30_e', 'reward_node_bonus_normal',
               'reward_node_bonus_super'):
        assert _k not in ENV_ECONOMY_ESTIMATES, f'零样本参数禁拍值落表:{_k}'


def test_e1_bc_market_resolved_from_registry() -> None:
    """E1 增补:二手市场按注册表现参 resolved(design §2.2.1 B 类公式)。

    开局帧:值 = P(达 20)× 30,期望值由注册表参数现算(不硬锁数据值);
    resolved 跟随 CI 下端方向(下端 > 0 才闭合)——两者都从注册表推导,
    重采改参后本锁照常可跑。
    """
    _p = ENV_ECONOMY_ESTIMATES['refresh_total_ge20_p']
    _v, _ok = env_economy_value('二手市场', _bs())
    assert _v == pytest.approx(_p.value * 30)
    assert _ok is (_p.ci[0] > 0.0)


def test_e1_bc_longterm_savings_formula(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """E1 增补:长线利好公式 P×[返金 + (基价−新价)×E(后继)](design §2.2.1)。

    注入全参数(不依赖落地序):项 1 = P×20;项 2 = P×(2−1)×E_after
    (基价 = cw_state.REFRESH_COST_BASE 游戏定义)。CI 两端 = 因子端点
    乘积(非负单调),逐位断言。
    """
    _p = _est(0.5, 0.4, 0.6)
    _e = _est(3.0, 2.0, 4.0)
    monkeypatch.setitem(ENV_ECONOMY_ESTIMATES, 'refresh_paid_ge30_p', _p)
    monkeypatch.setitem(ENV_ECONOMY_ESTIMATES, 'refresh_paid_after30_e', _e)
    _th, _refund = ENV_ECONOMY['长线利好'].gold_after_refreshes
    _new_cost = ENV_ECONOMY['长线利好'].refresh_cost_after[1]
    from sr_od.application.currency_war.kernel.cw_state import REFRESH_COST_BASE
    _save = REFRESH_COST_BASE - _new_cost
    assert _save == 1
    _v, _ok = env_economy_value('长线利好', _bs())
    assert _v == pytest.approx(_p.value * (_refund + _save * _e.value))
    assert _ok is True


def test_e2_bc_ci_flip_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    """E2 增补:B/C 通道 CI 翻转 fail-closed(design §2.7/§2.2.4 参数级门)。

    - B 类:二手市场注入 P(达20) CI 下端 0(端点重算 0,方向翻转)→
      (0, False);下端 > 0 → resolved 且值 = P×30。
    - C 类:经济过热注入增益 CI 含负端(端点重算 < 0)→ (0, False);
      正 CI → resolved,值 = 增益 × 剩余期望奖励节点数(槽位结构 × 到达权,
      到达参注入 0.9/0.8 端点可手算:开局视界 = 3×1 + 1×0.9 = 3.9)。
    """
    # B 类翻转/正对照
    monkeypatch.setitem(ENV_ECONOMY_ESTIMATES, 'refresh_total_ge20_p',
                        _est(0.2, 0.0, 0.3))
    assert env_economy_value('二手市场', _bs()) == (0.0, False)
    monkeypatch.setitem(ENV_ECONOMY_ESTIMATES, 'refresh_total_ge20_p',
                        _est(0.2, 0.05, 0.3))
    _v, _ok = env_economy_value('二手市场', _bs())
    assert _v == pytest.approx(0.2 * 30)
    assert _ok is True
    # C 类翻转/正对照(到达参数同步注入,视界因子确定)
    monkeypatch.setitem(ENV_ECONOMY_ESTIMATES, 'plane_arrival_p2',
                        _est(0.9, 0.8, 1.0))
    monkeypatch.setitem(ENV_ECONOMY_ESTIMATES, 'reward_node_bonus_normal',
                        _est(2.0, -0.5, 3.0))
    assert env_economy_value('经济过热', _bs()) == (0.0, False)
    monkeypatch.setitem(ENV_ECONOMY_ESTIMATES, 'reward_node_bonus_normal',
                        _est(2.0, 1.0, 3.0))
    _horizon = 3 * 1.0 + 0.9   # _REWARD_SLOTS:P1 三槽权 1 + P2 槽权 0.9
    _v, _ok = env_economy_value('经济过热', _bs())
    assert _v == pytest.approx(2.0 * _horizon)
    assert _ok is True
    # C 类超极变体分键独立(经济严重过热读 reward_node_bonus_super)
    monkeypatch.setitem(ENV_ECONOMY_ESTIMATES, 'reward_node_bonus_super',
                        _est(4.0, 2.0, 6.0))
    _v, _ok = env_economy_value('经济严重过热', _bs())
    assert _v == pytest.approx(4.0 * _horizon)
    assert _ok is True


def test_e2_bc_missing_params_fail_closed(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """E2 增补:B/C 通道缺参 fail-closed 的分型面(design §2.2.4)。

    - 长线利好:达阈概率在册但条件后继期望缺位(当前真实形态,n=0 不落)
      → 节省项缺参 → 整通道 fail-closed;
    - C 类:增益参数在册但位面到达缺参(视界因子不可算)→ fail-closed;
    - C 类哨兵条目漏变体映射(登记笔误形态)→ 参数查询恒 miss → fail-closed
      (映射漏登记的构建闸 = _validate_estimates_governance ①,另测)。
    """
    monkeypatch.setitem(ENV_ECONOMY_ESTIMATES, 'refresh_paid_ge30_p',
                        _est(0.5, 0.4, 0.6))
    monkeypatch.delitem(ENV_ECONOMY_ESTIMATES, 'refresh_paid_after30_e',
                        raising=False)
    assert env_economy_value('长线利好', _bs()) == (0.0, False)
    monkeypatch.setitem(ENV_ECONOMY_ESTIMATES, 'reward_node_bonus_normal',
                        _est(2.0, 1.0, 3.0))
    monkeypatch.delitem(ENV_ECONOMY_ESTIMATES, 'plane_arrival_p2',
                        raising=False)
    assert env_economy_value('经济过热', _bs()) == (0.0, False)
    _eff = inv.EnvEconomyEffect(reward_node_bonus=1.0)
    _env = inv.InvestmentEnv(name='测试C类无名变体', category='经济',
                             effect='', source='test', economy=_eff)
    monkeypatch.setitem(inv.ENV_ECONOMY, '测试C类无名变体', _eff)
    monkeypatch.setitem(inv.INVESTMENT_ENVS, '测试C类无名变体', _env)
    assert env_economy_value('测试C类无名变体', _bs()) == (0.0, False)


def test_pending_modeling_registered() -> None:
    """轮岗/人才下沉「待建模」显式在册(design §2.2.4;landing §3.3 判据②)。

    在册 = 区别于「漏登记」:有经济语义、v1 无参数化模型,消费端恒
    (0.0, False);不入 ENV_ECONOMY(无通道字段可装,双登记由构建闸拒绝)
    且必须真实存在于环境注册表(孤儿键构建闸拒绝)。
    """
    for _n in ('轮岗', '人才下沉'):
        assert _n in ENV_ECONOMY_PENDING_MODELING
        assert ENV_ECONOMY_PENDING_MODELING[_n]
        assert _n not in ENV_ECONOMY
        assert _n in INVESTMENT_ENVS
        assert env_economy_value(_n, _bs()) == (0.0, False)


def test_pending_verification_registered() -> None:
    """增发货币晶矿开启机制实采项在册(design §2.2.1 假设登记行的验证项;
    landing §3.3 范围行)。在册 = 假设可审:条目带处置承诺(证非自动 →
    bot 具备开矿动作前通道 fail-closed)。
    """
    assert '增发货币晶矿自动开启' in ENV_ECONOMY_PENDING_VERIFICATION
    assert ENV_ECONOMY_PENDING_VERIFICATION['增发货币晶矿自动开启']


def test_econ_value_norm_bounds(monkeypatch: pytest.MonkeyPatch) -> None:
    """ECON_VALUE_NORM 值域上界(design §2.3;landing §3.3 范围行)。

    全表开局期望 ≤ NORM(取整上界;域界非拍值——越界 = 注册表演化,
    构建闸炸出强制重新注册,tripwire 用压低上界验证炸出路径)。
    """
    _bs0 = _bs()
    for _n in ENV_ECONOMY:
        _v, _ok = env_economy_value(_n, _bs0)
        if _ok:
            assert _v <= ECON_VALUE_NORM, _n
    monkeypatch.setattr(cw_env_economy, 'ECON_VALUE_NORM', 0.5)
    with pytest.raises(ValueError):
        cw_env_economy._validate_estimates_governance()
