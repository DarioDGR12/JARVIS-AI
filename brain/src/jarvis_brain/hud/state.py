from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from jarvis_brain.bus.envelope import Event

OPERATIONAL = (
    "boot",
    "standby",
    "listening",
    "thinking",
    "tool",
    "speaking",
    "alert",
)

HUD_VIEWS = ("home", "chat", "system", "ha", "settings", "map", "vision")

_STATE_TO_MODE = {
    "thinking": "thinking",
    "idle": "standby",
    "speaking": "speaking",
    "tool": "tool",
    "alert": "alert",
    "listening": "listening",
}


@dataclass
class HudState:
    """In-memory HUD. Reimplemented; not copied from jarvis-hud."""

    operational: str = "boot"
    visual: str = "jarvis"
    view: str = "home"
    camera_hold: bool = False
    camera_enabled: bool = False
    camera_label: str | None = None
    camera_error: str | None = None
    camera_device: str | None = None
    visor: bool = False
    click_through: bool = False
    presence: bool | None = None
    standby_empty: bool = False
    last_display: dict[str, Any] | None = None
    last_speak: dict[str, Any] | None = None
    toasts: list[dict[str, Any]] = field(default_factory=list)
    ready: bool = False

    def snapshot(self) -> dict[str, Any]:
        return {
            "operational": self.operational,
            "visual": self.visual,
            "view": self.view,
            "camera_hold": self.camera_hold,
            "camera_enabled": self.camera_enabled,
            "camera_label": self.camera_label,
            "camera_error": self.camera_error,
            "camera_device": self.camera_device,
            "visor": self.visor,
            "click_through": self.click_through,
            "presence": self.presence,
            "standby_empty": self.standby_empty,
            "last_display": self.last_display,
            "last_speak": self.last_speak,
            "toasts": list(self.toasts[-8:]),
            "ready": self.ready,
            "views": list(HUD_VIEWS),
        }

    def set_mode(self, *, operational: str | None = None, visual: str | None = None) -> None:
        if operational in OPERATIONAL:
            self.operational = operational
        if visual in {"jarvis", "companion"}:
            self.visual = visual

    def show_view(self, view: str) -> bool:
        if view not in HUD_VIEWS:
            return False
        self.view = view
        return True

    def display(self, payload: dict[str, Any]) -> None:
        kind = str(payload.get("kind") or "text")
        content = str(payload.get("content") or "")
        card = {"kind": kind, "content": content, "title": payload.get("title")}
        self.last_display = card
        if kind in {"alert", "toast"}:
            self.toasts.append(card)
            self.toasts = self.toasts[-8:]
        if kind == "alert":
            self.operational = "alert"

    def apply(self, event: Event) -> None:
        payload = event.payload or {}
        if event.type == "hud.set_mode":
            self.set_mode(
                operational=payload.get("operational"),
                visual=payload.get("visual"),
            )
        elif event.type == "hud.show_view":
            self.show_view(str(payload.get("view") or ""))
        elif event.type == "hud.display":
            self.display(payload)
        elif event.type == "hud.highlight":
            self.last_display = {
                "kind": "highlight",
                "content": str(payload.get("target") or payload.get("id") or ""),
                "title": payload.get("reason"),
            }
        elif event.type == "hud.speak":
            self.last_speak = {
                "text": payload.get("text"),
                "voice": payload.get("voice") or self.visual,
            }
            self.operational = "speaking"
        elif event.type == "hud.camera":
            if "hold" in payload:
                self.camera_hold = bool(payload.get("hold"))
            if "enabled" in payload:
                self.camera_enabled = bool(payload.get("enabled"))
                if not self.camera_enabled:
                    self.camera_label = None
            if "label" in payload:
                label = str(payload.get("label") or "").strip()
                self.camera_label = label or None
            if "error" in payload:
                err = str(payload.get("error") or "").strip()
                self.camera_error = err or None
            if "device_id" in payload:
                device = str(payload.get("device_id") or "").strip()
                self.camera_device = device or None
        elif event.type == "hud.visor":
            self.visor = bool(payload.get("enabled"))
            if not self.visor:
                self.click_through = False
        elif event.type == "hud.click_through":
            self.click_through = bool(payload.get("enabled"))
        elif event.type == "hud.presence":
            present = bool(payload.get("present"))
            self.presence = present
            self.standby_empty = not present
            if not present and self.operational not in {
                "alert",
                "listening",
                "thinking",
                "speaking",
                "tool",
            }:
                self.operational = "standby"
        elif event.type == "hud.ready":
            self.ready = True
        elif event.type == "brain.status":
            mapped = _STATE_TO_MODE.get(str(payload.get("state") or ""))
            if mapped:
                self.operational = mapped
        elif event.type == "persona.changed":
            visual = payload.get("to")
            if visual in {"jarvis", "companion"}:
                self.visual = visual
        elif event.type == "auth.challenge":
            self.display(
                {
                    "kind": "alert",
                    "content": "LOOK AT CAMERA",
                    "title": payload.get("reason"),
                }
            )
            self.camera_hold = True
        elif event.type == "auth.result":
            self.camera_hold = False
            if not payload.get("ok"):
                self.display(
                    {
                        "kind": "alert",
                        "content": "Auth failed",
                        "title": payload.get("error"),
                    }
                )
            elif self.operational == "alert":
                self.operational = "standby"
