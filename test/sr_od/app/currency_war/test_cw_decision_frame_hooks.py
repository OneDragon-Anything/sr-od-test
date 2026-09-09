"""决策帧截图留证钩子锁(decision_frame_hooks;硬砍批后残存)。

残存锁面:①滚动删除逻辑(每挂点保留最近 KEEP_PER_TAG 帧,旧的被删;PNG 与
观察证据 JSON 两分支都辖);②挂点调用存在(源码级:cw_op 两挂点内联
字面 + cw_loop 经 dispatch 包装统一落帧、调用点声明 frame_tag,
ADR-0584;烟雾容差背书见 test_hook_call_sites_exist docstring)。

砍除面墓碑(硬砍批):test_filename_format 删——文件名格式锁(ts 前缀可对齐
decisions 行 ts),纯命名格式约束;滚动删除语义由残存 2 测辖定(旧文件构造
即依赖 ts 字典序=时间序,格式破坏会连带滚动测试红)。
"""
import numpy as np
from pathlib import Path
import pytest

from sr_od.application.currency_war.operations import decision_frame_hooks as dfh


class _FakeOp:
    def screenshot(self):
        return np.zeros((4, 4, 3), dtype=np.uint8)


@pytest.fixture
def frame_env(tmp_path, monkeypatch):
    """落盘重定向到 tmp_path + 固定 run_id(测试零真实副作用,不写真实 .debug/)。"""
    root = tmp_path
    monkeypatch.setattr(dfh, 'get_project_root', lambda: root)
    import sr_od.application.currency_war.telemetry.state as tel_state
    monkeypatch.setattr(tel_state, 'current_run_id', lambda: 'run_t')
    return root / '.debug' / 'temp' / 'currency_war' / 'decision_frames' / 'run_t'


def _img() -> np.ndarray:
    return np.zeros((4, 4, 3), dtype=np.uint8)


def test_rolling_delete_keeps_recent(frame_env):
    """锁滚动删除:同 tag 超 KEEP_PER_TAG 帧后,最旧的被删、保留最近 N 帧。"""
    # 先铺 KEEP_PER_TAG + 5 个旧文件(文件名 ts 递增保字典序=时间序)
    for i in range(dfh.KEEP_PER_TAG + 5):
        name = f'20260101_0000{i // 10:02d}_{i % 10:03d}_deploy.png'
        frame_env.mkdir(parents=True, exist_ok=True)
        (frame_env / name).write_bytes(b'old')
    fn = dfh.save_decision_frame(_FakeOp(), 'deploy', _img())
    assert fn is not None
    mine = sorted(frame_env.glob('*_deploy.png'))
    assert len(mine) == dfh.KEEP_PER_TAG
    # 最旧的 5 个被删;新写入的帧在(最近一帧保留)
    assert (frame_env / fn) in mine
    assert not (frame_env / '20260101_000000_000_deploy.png').exists()
    # 不同 tag 不被误删(滚动按 tag 维度隔离)
    other = frame_env / '20260101_000000_000_shop_entry.png'
    other.write_bytes(b'other-tag')
    dfh.save_decision_frame(_FakeOp(), 'deploy', _img())
    assert other.is_file()


