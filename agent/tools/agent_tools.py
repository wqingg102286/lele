import os
from utils.logger_handler import logger
from langchain_core.tools import tool
from rag.rag_service import RagSummarizeService
from utils.config_handler import agent_conf
from utils.path_tool import get_abs_path
import json
from urllib.parse import urlencode
from urllib.request import urlopen
from urllib.error import URLError, HTTPError
import re

# 懒加载 RAG 服务，避免在模块导入时就立刻初始化向量库与模型，提升启动速度并方便测试。
rag: RagSummarizeService | None = None


def _get_rag_service() -> RagSummarizeService:
    global rag
    if rag is None:
        rag = RagSummarizeService()
    return rag

_IPV4_RE = re.compile(
    r"^(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)\."
    r"(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)\."
    r"(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)\."
    r"(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)$"
)

def _is_valid_ipv4(ip: str) -> bool:
    return bool(_IPV4_RE.match(ip or ""))

def _get_public_ip() -> str:
    # 可在agent.yml里覆盖
    ip_sources = agent_conf.get("public_ip_sources", [
        "https://ipv4.icanhazip.com",
    ])
    timeout = float(agent_conf.get("public_ip_timeout", 3))
    for source in ip_sources:
        try:
            with urlopen(source, timeout=timeout) as resp:
                ip = resp.read().decode("utf-8").strip()
                if _is_valid_ipv4(ip):
                    return ip
        except Exception:
            continue

    return ""

GAODE_BASE_URL = agent_conf.get("gaode_base_url")
GAODE_TIMEOUT = float(agent_conf.get("gaode_timeout"))

def _gaode_get(path: str, params: dict) -> dict:
    gaode_key = os.getenv("GAODE_KEY")
    if not gaode_key:
        raise RuntimeError("未配置高德 Key：请设置环境变量 `GAODE_KEY` 后再运行。")


    query = dict(params)
    query["key"] = gaode_key
    url = f"{GAODE_BASE_URL}{path}?{urlencode(query)}"

    try:
        with urlopen(url, timeout=GAODE_TIMEOUT) as resp:
            data = resp.read().decode("utf-8")
            return json.loads(data)
    except HTTPError as e:
        raise RuntimeError(f"高德HTTP错误: {e.code}") from e
    except URLError as e:
        raise RuntimeError(f"高德网络错误: {e.reason}") from e
    except Exception as e:
        raise RuntimeError(f"高德请求异常: {str(e)}") from e


def _resolve_city_to_adcode(city: str) -> tuple[str, str]:
    geo = _gaode_get("/v3/geocode/geo", {"address": city})
    if geo.get("status") != "1" or not geo.get("geocodes"):
        raise RuntimeError(f"城市解析失败: {geo.get('info', 'unknown')}")

    first = geo["geocodes"][0]
    adcode = first.get("adcode")
    if not adcode:
        raise RuntimeError("城市解析成功但未返回adcode")

    resolved_city = first.get("city") or first.get("district") or city
    if isinstance(resolved_city, list):
        resolved_city = "".join(resolved_city)

    return str(resolved_city), str(adcode)


@tool(description="获取指定城市的天气，以消息字符串的形式返回")
def get_weather(city: str) -> str:
    if not city or not city.strip():
        return "未提供城市名称，无法查询天气"

    try:
        resolved_city, adcode = _resolve_city_to_adcode(city.strip())
        weather = _gaode_get(
            "/v3/weather/weatherInfo",
            {"city": adcode, "extensions": "base"},
        )

        if weather.get("status") != "1" or not weather.get("lives"):
            return f"城市{resolved_city}天气查询失败：{weather.get('info', 'unknown')}"

        live = weather["lives"][0]
        condition = live.get("weather", "未知")
        temperature = live.get("temperature", "未知")
        humidity = live.get("humidity", "未知")
        wind_direction = live.get("winddirection", "未知")
        wind_power = live.get("windpower", "未知")
        report_time = live.get("reporttime", "未知")

        return (
            f"城市{resolved_city}天气为{condition}，气温{temperature}摄氏度，"
            f"空气湿度{humidity}%，{wind_direction}风{wind_power}级，"
            f"数据发布时间{report_time}。"
        )
    except Exception as e:
        logger.exception(f"[get_weather]天气查询失败 city={city}")
        return f"城市{city}天气查询失败，请稍后重试"


@tool(description="获取用户所在城市的名称，以纯字符串形式返回")
def get_user_location() -> str:
    try:
        public_ip = _get_public_ip()
        params = {"ip": public_ip} if public_ip else {}
        ip_info = _gaode_get("/v3/ip", params)

        if ip_info.get("status") != "1":
            logger.warning(
                f"[get_user_location]高德返回失败 info={ip_info.get('info')} "
                f"infocode={ip_info.get('infocode')} ip={public_ip or 'none'}"
            )
            return "未知城市"

        city = ip_info.get("city", "")
        province = ip_info.get("province", "")

        if isinstance(city, list):
            city = "".join(city)
        if isinstance(province, list):
            province = "".join(province)

        city = str(city).strip()
        province = str(province).strip()

        if city:
            return city
        if province:
            return province

        logger.warning(
            f"[get_user_location]空城市信息 info={ip_info.get('info')} "
            f"infocode={ip_info.get('infocode')} ip={public_ip or 'none'} raw={ip_info}"
        )
        return "未知城市"

    except Exception as e:
        logger.exception("[get_user_location]定位失败")
        return "未知城市"



@tool(description="从向量存储中检索参考资料")
def rag_summarize(query: str) -> str:
    return _get_rag_service().rag_summarize(query)

@tool(description="无入参，返回一个标记字符串；调用后由中间件根据工具名自动在 runtime.context 中打上报告生成标记，用于后续提示词切换。")
def fill_context_for_report():
    return "fill_context_for_report已调用"


if __name__ == '__main__':
    # loc = get_user_location.func()
    print(get_weather.func("天津"))