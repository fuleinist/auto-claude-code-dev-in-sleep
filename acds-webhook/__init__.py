"""
acds-webhook: Slack/Discord interactive gate notification for ACDS
Sends rich formatted messages at Ralph gates, supports approval via webhook reply.
"""
import json
import logging
import time
import threading
from dataclasses import dataclass, field
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Optional, Dict, Any, List
from urllib.parse import urlparse, parse_qs

logger = logging.getLogger(__name__)


@dataclass
class GateStatus:
    """Status of a Ralph gate checkpoint."""
    iteration: int
    executor_model: str
    coverage: Optional[float] = None
    coverage_delta: Optional[float] = None
    reviewer_score: Optional[float] = None
    score_delta: Optional[float] = None
    gates_passed: List[str] = field(default_factory=list)
    gates_failed: List[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)


class _WebhookHandler(BaseHTTPRequestHandler):
    """HTTP handler for approval callbacks."""

    approval_result: Optional[str] = None
    request_log: List[Dict] = field(default_factory=list)

    def log_message(self, fmt, *args):
        logger.info(f"[WebhookServer] {fmt % args}")

    def do_GET(self):
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        status = {"status": "ok"}

        if parsed.path == "/approve":
            _WebhookHandler.approval_result = "approved"
            status = {"status": "approved", "message": "Loop approved, continuing..."}
        elif parsed.path == "/abort":
            _WebhookHandler.approval_result = "aborted"
            status = {"status": "aborted", "message": "Loop aborted by human."}
        elif parsed.path == "/status":
            status = {"result": _WebhookHandler.approval_result or "pending"}
        else:
            self.send_response(404)
            self.end_headers()
            return

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(status).encode())


@dataclass
class WebhookConfig:
    """Configuration for webhook notifications."""
    url: str = ""
    platform: str = "slack"  # "slack" or "discord"
    port: int = 8765
    timeout_seconds: int = 300


