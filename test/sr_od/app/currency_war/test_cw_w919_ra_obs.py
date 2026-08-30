# type: ignore
"""w919 R-A 批1观测接线锁:ρ 实测(shop 快照富化)+ 方向重估决策面观测。

设计=.debug/temp/currency_war/w919_ra_obs/DESIGN.md(批1,零行为变化):
- ρ 实测口径(设计件 §2.1 辅通道):shop 单帧各体系成员在店件数;
  W 窗占比由读端聚合,采集点只记分子;
- 方向观测:候选(无滞回重派生 top-2)/滞回信号位/供给衰减坐标平铺,
  只观测不参与决策;P1 辖域;
- 采集失败静默跳过:遥测行缺失/观测源抛异常不得影响落盘主链(锁固化)。

锁结构/键面,不锁分布数值;全部落盘走 tmp_path(测试纪律:不写真实 .debug/)。
"""
import json
from pathlib import Path
from types import SimpleNamespace

from sr_od.application.currency_war.kernel.cw_intention import (
    IntentionState,
    _bond_members,
)
from sr_od.application.currency_war.kernel.cw_state import (
    BenchChar,
    GameState,
    ShopCard,
)
from sr_od.application.currency_war.telemetry import recorder
from sr_od.application.currency_war.telemetry import state as cw_telemetry
from sr_od.application.currency_war.telemetry.schema import (
    RHO_SHOP_OBS_FIELDS,
    RHO_SYSTEM_KEYS,
    rho_shop_obs,
)


def _setup_recorder(monkeypatch, tmp_path: Path, run_id: str = 'w919t') -> None:
    """recorder/run_id 指向 tmp_path(测试纪律;W603 同款隔离)。"""
    monkeypatch.setattr(cw_telemetry, '_RECORDER',
                        recorder.TelemetryRecorder(enabled=True, replay_dir=tmp_path))
    monkeypatch.setattr(cw_telemetry, '_CURRENT_RUN_ID', run_id)
    monkeypatch.setattr(cw_telemetry, '_CURRENT_DIFFICULTY', 'A8')
    monkeypatch.setattr(cw_telemetry, '_RUN_CLOSED', False)
    monkeypatch.setattr(cw_telemetry, '_defect_seen', {})
    monkeypatch.setattr(cw_telemetry, '_defect_seen_run', '')


def _rows(tmp_path: Path, name: str) -> list[dict]:
    p = tmp_path / name
    if not p.exists():
        return []
    return [json.loads(ln) for ln in
            p.read_text(encoding='utf-8').splitlines() if ln.strip()]


# ===== ① rho_shop_obs 纯函数(键面/计数口径)=====

def test_rho_shop_obs_keys_and_counts():
    """锁①a:键面=RHO_SYSTEM_KEYS(派生单一源);计数=成员名单 ∩ 在店名
    (与 _bond_members 现算对拍,不手抄真值);未识别卡只进分母。"""
    names = ['丹恒·饮月', '希儿', '未知卡??', '桑博']
    obs = rho_shop_obs([SimpleNamespace(name=n) for n in names], pair='仙舟+持续伤害')
    assert tuple(obs['systems'].keys()) == RHO_SYSTEM_KEYS
    for key, cnt in obs['systems'].items():
        members = _bond_members(key)
        assert cnt == sum(1 for n in names if n in members)
    assert obs['n_shop'] == 4
    assert obs['pair'] == '仙舟+持续伤害'
    assert set(obs.keys()) == set(RHO_SHOP_OBS_FIELDS)


def test_rho_shop_obs_dict_cards_and_empty():
    """锁①b:dict 形态卡(sim 账本 waves 卡)同口径;空店/None 店零计数不炸。"""
    obs = rho_shop_obs([{'name': '希儿'}])
    assert obs['systems']['希儿系'] == 1
    assert obs['n_shop'] == 1
    for junk in ([], None):
        o = rho_shop_obs(junk)
        assert o['n_shop'] == 0
        assert all(v == 0 for v in o['systems'].values())


# ===== ② shop_snapshots 行 rho_obs 行为锁 =====

def _shop_cards():
    return [ShopCard(x=1, faction='仙舟', cost=3, name='丹恒·饮月'),
            ShopCard(x=2, faction='持续伤害', cost=4, name='卡芙卡')]