def test_json_evidence_rolling_prune(tmp_path, monkeypatch):
    """观察证据 JSON 分支按 tag 滚动治理(_prune_old 的 suffix 路由)。

    独立失败模式:丢 suffix='.json' 实参 → PNG 删式(`_<tag>.png`)匹配
    不到 .json,假局长局/批量驱动下证据无限累积——PNG 桶滚动锁(上条)
    不辖 JSON 分支;分支语义见 decision_frame_hooks.save_decision_frame
    docstring「留证面改形」。槽+端口装配 = JSON 分支的运行前提(未接槽
    走拒写守卫),teardown 复位槽(进程全局,测试纪律 4)。
    """
    from sr_od.application.currency_war import cw_game_ports
    from sr_od.application.currency_war.telemetry import state as tel_state

    class _Src:
        def evidence_snapshot(self, tag):
            return {'probe': tag}

    class _Op:
        def screenshot(self):
            return None

    monkeypatch.setattr(dfh, 'get_project_root', lambda: tmp_path / 'prod')
    monkeypatch.setattr(tel_state, 'current_run_id', lambda: 'run_jp')
    monkeypatch.setattr(cw_game_ports, 'observation_source', lambda: _Src())
    dfh.set_decision_frame_dir(tmp_path / 'archive')
    try:
        out = tmp_path / 'archive' / 'decision_frames' / 'run_jp'
        # 先铺 KEEP_PER_TAG + 3 个旧 json(文件名 ts 递增保字典序=时间序)
        out.mkdir(parents=True, exist_ok=True)
        for i in range(dfh.KEEP_PER_TAG + 3):
            name = f'20260101_0000{i // 10:02d}_{i % 10:03d}_probe.json'
            (out / name).write_text('{}', encoding='utf-8')
        fn = dfh.save_decision_frame(_Op(), 'probe')
        assert fn is not None and fn.endswith('.json')
        mine = sorted(out.glob('*_probe.json'))
        assert len(mine) == dfh.KEEP_PER_TAG
        assert (out / fn) in mine
        # 最旧的被删(含新帧共 44 → 保留最近 40)
        assert not (out / '20260101_000000_000_probe.json').exists()
    finally:
        dfh.set_decision_frame_dir(None)


def test_hook_call_sites_exist():
    """锁挂点存在(源码级;ADR-0584 改写为 dispatch 包装形)。

    锁语义重推(T-121 方案审 N2,按锁的存在性纪律):原锁钉「各分支体内联
    save_decision_frame 字面调用形」;包装上收后挂点单一化,新语义 =
    「①包装定义内统一落帧 + ②各调用点声明 frame_tag 实参」——红时登记的
    语义 = 分发点丢了留证帧声明(挂点存在性不变)。
    烟雾容差背书(纪律 8「防证据链静默脱落」):留证钩子 best-effort
    (落盘失败仅 log.warning,生产零报错),挂点静默脱落时证据停止累积
    且不可发现——失守事故本体 = P35 局复盘「OCR 文本与牌面解析对不上」
    无画面实锤(decision_frame_hooks 模块头「层次定位」背景),本锁是
    挂点在场的唯一会红载体。
    """
    src_root = Path(__file__).parents[5] / 'src' / 'sr_od' / 'application' \
        / 'currency_war'
    buy = (src_root / 'operations' / 'cw_op' / 'cw_op_buy_cards.py').read_text(
        encoding='utf-8')
    deploy = (src_root / 'operations' / 'cw_op' / 'cw_op_deploy.py').read_text(
        encoding='utf-8')
    loop = (src_root / 'operations' / 'cw_loop.py').read_text(encoding='utf-8')
    # 挂点 1/2:商店入口观察(每段一帧;刷新重观察同点覆盖)
    assert "save_decision_frame(op, 'shop_entry'" in buy
    # 挂点 3:部署决策帧
    assert "save_decision_frame(self, 'deploy'" in deploy
    # 挂点 4:分发包装统一落帧(_dispatch_screen_op 定义内唯一字面形挂点)
    assert 'save_decision_frame(self, frame_tag' in loop
    # 抽样调用点 frame_tag 实参字面存在(五 tag:决策 op ×3 + 0n/0j;
    # 原「内联 save_decision_frame(self, '<tag>'」形断言随包装上收改写)
    for tag in ('overlay_partner', 'overlay_invest_strategy', 'overlay_shop_open',
                'overlay_wish_trial', 'overlay_frontless'):
        assert f"frame_tag='{tag}'" in loop, tag
    # 计数断言 = 包装调用计数(定稿覆盖面实测 34 = 33 调用点 + 包装定义 1:
    # 决策 op 13 + 0n/0j/0p/0q/0r/0s×2/1 备战/战斗窗/3c + 推进族 10;
    # 下限 30 容纳合理增删,批量移除分发点即红)
    n_dispatch = loop.count('_dispatch_screen_op(')
    assert n_dispatch >= 30, n_dispatch