class SlackNotifier:
    """Send Slack Block Kit messages for gate approval."""

    @staticmethod
    def build_blocks(status: GateStatus, approval_base: str) -> Dict:
        gate_lines = ""
        for g in status.gates_passed:
            gate_lines += f"• {g}: ✅ PASS\n"
        for g in status.gates_failed:
            gate_lines += f"• {g}: ❌ FAIL\n"

        blocks = [
            {"type": "header", "text": {"type": "plain_text", "text": "🛡️ ACDS Ralph Gate Check", "emoji": True}},
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Repo:*\n`auto-claude-code-dev-in-sleep`"},
                    {"type": "mrkdwn", "text": f"*Iteration:*\n{status.iteration}/10"},
                    {"type": "mrkdwn", "text": f"*Executor:*\n{status.executor_model}"},
                    {
                        "type": "mrkdwn",
                        "text": f"*Reviewer Score:*\n{status.reviewer_score}/10"
                        if status.reviewer_score else "*Reviewer Score:*\n—",
                    },
                ],
            },
        ]

        if status.coverage is not None:
            blocks.append({
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Coverage:*\n{status.coverage}%"},
                    {
                        "type": "mrkdwn",
                        "text": f"*Coverage Δ:*\n{'+' if (status.coverage_delta or 0) >= 0 else ''}{status.coverage_delta}%",
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Score Δ:*\n{'+' if (status.score_delta or 0) >= 0 else ''}{status.score_delta}pt",
                    },
                ],
            })

        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": gate_lines}})

        approve_url = f"{approval_base}/approve"
        abort_url = f"{approval_base}/abort"
        blocks.append({
            "type": "actions",
            "elements": [
                {"type": "button", "text": {"type": "plain_text", "text": "✅ Approve"}, "action_id": "acds_approve", "url": approve_url},
                {"type": "button", "text": {"type": "plain_text", "text": "🚫 Force Abort"}, "action_id": "acds_abort", "url": abort_url},
            ],
        })

        return {"blocks": blocks}

    @staticmethod
    def send(url: str, blocks: Dict) -> bool:
        import urllib.request
        try:
            data = json.dumps(blocks).encode()
            req = urllib.request.Request(
                url, data=data, headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.status == 200
        except Exception as e:
            logger.error(f"Slack send failed: {e}")
            return False


class DiscordNotifier:
    """Send Discord embeds for gate approval."""

    @staticmethod
    def build_embed(status: GateStatus, approval_base: str) -> Dict:
        fields = [
            {"name": "Iteration", "value": f"{status.iteration}/10", "inline": True},
            {"name": "Executor", "value": status.executor_model, "inline": True},
            {
                "name": "Reviewer Score",
                "value": f"{status.reviewer_score}/10" if status.reviewer_score else "—",
                "inline": True,
            },
        ]

        if status.coverage is not None:
            fields += [
                {"name": "Coverage", "value": f"{status.coverage}%", "inline": True},
                {"name": "Coverage Δ", "value": f"{status.coverage_delta:+.1f}%", "inline": True},
            ]

        gate_lines = "\n".join([f"✅ {g}" for g in status.gates_passed])
        if status.gates_failed:
            gate_lines += "\n" + "\n".join([f"❌ {g}" for g in status.gates_failed])
        if gate_lines:
            fields.append({"name": "Ralph Gates", "value": gate_lines, "inline": False})

        return {
            "embeds": [{
                "title": "🛡️ ACDS Ralph Gate Check",
                "color": 0x10B981 if not status.gates_failed else 0xEF4444,
                "fields": fields,
                "url": approval_base,
                "footer": {"text": "ACDS Human Handoff"},
            }]
        }

    @staticmethod
    def send(url: str, embed: Dict) -> bool:
        import urllib.request
        try:
            data = json.dumps(embed).encode()
            req = urllib.request.Request(
                url, data=data, headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.status == 200
        except Exception as e:
            logger.error(f"Discord send failed: {e}")
            return False


class WebhookNotifier:
    """
    Sends gate checkpoint notifications and waits for human approval.
    Supports both Slack and Discord webhooks.
    """

    def __init__(self, config: Optional[WebhookConfig] = None):
        self.config = config or WebhookConfig()
        self._server: Optional[HTTPServer] = None
        self._server_thread: Optional[threading.Thread] = None

    def start_server(self):
        """Start the approval callback server."""
        if not self.config.url:
            return
        try:
            self._server = HTTPServer(("localhost", self.config.port), _WebhookHandler)
            self._server_thread = threading.Thread(target=self._server.serve_forever, daemon=True)
            self._server_thread.start()
            logger.info(f"Webhook server started on port {self.config.port}")
        except Exception as e:
            logger.warning(f"Could not start webhook server: {e}")

    def stop_server(self):
        if self._server:
            self._server.shutdown()
            self._server = None

    def notify_and_wait(self, status: GateStatus) -> str:
        """
        Send notification and wait for approval.
        Returns: 'approved' | 'aborted' | 'timeout'
        """
        self.start_server()
        approval_base = f"http://localhost:{self.config.port}"

        if self.config.platform == "slack":
            blocks = SlackNotifier.build_blocks(status, approval_base)
            SlackNotifier.send(self.config.url, blocks)
        elif self.config.platform == "discord":
            embed = DiscordNotifier.build_embed(status, approval_base)
            DiscordNotifier.send(self.config.url, embed)

        _WebhookHandler.approval_result = None
        start = time.time()
        while time.time() - start < self.config.timeout_seconds:
            if _WebhookHandler.approval_result:
                result = _WebhookHandler.approval_result
                self.stop_server()
                return result
            time.sleep(1)

        self.stop_server()
        return "timeout"

    def send_notification(self, status: GateStatus) -> bool:
        """Send notification without waiting for response."""
        if self.config.platform == "slack":
            blocks = SlackNotifier.build_blocks(status, "http://localhost:8765")
            return SlackNotifier.send(self.config.url, blocks)
        elif self.config.platform == "discord":
            embed = DiscordNotifier.build_embed(status, "http://localhost:8765")
            return DiscordNotifier.send(self.config.url, embed)
        return False