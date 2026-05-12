"""
acds-report: HTML iteration diary generator
Generates beautiful HTML reports documenting ACDS loop iterations.
"""
import json
import logging
import time
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum, auto

logger = logging.getLogger(__name__)


class ReportType(Enum):
    """Type of report to generate."""
    ITERATION = auto()
    SUMMARY = auto()
    DETAILED = auto()
    DIFF = auto()


@dataclass
class LogEntry:
    """A single log entry from ACDS execution."""
    timestamp: float
    level: str
    message: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    iteration: int = 0


@dataclass
class IterationData:
    """Data for a single iteration."""
    iteration: int
    task: str
    status: str
    start_time: float
    end_time: Optional[float] = None
    duration_seconds: float = 0.0
    changes: List[Dict] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    logs: List[LogEntry] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ReportConfig:
    """Configuration for report generation."""
    title: str = "ACDS Iteration Report"
    theme: str = "dark"
    include_logs: bool = True
    include_diff: bool = True
    include_metrics: bool = True
    max_log_entries: int = 100
    output_path: str = "acds-report.html"
    author: str = "ACDS"
    logo_url: Optional[str] = None


class HTMLGenerator:
    """Generates HTML content for reports."""
    
    @staticmethod
    def generate_report(data: Dict[str, Any], config: ReportConfig) -> str:
        """Generate complete HTML report."""
        theme = HTMLGenerator._get_theme(config.theme)
        
        iterations_html = HTMLGenerator._render_iterations(data.get("iterations", []))
        metrics_html = HTMLGenerator._render_metrics(data.get("summary", {}))
        timeline_html = HTMLGenerator._render_timeline(data.get("iterations", []))
        
        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{config.title}</title>
    <style>
        {theme}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 0; padding: 0; background: var(--bg); color: var(--text); }}
        .container {{ max-width: 1400px; margin: 0 auto; padding: 20px; }}
        header {{ background: var(--header-bg); padding: 30px; border-radius: 12px; margin-bottom: 30px; text-align: center; }}
        header h1 {{ margin: 0 0 10px 0; color: var(--primary); font-size: 2em; }}
        header .meta {{ color: var(--muted); font-size: 0.9em; }}
        .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; margin-bottom: 30px; }}
        .card {{ background: var(--card-bg); border-radius: 10px; padding: 20px; border: 1px solid var(--border); }}
        .card h3 {{ margin: 0 0 15px 0; color: var(--primary); border-bottom: 2px solid var(--primary); padding-bottom: 10px; }}
        .metric {{ display: flex; justify-content: space-between; padding: 10px 0; border-bottom: 1px solid var(--border); }}
        .metric:last-child {{ border-bottom: none; }}
        .metric-value {{ font-weight: bold; color: var(--accent); }}
        .iteration {{ background: var(--card-bg); border-radius: 10px; margin-bottom: 20px; overflow: hidden; border: 1px solid var(--border); }}
        .iteration-header {{ background: var(--header-bg); padding: 15px 20px; display: flex; justify-content: space-between; align-items: center; }}
        .iteration-title {{ font-weight: bold; font-size: 1.1em; }}
        .iteration-status {{ padding: 4px 12px; border-radius: 20px; font-size: 0.85em; }}
        .status-success {{ background: #10b981; color: white; }}
        .status-failed {{ background: #ef4444; color: white; }}
        .status-pending {{ background: #f59e0b; color: white; }}
        .iteration-body {{ padding: 20px; }}
        .log-entry {{ padding: 8px 12px; border-left: 3px solid var(--border); margin-bottom: 8px; font-family: 'Monaco', 'Menlo', monospace; font-size: 0.85em; }}
        .log-error {{ border-left-color: #ef4444; }}
        .log-warn {{ border-left-color: #f59e0b; }}
        .log-info {{ border-left-color: #3b82f6; }}
        .log-debug {{ border-left-color: #6b7280; }}
        .timestamp {{ color: var(--muted); margin-right: 10px; }}
        .chart {{ background: var(--card-bg); border-radius: 10px; padding: 20px; margin-bottom: 20px; }}
        .timeline {{ display: flex; flex-direction: column; gap: 10px; }}
        .timeline-item {{ display: flex; align-items: center; gap: 15px; }}
        .timeline-dot {{ width: 12px; height: 12px; border-radius: 50%; }}
        .timeline-dot.success {{ background: #10b981; }}
        .timeline-dot.failed {{ background: #ef4444; }}
        .timeline-content {{ flex: 1; }}
        footer {{ text-align: center; padding: 30px; color: var(--muted); font-size: 0.85em; }}
        @media (max-width: 768px) {{ .grid {{ grid-template-columns: 1fr; }} }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🚀 {config.title}</h1>
            <div class="meta">
                Generated by {config.author} • {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
            </div>
        </header>
        
        <div class="grid">
            {metrics_html}
        </div>
        
        {timeline_html}
        
        <h2 style="color: var(--primary); margin-bottom: 20px;">📋 Iterations</h2>
        {iterations_html}
        
        <footer>
            <p>Auto Claude Code Dev in Sleep • Iteration Report</p>
        </footer>
    </div>
</body>
</html>"""
        return html
    
    @staticmethod
    def _get_theme(theme: str) -> str:
        themes = {
            "dark": """
                :root {
                    --bg: #0f172a;
                    --card-bg: #1e293b;
                    --header-bg: #334155;
                    --text: #f1f5f9;
                    --muted: #94a3b8;
                    --primary: #38bdf8;
                    --accent: #22d3ee;
                    --border: #475569;
                }
            """,
            "light": """
                :root {
                    --bg: #f8fafc;
                    --card-bg: #ffffff;
                    --header-bg: #f1f5f9;
                    --text: #1e293b;
                    --muted: #64748b;
                    --primary: #0ea5e9;
                    --accent: #06b6d4;
                    --border: #e2e8f0;
                }
            """,
            "github": """
                :root {
                    --bg: #ffffff;
                    --card-bg: #f6f8fa;
                    --header-bg: #24292f;
                    --text: #24292f;
                    --muted: #57606a;
                    --primary: #0969da;
                    --accent: #0550ae;
                    --border: #d0d7de;
                }
            """
        }
        return themes.get(theme, themes["dark"])
    
    @staticmethod
    def _render_metrics(summary: Dict[str, Any]) -> str:
        cards = [
            ("Total Iterations", str(summary.get("total_iterations", 0)), "iterations"),
            ("Success Rate", f"{summary.get('success_rate', 0):.1f}%", "rate"),
            ("Total Duration", summary.get("total_duration", "0s"), "clock"),
            ("Files Changed", str(summary.get("files_changed", 0)), "files"),
        ]
        
        html = ""
        for icon, label, value in cards:
            html += f"""
            <div class="card">
                <h3>📊 {label}</h3>
                <div class="metric">
                    <span>{value}</span>
                </div>
            </div>
            """
        return html
    
    @staticmethod
    def _render_timeline(iterations: List[Dict]) -> str:
        items = ""
        for it in iterations[:10]:
            status_class = "success" if it.get("status") == "success" else "failed"
            items += f"""
            <div class="timeline-item">
                <div class="timeline-dot {status_class}"></div>
                <div class="timeline-content">
                    <strong>#{it.get('iteration', 0)}</strong>: {it.get('task', 'Unknown')}
                    <div style="color: var(--muted); font-size: 0.85em;">
                        {it.get('duration', '0s')} • {it.get('status', 'pending')}
                    </div>
                </div>
            </div>
            """
        
        return f"""
        <div class="chart">
            <h3 style="color: var(--primary); margin: 0 0 15px 0;">📈 Timeline</h3>
            <div class="timeline">{items}</div>
        </div>
        """
    
    @staticmethod
    def _render_iterations(iterations: List[Dict]) -> str:
        html = ""
        for it in iterations:
            status_class = it.get("status", "pending")
            status_label = status_class.capitalize()
            
            logs_html = ""
            for log in it.get("logs", [])[:10]:
                log_class = f"log-{log.get('level', 'info')}"
                ts = datetime.fromtimestamp(log.get("timestamp", 0)).strftime("%H:%M:%S")
                logs_html += f'''
                <div class="log-entry {log_class}">
                    <span class="timestamp">[{ts}]</span>
                    {log.get('message', '')}
                </div>
                '''
            
            html += f"""
            <div class="iteration">
                <div class="iteration-header">
                    <span class="iteration-title">Iteration #{it.get('iteration', 0)}: {it.get('task', 'Unknown')}</span>
                    <span class="iteration-status status-{status_class}">{status_label}</span>
                </div>
                <div class="iteration-body">
                    <p><strong>Duration:</strong> {it.get('duration', '0s')}</p>
                    <p><strong>Changes:</strong> {len(it.get('changes', []))} files</p>
                    {f'<h4>Logs:</h4><div>{logs_html}</div>' if logs_html else ''}
                </div>
            </div>
            """
        return html


class ReportGenerator:
    """
    Generates HTML reports for ACDS iterations.
    Supports multiple report types and themes.
    """
    def __init__(self, config: Optional[ReportConfig] = None):
        self.config = config or ReportConfig()
        self._html_gen = HTMLGenerator()
    
    def generate(
        self,
        iterations: List[IterationData],
        output_path: Optional[str] = None
    ) -> str:
        """Generate report from iteration data."""
        output_path = output_path or self.config.output_path
        
        summary = self._compute_summary(iterations)
        iterations_dict = [self._iteration_to_dict(it) for it in iterations]
        
        data = {
            "iterations": iterations_dict,
            "summary": summary,
            "generated_at": time.time()
        }
        
        html = self._html_gen.generate_report(data, self.config)
        
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(html, encoding="utf-8")
        
        logger.info(f"Report generated: {output_path}")
        return output_path
    
    def _compute_summary(self, iterations: List[IterationData]) -> Dict:
        total = len(iterations)
        success = sum(1 for it in iterations if it.status == "success")
        
        total_duration = sum(it.duration_seconds for it in iterations)
        
        all_changes = sum(len(it.changes) for it in iterations)
        
        return {
            "total_iterations": total,
            "success_rate": (success / total * 100) if total > 0 else 0,
            "total_duration": self._format_duration(total_duration),
            "files_changed": all_changes
        }
    
    @staticmethod
    def _format_duration(seconds: float) -> str:
        if seconds < 60:
            return f"{seconds:.1f}s"
        elif seconds < 3600:
            return f"{seconds/60:.1f}m"
        else:
            return f"{seconds/3600:.1f}h"
    
    @staticmethod
    def _iteration_to_dict(it: IterationData) -> Dict:
        return {
            "iteration": it.iteration,
            "task": it.task,
            "status": it.status,
            "start_time": datetime.fromtimestamp(it.start_time).isoformat(),
            "end_time": datetime.fromtimestamp(it.end_time).isoformat() if it.end_time else None,
            "duration": ReportGenerator._format_duration(it.duration_seconds),
            "duration_seconds": it.duration_seconds,
            "changes": it.changes,
            "errors": it.errors,
            "logs": [
                {
                    "timestamp": log.timestamp,
                    "level": log.level,
                    "message": log.message,
                    "metadata": log.metadata
                }
                for log in it.logs[:100]
            ],
            "metrics": it.metrics
        }
    
    def generate_from_file(self, data_file: str, output_path: Optional[str] = None) -> str:
        """Generate report from JSON data file."""
        data = json.loads(Path(data_file).read_text())
        iterations = [self._dict_to_iteration(d) for d in data.get("iterations", [])]
        return self.generate(iterations, output_path)
    
    @staticmethod
    def _dict_to_iteration(d: Dict) -> IterationData:
        return IterationData(
            iteration=d.get("iteration", 0),
            task=d.get("task", ""),
            status=d.get("status", "pending"),
            start_time=d.get("start_time", time.time()),
            end_time=d.get("end_time"),
            duration_seconds=d.get("duration_seconds", 0.0),
            changes=d.get("changes", []),
            errors=d.get("errors", []),
            logs=[
                LogEntry(
                    timestamp=log.get("timestamp", 0),
                    level=log.get("level", "info"),
                    message=log.get("message", ""),
                    metadata=log.get("metadata", {})
                )
                for log in d.get("logs", [])
            ],
            metrics=d.get("metrics", {})
        )


class DiaryGenerator:
    """
    Specialized generator for iteration diaries.
    Creates a timeline view of all iterations.
    """
    def __init__(self):
        self.entries: List[Dict] = []
    
    def add_entry(self, iteration: int, task: str, result: str, details: Optional[Dict] = None):
        """Add an entry to the diary."""
        self.entries.append({
            "iteration": iteration,
            "task": task,
            "result": result,
            "timestamp": time.time(),
            "details": details or {}
        })
    
    def generate_diary(self, output_path: str = "acds-diary.html") -> str:
        """Generate diary HTML."""
        timeline_items = ""
        for entry in self.entries:
            ts = datetime.fromtimestamp(entry["timestamp"]).strftime("%Y-%m-%d %H:%M")
            timeline_items += f"""
            <div class="timeline-item">
                <div class="timeline-dot success"></div>
                <div class="timeline-content">
                    <strong>#{entry['iteration']}</strong> {entry['task']}
                    <div style="color: var(--muted);">{ts}</div>
                </div>
            </div>
            """
        
        html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>ACDS Iteration Diary</title>
    <style>
        :root {{ --bg: #0f172a; --card-bg: #1e293b; --text: #f1f5f9; --muted: #94a3b8; --primary: #38bdf8; --border: #475569; }}
        body {{ font-family: -apple-system, sans-serif; background: var(--bg); color: var(--text); padding: 40px; }}
        .diary {{ max-width: 800px; margin: 0 auto; }}
        h1 {{ color: var(--primary); }}
        .entry {{ background: var(--card-bg); padding: 20px; margin-bottom: 15px; border-radius: 8px; border-left: 4px solid var(--primary); }}
        .entry-title {{ font-size: 1.2em; font-weight: bold; margin-bottom: 10px; }}
        .entry-meta {{ color: var(--muted); font-size: 0.85em; }}
    </style>
</head>
<body>
    <div class="diary">
        <h1>📔 ACDS Iteration Diary</h1>
        {timeline_items}
    </div>
</body>
</html>"""
        
        Path(output_path).write_text(html)
        return output_path


# CLI entry point
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="ACDS Report - HTML iteration diary generator")
    parser.add_argument("--input", "-i", help="Input JSON file with iteration data")
    parser.add_argument("--output", "-o", default="acds-report.html", help="Output HTML file")
    parser.add_argument("--theme", "-t", choices=["dark", "light", "github"], default="dark", help="Report theme")
    parser.add_argument("--title", help="Report title")

    args = parser.parse_args()

    gen = ReportGenerator(ReportConfig(
        title=args.title or "ACDS Iteration Report",
        theme=args.theme,
        output_path=args.output
    ))

    if args.input:
        output = gen.generate_from_file(args.input)
    else:
        # Generate sample report
        sample_data = [
            IterationData(
                iteration=1,
                task="Initialize project structure",
                status="success",
                start_time=time.time() - 3600,
                end_time=time.time() - 3500,
                duration_seconds=100,
                changes=[{"file": "README.md", "type": "create"}],
                logs=[LogEntry(time.time() - 3600, "info", "Starting iteration")]
            )
        ]
        output = gen.generate(sample_data)
    
    print(f"Report saved to: {output}")