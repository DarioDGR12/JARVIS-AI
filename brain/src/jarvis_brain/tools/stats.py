from __future__ import annotations

from pathlib import Path


def _read(path: Path) -> str:
    try:
        return path.read_text()
    except OSError:
        return ""


def system_stats() -> dict:
    mem = _read(Path("/proc/meminfo"))
    load = _read(Path("/proc/loadavg")).split()
    cpu_temp = None
    thermal = Path("/sys/class/thermal/thermal_zone0/temp")
    if thermal.is_file():
        raw = _read(thermal).strip()
        if raw.isdigit():
            cpu_temp = round(int(raw) / 1000, 1)

    def _kib(name: str) -> int | None:
        for line in mem.splitlines():
            if line.startswith(name):
                parts = line.split()
                if len(parts) >= 2 and parts[1].isdigit():
                    return int(parts[1])
        return None

    total = _kib("MemTotal:")
    avail = _kib("MemAvailable:")
    used_pct = None
    if total and avail is not None and total > 0:
        used_pct = round(100 * (1 - avail / total), 1)
    return {
        "load": [float(x) for x in load[:3]] if len(load) >= 3 else [],
        "mem_total_kib": total,
        "mem_avail_kib": avail,
        "mem_used_pct": used_pct,
        "cpu_temp_c": cpu_temp,
    }


def format_stats(stats: dict) -> str:
    load = stats.get("load") or []
    load_s = " ".join(f"{x:.2f}" for x in load) if load else "?"
    mem = stats.get("mem_used_pct")
    temp = stats.get("cpu_temp_c")
    bits = [f"load {load_s}"]
    if mem is not None:
        bits.append(f"RAM {mem}%")
    if temp is not None:
        bits.append(f"{temp} °C")
    return "Sistema: " + ", ".join(bits) + "."