def test_shop_snapshot_row_carries_rho_obs(tmp_path: Path, monkeypatch) -> None:
    """锁②a:生产 shop 快照行附 rho_obs,pair 自 session 意向方向取。"""
    _setup_recorder(monkeypatch, tmp_path)
    monkeypatch.setattr(cw_telemetry, '_CTX_MATCH_REF', [SimpleNamespace(
        session=SimpleNamespace(
            v3_intention=IntentionState(p1_pair=('仙舟', '持续伤害'))))])
    recorder.record_shop_snapshot('offer', _shop_cards(), 30, plane=1, round_num=2)
    r = _rows(tmp_path, 'shop_snapshots.jsonl')[0]
    rho = r['rho_obs']
    assert rho is not None and set(rho.keys()) == set(RHO_SHOP_OBS_FIELDS)
    assert rho['pair'] == '仙舟+持续伤害'
    assert rho['n_shop'] == 2
    assert set(rho['systems'].keys()) == set(RHO_SYSTEM_KEYS)
    # 行原有键不动(同 schema,supply 视图零改动)
    assert r['event'] == 'offer' and r['gold'] == 30


def test_shop_snapshot_rho_without_session(tmp_path: Path, monkeypatch) -> None:
    """锁②b:无 match 注册(离线/测试)→ pair='' 但 rho_obs 照记(计数面
    只依赖 shop 名单,不依赖 session)。"""
    _setup_recorder(monkeypatch, tmp_path)
    monkeypatch.setattr(cw_telemetry, '_CTX_MATCH_REF', [None])
    recorder.record_shop_snapshot('refresh', _shop_cards(), 12, plane=1, round_num=3)
    rho = _rows(tmp_path, 'shop_snapshots.jsonl')[0]['rho_obs']
    assert rho['pair'] == '' and rho['n_shop'] == 2


# ===== ③ decisions 行方向观测行为锁 =====

def test_decision_row_direction_fields(tmp_path: Path, monkeypatch) -> None:
    """锁③a:P1 ∧ 有意向 → 候选/滞回位/衰减坐标落行;滞回压着切换帧
    switch=True(supply′ 序仙舟领先但差 < θ,滞回按住当前线)。"""
    _setup_recorder(monkeypatch, tmp_path)
    # 滞回面只在方向机制开臂时生效(_pair_hysteresis 开关关恒原样返回)
    # → 本锁用 dataclasses.replace 开臂注册表替换模块缺省(冻结实例,
    # 不可原地改;观测经 _derive_p1_pair 缺省参读模块全局,调用时点取值)
    import dataclasses

    from sr_od.application.currency_war.kernel import cw_intention
    monkeypatch.setattr(
        cw_intention, 'DEFAULT_REGISTRY',
        dataclasses.replace(cw_intention.DEFAULT_REGISTRY,
                            realization_chain_enabled=True,
                            realization_direction_enabled=True))
    ist = IntentionState(p1_pair=('持续伤害', '列车同行'),
                         supply_drought={'仙舟': 1})
    monkeypatch.setattr(cw_telemetry, '_CTX_MATCH_REF', [SimpleNamespace(
        session=SimpleNamespace(v3_intention=ist))])
    # support′ 序:仙舟 0.667·γ≈0.63 > 列车 0.50 = 持续伤害 0.50;当前线
    # 首位(持续伤害)原列第 3,滞回把它顶进 top-2 → 产物集合改变
    # (raw={仙舟,列车} vs applied={持续伤害,仙舟})→ switch=True
    st = GameState(gold=30, hp=50, round_num=5, plane=1,
                   bench=[BenchChar(slot=0, char_id='丹恒·饮月', faction='仙舟'),
                          BenchChar(slot=1, char_id='藿藿', faction='仙舟'),
                          BenchChar(slot=2, char_id='卡芙卡', faction='持续伤害')])
    cw_telemetry.get_recorder().record_decision('w919a', 'A8', st, '', {}, {}, [])
    r = _rows(tmp_path, 'decisions.jsonl')[0]
    assert r['sess_dir_supply_drought'] == {'仙舟': 1}
    cand = r['sess_dir_candidate']
    # 候选 = 滞回前 support′ 序 top-2(仙舟/列车同行);标签按
    # _P1_PAIR_PREF 序规整(列车在前)
    assert isinstance(cand, str) \
        and set(cand.split('+')) == {'仙舟', '列车同行'}
    assert r['sess_dir_switch'] is True


