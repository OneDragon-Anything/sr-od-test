"""合成特效帧态门 + cap 域外双帧一致采信(ADR-0420 抽样批3)。

锁面:
1. 帧态门两签名(星爆粒子/满席横幅)合成图正负样本——阈值不贴边;
2. reconcile 采新确认前的门拦截(保旧+防抖冻结)与门后干净帧仍可确认;
3. 静态口径锁(reconcile 引用门函数);
4. cap 域外双帧一致采信/超绝对上界拒/cap<level 恒拒(在 ADR-0286 接线文件)。
"""
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np

_REPO = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(_REPO / 'src'))
sys.path.insert(0, str(_REPO / 'sr-od-test'))

from sr_od.application.currency_war.kernel.cw_reconcile import (  # noqa: E402
    reconcile_tracking,
)
from sr_od.application.currency_war.obs.cw_identity_obs import (  # noqa: E402
    is_merge_effect_frame,
)


def _banner_frame() -> np.ndarray:
    """合成拖拽过渡帧:满席警告横幅带(深红,R 主导)——签名②正样本。"""
    img = np.zeros((1080, 1920, 3), dtype=np.uint8)
    img[515:555, 470:1450] = (160, 30, 40)   # RGB:R−max(G,B)=120>40
    return img


def _burst_frame() -> np.ndarray:
    """合成星爆帧:前排带 4 个金色四角星爆点(每个 ~80px)——签名①正样本。"""
    img = np.zeros((1080, 1920, 3), dtype=np.uint8)
    for cx in (700, 900, 1100, 1300):
        img[500:505, cx - 8:cx + 8] = (255, 215, 0)   # RGB 纯金:H≈25/S=255/V=255
    return img


def test_gate_banner_signature() -> None:
    """签名②:满席横幅帧 → True;空帧/None → False(离线不拦)。"""
    assert is_merge_effect_frame(_banner_frame()) is True
    assert is_merge_effect_frame(np.zeros((1080, 1920, 3), dtype=np.uint8)) is False
    assert is_merge_effect_frame(None) is False


def test_gate_burst_signature() -> None:
    """签名①:星爆粒子帧 → True;仅 2 个粒子(阈 3 之下)→ False。"""
    assert is_merge_effect_frame(_burst_frame()) is True
    img = np.zeros((1080, 1920, 3), dtype=np.uint8)
    for cx in (700, 900):
        img[500:505, cx - 8:cx + 8] = (255, 215, 0)
    assert is_merge_effect_frame(img) is False


def _sess() -> SimpleNamespace:
    return SimpleNamespace(
        tracked_bench_chars=[SimpleNamespace(char_id='万敌', star=2, slot=1,
                                             position_pref='back')],
        tracked_deployed=[],
        star_regression_count={}, star_pending_regression={})


def _read(star: int) -> list[SimpleNamespace]:
    return [SimpleNamespace(char_id='万敌', star=star, slot=1, position_pref='back')]


def test_gate_blocks_confirm_and_freezes_pending(monkeypatch) -> None:
    """特效帧上的第 2 次回退:**保旧 + 防抖冻结**(pending 不推进、不计数、
    不采新)——star 层 2/2 采新帧全错(动画窗 ≥2 帧骗过连续确认)的
    直接回归锁。随后干净帧(screen=None)同回退 → 仍走确认采新(门冻结非清零)。

    分包期5 补遗(§3.3-⑥ SIFT 上移)后门实现经注入槽进 kernel:
    测试同生产装配点同语义,显式注入真 ``is_merge_effect_frame``。"""
    import sr_od.application.currency_war.kernel.cw_reconcile as cr
    monkeypatch.setattr(cr, '_conflict', lambda *a, **k: None)
    monkeypatch.setattr(cr, '_IS_MERGE_EFFECT_FRAME', is_merge_effect_frame)
    s = _sess()
    s.star_pending_regression = {'万敌': 1}   # 上帧已防抖挂起
    reconcile_tracking(s, _read(1), [], _burst_frame(), source='t', ctx=None)
    assert s.tracked_bench_chars[0].star == 2, '特效帧读数不进 tracking(保旧)'
    assert s.star_pending_regression.get('万敌') == 1, '防抖冻结(不推进到确认)'
    assert not s.star_regression_count.get('万敌'), '特效帧不计数'
    # 门后干净帧:同回退仍确认采新(冻结 ≠ 清零)
    reconcile_tracking(s, _read(1), [], None, source='t', ctx=None)
    assert s.tracked_bench_chars[0].star == 1, '干净帧确认采新'
    assert s.star_pending_regression.get('万敌') == 1, '确认后防抖仍挂起(既有语义)'

    s2 = _sess()
    s2.star_pending_regression = {'万敌': 1}
    reconcile_tracking(s2, _read(1), [], _banner_frame(), source='t', ctx=None)
    assert s2.tracked_bench_chars[0].star == 2, '横幅帧(拖拽过渡)同样保旧'


def test_gate_source_lock() -> None:
    """静态口径锁(分包期5 补遗重钉):kernel 只持注入槽不直依 obs 桶;
    生产装配点(decision_assembly)接通真门实现,防未来重构绕过或回接直依。"""
    src = (_REPO / 'src' / 'sr_od' / 'application' / 'currency_war'
           / 'kernel' / 'cw_reconcile.py').read_text(encoding='utf-8')
    assert '_IS_MERGE_EFFECT_FRAME' in src, '采新确认前未引用合成特效帧态门注入槽'
    assert 'cw_identity_obs' not in src, 'kernel 不得直依 obs 桶(分包矩阵)'
    asm = (_REPO / 'src' / 'sr_od' / 'application' / 'currency_war'
           / 'decision_assembly.py').read_text(encoding='utf-8')
    assert 'is_merge_effect_frame' in asm, '生产装配点未接通特效帧态门'
