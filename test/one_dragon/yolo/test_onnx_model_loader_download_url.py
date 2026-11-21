"""回归锁:YOLO 模型下载 URL 的代理拼接(空 gh_proxy_url 回落默认代理)。

背景:实机一条龙运行中,模拟宇宙 app 启动时检测到模型目录为空,走下载路径;
``YoloScreenDetector`` 构造 ``Yolov8Detector`` 未传 ``gh_proxy_url``(构造器默认
``None``),旧代码直接拼接产出 ``None/https://...`` 非法 URL,``ValueError:
unknown url type`` → 模型下载必失败 → app 启动即崩(本次一条龙仅模拟宇宙
跳过,其余应用全部成功的唯一失败点)。

修后语义:``build_model_download_url`` 纯函数负责拼 URL——gh_proxy 开启但
gh_proxy_url 为空(None/'')时回落模块默认代理 ``_GH_PROXY_URL``;personal_proxy
优先级高于 gh_proxy,此时不加前缀(代理由 http_proxy/https_proxy 环境变量承担)。
"""

from one_dragon.yolo import onnx_model_loader
from one_dragon.yolo.onnx_model_loader import build_model_download_url

_BASE = 'https://github.com/OneDragon-Anything/OneDragon-YOLO/releases/download/sr_model'
_NAME = 'yolov8n-640-simuni-0601'


def test_empty_gh_proxy_url_falls_back_to_default_proxy() -> None:
    """核心回归:gh_proxy 开启但 gh_proxy_url 为空 → 必须回落默认代理,禁产出非法 URL。"""
    for empty in (None, ''):
        url = build_model_download_url(
            model_download_url=_BASE, model_name=_NAME,
            gh_proxy=True, gh_proxy_url=empty, personal_proxy=None,
        )
        expected = f'{onnx_model_loader._GH_PROXY_URL}/{_BASE}/{_NAME}.zip'  # noqa: SLF001
        assert url == expected, (
            f'gh_proxy_url={empty!r} 时应回落模块默认代理 '
            f'{onnx_model_loader._GH_PROXY_URL}(空值直接拼接=非法 URL),实得 {url!r}'
        )
        assert not url.startswith('None/'), '禁止 None 字面量混入 URL(原始事故形态)'


def test_explicit_gh_proxy_url_and_off_switch() -> None:
    """gh_proxy_url 显式配置时用配置值;gh_proxy 关闭时不加任何前缀。"""
    proxy = 'https://mirror.example.com'
    url = build_model_download_url(
        model_download_url=_BASE, model_name=_NAME,
        gh_proxy=True, gh_proxy_url=proxy, personal_proxy=None,
    )
    assert url == f'{proxy}/{_BASE}/{_NAME}.zip', f'应使用显式配置的代理前缀,实得 {url!r}'

    raw = build_model_download_url(
        model_download_url=_BASE, model_name=_NAME,
        gh_proxy=False, gh_proxy_url=None, personal_proxy=None,
    )
    assert raw == f'{_BASE}/{_NAME}.zip', f'gh_proxy 关闭时应返回原始 URL,实得 {raw!r}'


def test_personal_proxy_wins_over_gh_proxy_prefix() -> None:
    """personal_proxy 非空时优先于 gh_proxy:不加 URL 前缀,代理走环境变量。"""
    url = build_model_download_url(
        model_download_url=_BASE, model_name=_NAME,
        gh_proxy=True, gh_proxy_url='https://mirror.example.com',
        personal_proxy='http://127.0.0.1:7890',
    )
    assert url == f'{_BASE}/{_NAME}.zip', (
        f'personal_proxy 生效时不应再拼 gh 代理前缀(双代理叠加),实得 {url!r}'
    )