def test_decision_row_direction_guards(tmp_path: Path, monkeypatch) -> None:
    """锁③b:无意向状态机 → 三字段 None;P2+ 不辖(None;方向=locked_comp
    已由 v3_intention 嵌套行携带)。"""
    _setup_recorder(monkeypatch, tmp_path)
    sess = SimpleNamespace(v3_intention=None)
    monkeypatch.setattr(cw_telemetry, '_CTX_MATCH_REF',
                        [SimpleNamespace(session=sess)])
    st = GameState(gold=30, hp=50, round_num=5, plane=1)
    cw_telemetry.get_recorder().record_decision('w919b', 'A8', st, '', {}, {}, [])
    r = _rows(tmp_path, 'decisions.jsonl')[0]
    assert r['sess_dir_candidate'] is None
    assert r['sess_dir_switch'] is None
    assert r['sess_dir_supply_drought'] is None

    monkeypatch.setattr(cw_telemetry, '_CTX_MATCH_REF', [SimpleNamespace(
        session=SimpleNamespace(v3_intention=IntentionState(
            p1_pair=('仙舟', '持续伤害'))))])
    st2 = GameState(gold=30, hp=50, round_num=5, plane=2)
    cw_telemetry.get_recorder().record_decision('w919b2', 'A8', st2, '', {}, {}, [])
    r2 = _rows(tmp_path, 'decisions.jsonl')[1]
    assert r2['sess_dir_candidate'] is None


def test_direction_obs_failure_silent_rows_intact(tmp_path: Path, monkeypatch) -> None:
    """锁③c(端到端守卫):观测源抛异常(意向属性炸)→ decisions 与
    shop_snapshots 行照写、观测字段 None——遥测缺失不得影响落盘主链。"""
    _setup_recorder(monkeypatch, tmp_path)

    class _Boom:
        @property
        def v3_intention(self):
            raise RuntimeError('观测源故障')

    monkeypatch.setattr(cw_telemetry, '_CTX_MATCH_REF',
                        [SimpleNamespace(session=_Boom())])
    rec = cw_telemetry.get_recorder()
    rec.record_decision('w919c', 'A8',
                        GameState(gold=30, hp=50, round_num=5, plane=1),
                        '', {}, {}, [])
    # ρ 计算面故障 → rho_obs=None,行照写(采集点静默跳过)
    def _boom_rho(shop, pair=''):
        raise RuntimeError('ρ 计算面故障')

    monkeypatch.setattr(recorder, 'rho_shop_obs', _boom_rho)
    recorder.record_shop_snapshot('offer', _shop_cards(), 30, plane=1, round_num=5)
    d = _rows(tmp_path, 'decisions.jsonl')[0]
    assert d['sess_dir_candidate'] is None
    s = _rows(tmp_path, 'shop_snapshots.jsonl')[0]
    assert s['rho_obs'] is None and s['event'] == 'offer'


# ===== ④ 采集点接线锁(断开即红)=====

def test_rho_obs_wiring_source_lock():
    """锁④a:rho_obs 写入点必须挂在 recorder.record_shop_snapshot 与
    sim 账本第三流两处生产端——删任一写入(断开采集点)即本锁红。"""
    import sr_od.application.currency_war.sim.runner as runner
    import sr_od.application.currency_war.telemetry.recorder as rec_mod
    src = Path(rec_mod.__file__).read_text(encoding='utf-8')
    assert 'rho_shop_obs(shop, pair=_pair)' in src
    assert '"rho_obs": _rho' in src
    rsrc = Path(runner.__file__).read_text(encoding='utf-8')
    assert "'rho_obs': _rho" in rsrc


def test_direction_obs_wiring_source_lock():
    """锁④b:方向观测写入点必须挂在 recorder(session 自取尾巴)——
    删 sess_dir_* 赋值或候选现算调用即本锁红。"""
    src = Path(recorder.__file__).read_text(encoding='utf-8')
    assert 'trace.sess_dir_candidate' in src
    assert 'trace.sess_dir_supply_drought' in src
    assert '_direction_obs_fields(state, _ist_live)' in src


def test_schema_declares_new_fields():
    """锁④c:schema 声明面——DecisionTrace 三字段在册且缺省 None
    (旧 schema 兼容);RHO 键面常量与 rho_shop_obs 输出一致。"""
    import dataclasses
    names = {f.name: f.default
             for f in dataclasses.fields(recorder.DecisionTrace)}
    for k in ('sess_dir_candidate', 'sess_dir_switch', 'sess_dir_supply_drought'):
        assert k in names and names[k] is None
    assert set(RHO_SHOP_OBS_FIELDS) == set(rho_shop_obs([]).keys())
