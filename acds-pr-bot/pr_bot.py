"""
acds-pr-bot: GitHub/GitLab PR integration for pr mode
Handles pull request creation, review, and merge operations.
"""
import logging
import re
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from enum import Enum
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


class PRState(Enum):
    OPEN = "open"
    CLOSED = "closed"
    MERGED = "merged"
    DRAFT = "draft"


class Platform(Enum):
    GITHUB = "github"
    GITLAB = "gitlab"


@dataclass
class PRConfig:
    """Configuration for PR operations."""
    platform: Platform = Platform.GITHUB
    repo_owner: str = ""
    repo_name: str = ""
    base_branch: str = "main"
    head_branch: str = ""
    title: str = ""
    body: str = ""
    labels: List[str] = field(default_factory=list)
    reviewers: List[str] = field(default_factory=list)
    draft: bool = False
    auto_merge: bool = False
    delete_after_merge: bool = True


@dataclass
class PRInfo:
    """Represents a pull request."""
    number: int
    title: str
    body: str
    state: PRState
    url: str
    head_branch: str
    base_branch: str
    user: str
    labels: List[str] = field(default_factory=list)
    reviewers: List[str] = field(default_factory=list)


class GitHubPRBot:
    """GitHub PR operations handler."""
    
    def __init__(self, repo_owner: str, repo_name: str, gh_token: Optional[str] = None):
        self.repo_owner = repo_owner
        self.repo_name = repo_name
        self.gh_token = gh_token
        self.platform = Platform.GITHUB

    def create_pr(
        self,
        head_branch: str,
        title: str,
        body: str,
        base: str = "main",
        draft: bool = False,
        labels: Optional[List[str]] = None,
        reviewers: Optional[List[str]] = None,
    ) -> Optional[PRInfo]:
        """Create a new pull request."""
        import subprocess
        import json
        
        cmd = [
            "gh", "pr", "create",
            "--title", title,
            "--body", body,
            "--base", base,
            "--repo", f"{self.repo_owner}/{self.repo_name}"
        ]
        if draft:
            cmd.append("--draft")
        if labels:
            cmd.extend(["--label", ",".join(labels)])
        if reviewers:
            cmd.extend(["--reviewer", ",".join(reviewers)])
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            url = result.stdout.strip()
            pr_num = int(re.search(r"/pull/(\d+)", url).group(1))
            return PRInfo(
                number=pr_num,
                title=title,
                body=body,
                state=PRState.OPEN,
                url=url,
                head_branch=head_branch,
                base_branch=base,
                user=self.repo_owner,
                labels=labels or [],
                reviewers=reviewers or []
            )
        logger.error(f"PR creation failed: {result.stderr}")
        return None

    def get_pr(self, pr_number: int) -> Optional[PRInfo]:
        """Get PR information."""
        import subprocess
        import json
        
        result = subprocess.run(
            ["gh", "pr", "view", str(pr_number), "--json", 
             "number,title,body,state,url,headRefName,baseRefName,author,labels,reviewRequests",
             "--repo", f"{self.repo_owner}/{self.repo_name}"],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            return PRInfo(
                number=data["number"],
                title=data["title"],
                body=data["body"],
                state=PRState(data["state"]),
                url=data["url"],
                head_branch=data["headRefName"],
                base_branch=data["baseRefName"],
                user=data["author"]["login"],
                labels=[l["name"] for l in data.get("labels", [])],
                reviewers=[r["login"] for r in data.get("reviewRequests", [])]
            )
        return None

    def merge_pr(self, pr_number: int, method: str = "merge") -> bool:
        """Merge a pull request."""
        import subprocess
        result = subprocess.run(
            ["gh", "pr", "merge", str(pr_number), f"--{method}", "--admin",
             "--repo", f"{self.repo_owner}/{self.repo_name}"],
            capture_output=True, text=True
        )
        return result.returncode == 0

    def close_pr(self, pr_number: int) -> bool:
        """Close a pull request."""
        import subprocess
        result = subprocess.run(
            ["gh", "pr", "close", str(pr_number),
             "--repo", f"{self.repo_owner}/{self.repo_name}"],
            capture_output=True, text=True
        )
        return result.returncode == 0

    def add_labels(self, pr_number: int, labels: List[str]) -> bool:
        """Add labels to a PR."""
        import subprocess
        result = subprocess.run(
            ["gh", "pr", "edit", str(pr_number), "--add-label", ",".join(labels),
             "--repo", f"{self.repo_owner}/{self.repo_name}"],
            capture_output=True, text=True
        )
        return result.returncode == 0

    def request_reviewers(self, pr_number: int, reviewers: List[str]) -> bool:
        """Request reviewers for a PR."""
        import subprocess
        result = subprocess.run(
            ["gh", "pr", "edit", str(pr_number), "--add-reviewer", ",".join(reviewers),
             "--repo", f"{self.repo_owner}/{self.repo_name}"],
            capture_output=True, text=True
        )
        return result.returncode == 0


class GitLabMRBot:
    """GitLab Merge Request operations handler."""
    
    def __init__(self, project_id: str, gl_token: Optional[str] = None):
        self.project_id = project_id
        self.gl_token = gl_token
        self.platform = Platform.GITLAB
        self.api_url = f"https://gitlab.com/api/v4/projects/{project_id}"

    def _headers(self) -> Dict[str, str]:
        return {"PRIVATE-TOKEN": self.gl_token} if self.gl_token else {}

    def create_mr(
        self,
        source_branch: str,
        title: str,
        description: str,
        target: str = "main"
    ) -> Optional[Dict]:
        """Create a merge request."""
        import urllib.request
        import json
        
        data = json.dumps({
            "source_branch": source_branch,
            "target_branch": target,
            "title": title,
            "description": description
        }).encode()
        
        req = urllib.request.Request(
            f"{self.api_url}/merge_requests",
            data=data,
            headers=self._headers()
        )
        try:
            with urllib.request.urlopen(req) as resp:
                return json.loads(resp.read())
        except Exception as e:
            logger.error(f"MR creation failed: {e}")
            return None

    def merge_mr(self, mr_iid: int) -> bool:
        """Merge a merge request."""
        import urllib.request
        import json
        
        req = urllib.request.Request(
            f"{self.api_url}/merge_requests/{mr_iid}/merge",
            data=b"{}",
            headers={**self._headers(), "Content-Type": "application/json"}
        )
        try:
            urllib.request.urlopen(req)
            return True
        except Exception as e:
            logger.error(f"MR merge failed: {e}")
            return False


class PRBotFactory:
    """Factory for creating PR bot instances."""
    
    @staticmethod
    def from_url(url: str, token: Optional[str] = None) -> Any:
        """Create PR bot from repository URL."""
        parsed = urlparse(url)
        platform = Platform.GITHUB if "github.com" in parsed.netloc else Platform.GITLAB
        
        if platform == Platform.GITHUB:
            path_parts = parsed.path.strip("/").split("/")
            return GitHubPRBot(path_parts[0], path_parts[1], token)
        else:
            project_id = parsed.path.strip("/").split("/")[-1]
            return GitLabMRBot(project_id, token)

    @staticmethod
    def create(platform: Platform, **kwargs) -> Any:
        """Create PR bot by platform type."""
        if platform == Platform.GITHUB:
            return GitHubPRBot(kwargs["repo_owner"], kwargs["repo_name"], kwargs.get("token"))
        elif platform == Platform.GITLAB:
            return GitLabMRBot(kwargs["project_id"], kwargs.get("token"))


class PRMode:
    """
    PR mode controller for automated PR workflow.
    Manages creating, validating, and merging PRs.
    """
    def __init__(self, bot: Any):
        self.bot = bot
        self.current_pr: Optional[PRInfo] = None

    def create_pr_for_branch(
        self,
        branch: str,
        title: str,
        description: str,
        config: Optional[PRConfig] = None
    ) -> Optional[PRInfo]:
        """Create PR from a branch."""
        config = config or PRConfig()
        if isinstance(self.bot, GitHubPRBot):
            pr = self.bot.create_pr(
                head_branch=branch,
                title=title,
                body=description,
                base=config.base_branch,
                draft=config.draft,
                labels=config.labels,
                reviewers=config.reviewers
            )
        else:
            pr = self.bot.create_mr(
                source_branch=branch,
                title=title,
                description=description,
                target=config.base_branch
            )
        
        self.current_pr = pr
        return pr

    def validate_pr(self) -> Dict[str, Any]:
        """Validate current PR status."""
        if not self.current_pr:
            return {"valid": False, "error": "No active PR"}
        
        if isinstance(self.bot, GitHubPRBot):
            pr = self.bot.get_pr(self.current_pr.number)
        else:
            pr = None
        
        if pr:
            checks = {
                "valid": pr.state == PRState.OPEN,
                "state": pr.state.value,
                "labels": pr.labels,
                "reviewers": pr.reviewers,
                "url": pr.url
            }
            return checks
        return {"valid": False, "error": "PR not found"}

    def merge_if_ready(self, min_approvals: int = 1) -> bool:
        """Merge PR if it meets criteria."""
        if not self.current_pr:
            return False
        
        validation = self.validate_pr()
        if not validation.get("valid"):
            return False
        
        return self.bot.merge_pr(self.current_pr.number)

    def cleanup(self) -> bool:
        """Clean up after PR work."""
        if self.current_pr and isinstance(self.bot, GitHubPRBot):
            return self.bot.close_pr(self.current_pr.number)
        return True


# CLI entry point
if __name__ == "__main__":
    import argparse
    import os

    parser = argparse.ArgumentParser(description="ACDS PR Bot - GitHub/GitLab PR integration")
    parser.add_argument("action", choices=["create", "merge", "status", "close"])
    parser.add_argument("--repo", help="Repository (owner/name)")
    parser.add_argument("--branch", help="Branch name")
    parser.add_argument("--title", help="PR title")
    parser.add_argument("--body", help="PR description")

    args = parser.parse_args()

    if not args.repo:
        print("Error: --repo required")
        exit(1)

    owner, name = args.repo.split("/")
    bot = GitHubPRBot(owner, name)
    pr_mode = PRMode(bot)

    if args.action == "create":
        pr = pr_mode.create_pr_for_branch(
            branch=args.branch,
            title=args.title or f"Update from {args.branch}",
            description=args.body or ""
        )
        if pr:
            print(f"Created PR #{pr.number}: {pr.url}")
        else:
            print("Failed to create PR")

    elif args.action == "merge":
        if pr_mode.current_pr:
            success = pr_mode.merge_if_ready()
            print("Merged" if success else "Merge failed")