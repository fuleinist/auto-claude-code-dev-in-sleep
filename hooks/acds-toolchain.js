/**
 * acds-toolchain.js — Toolchain Intelligence hook for ACDS
 * 
 * Fetches relevant skills from VoltAgent/awesome-agent-skills per iteration
 * based on: language, framework, change type, executor model.
 * 
 * Usage: node acds-toolchain.js <project-path> [--stack js|py|rust|go|cs|java|ts|latex]
 */

const fs = require('fs');
const path = require('path');
const https = require('https');
const http = require('http');
const { execSync } = require('child_process');

const PROJECT_ROOT = process.argv[2] || process.cwd();
const STACK_ARG = process.argv[3] || '';

// ─── Skill registry (mirrored from VoltAgent/awesome-agent-skills) ──
const SKILL_REGISTRY = {
  // JavaScript / TypeScript
  'js': {
    'ts-refactor': { 
      repo: 'anthropics/ts-refactor', 
      desc: 'TypeScript refactoring patterns',
      url: 'https://officialskills.sh/anthropics/skills/ts-refactor'
    },
    'vitest-gen': {
      repo: 'vitest/test-generator',
      desc: 'Vitest test generation',
      url: 'https://officialskills.sh/vitest/skills/test-gen'
    },
    'eslint-fix': {
      repo: 'eslint/npx',
      desc: 'ESLint auto-fix',
      cmd: 'npx eslint . --fix'
    }
  },
  'ts': {
    'ts-refactor': {
      repo: 'anthropics/ts-refactor',
      desc: 'TypeScript refactoring patterns',
      url: 'https://officialskills.sh/anthropics/skills/ts-refactor'
    },
    'ts-types': {
      repo: 'anthropics/ts-types',
      desc: 'Type-safe TypeScript patterns',
      url: 'https://officialskills.sh/anthropics/skills/ts-types'
    },
    'vitest-gen': {
      repo: 'vitest/test-generator',
      desc: 'Vitest test generation',
      url: 'https://officialskills.sh/vitest/skills/test-gen'
    }
  },
  'py': {
    'py-refactor': {
      repo: 'pylint/pylint',
      desc: 'Python refactoring patterns',
      cmd: 'python -m pylint --generate-rcfile > .pylintrc 2>/dev/null || true'
    },
    'pytest-gen': {
      repo: 'pytest/pytest',
      desc: 'Pytest test generation patterns',
      cmd: 'pytest --collect-only 2>/dev/null | head -20'
    }
  },
  'rust': {
    'rust-clippy': {
      repo: 'rust-lang/rust-clippy',
      desc: 'Rust linting and auto-fix',
      cmd: 'cargo clippy -- -W clippy::all 2>/dev/null || echo "no clippy"'
    },
    'rust-test': {
      repo: 'rust-lang/cargo-test',
      desc: 'Rust test patterns',
      cmd: 'cargo test -- --nocapture 2>&1 | tail -20'
    }
  },
  'go': {
    'go-vet': {
      repo: 'golang/go',
      desc: 'Go vet and lint patterns',
      cmd: 'go vet ./... 2>&1'
    },
    'go-test': {
      repo: 'golang/go-test',
      desc: 'Go test patterns',
      cmd: 'go test -v ./... 2>&1 | tail -30'
    }
  },
  'default': {
    'general-refactor': {
      repo: 'voltagent/awesome-agent-skills',
      desc: 'General refactoring patterns',
      url: 'https://github.com/VoltAgent/awesome-agent-skills'
    },
    'security-audit': {
      repo: 'trailofbits/security-audit',
      desc: 'Security audit patterns',
      url: 'https://github.com/trailofbits/security-audit'
    },
    'docs-gen': {
      repo: 'anthropics/md',
      desc: 'Markdown documentation patterns',
      url: 'https://officialskills.sh/anthropics/skills/md'
    }
  }
};

// ─── Detect stack ─────────────────────────────────────────────────
function detectStack() {
  const files = fs.readdirSync(PROJECT_ROOT).filter(f => !f.startsWith('.'));
  
  if (files.includes('package.json')) {
    try {
      const pkg = JSON.parse(fs.readFileSync(path.join(PROJECT_ROOT, 'package.json'), 'utf8'));
      if (pkg.devDependencies?.typescript || pkg.dependencies?.typescript || files.includes('tsconfig.json')) {
        return 'ts';
      }
      return 'js';
    } catch {}
  }
  
  if (files.includes('pyproject.toml') || files.includes('setup.py') || files.includes('requirements.txt')) {
    return 'py';
  }
  
  if (files.includes('Cargo.toml')) return 'rust';
  if (files.includes('go.mod')) return 'go';
  if (files.includes('*.csproj') || files.includes('*.sln')) return 'cs';
  if (files.includes('pom.xml') || files.includes('build.gradle')) return 'java';
  
  return 'default';
}

function getExplicitStack() {
  if (STACK_ARG === '--stack' || STACK_ARG === '-s') {
    return process.argv[4] || 'default';
  }
  // Parse from args
  const stackIdx = process.argv.indexOf('--stack');
  if (stackIdx !== -1 && process.argv[stackIdx + 1]) {
    return process.argv[stackIdx + 1];
  }
  return null;
}

// ─── Select skills ─────────────────────────────────────────────────
function selectSkills(stack, changeType) {
  const stackSkills = SKILL_REGISTRY[stack] || SKILL_REGISTRY['default'];
  const defaultSkills = SKILL_REGISTRY['default'];
  
  const selected = {};
  
  // Always include general refactor
  if (defaultSkills['general-refactor']) selected['general-refactor'] = defaultSkills['general-refactor'];
  
  // Stack-specific skills
  for (const [name, skill] of Object.entries(stackSkills)) {
    selected[name] = skill;
  }
  
  // Context-aware additions
  if (changeType === 'security') {
    if (SKILL_REGISTRY['default']['security-audit']) {
      selected['security-audit'] = SKILL_REGISTRY['default']['security-audit'];
    }
  }
  
  if (changeType === 'docs') {
    if (SKILL_REGISTRY['default']['docs-gen']) {
      selected['docs-gen'] = SKILL_REGISTRY['default']['docs-gen'];
    }
  }
  
  return selected;
}

// ─── Fetch from GitHub (lightweight) ──────────────────────────────
async function fetchGitHubSkills() {
  return new Promise((resolve) => {
    try {
      const req = https.get('https://api.github.com/repos/VoltAgent/awesome-agent-skills/contents', {
        headers: { 'User-Agent': 'ACDS/1.0' }
      }, (res) => {
        let data = '';
        res.on('data', chunk => data += chunk);
        res.on('end', () => {
          try {
            const json = JSON.parse(data);
            const skills = json.filter(f => f.type === 'dir').map(f => f.name).slice(0, 20);
            resolve(skills);
          } catch {
            resolve([]);
          }
        });
      });
      req.setTimeout(5000, () => { req.destroy(); resolve([]); });
      req.on('error', () => resolve([]));
    } catch {
      resolve([]);
    }
  });
}

// ─── Main ─────────────────────────────────────────────────────────
async function main() {
  const explicitStack = getExplicitStack();
  const detectedStack = detectStack();
  const stack = explicitStack || detectedStack;
  
  console.log(`\n🔧 ACDS Toolchain Intelligence`);
  console.log('─'.repeat(60));
  console.log(`  Project: ${PROJECT_ROOT}`);
  console.log(`  Detected stack: ${detectedStack}${explicitStack ? ` (override: ${explicitStack})` : ''}`);
  
  // Detect change type from recent commits
  let changeType = 'general';
  try {
    const log = execSync('git log --oneline -5', { cwd: PROJECT_ROOT, encoding: 'utf8', timeout: 5000 });
    if (/security|vuln|cve/i.test(log)) changeType = 'security';
    else if (/doc|readme|changelog/i.test(log)) changeType = 'docs';
    else if (/test|spec/i.test(log)) changeType = 'testing';
  } catch {}
  
  // Select skills
  const skills = selectSkills(stack, changeType);
  
  console.log(`\n  Selected skills (${Object.keys(skills).length}):`);
  for (const [name, skill] of Object.entries(skills)) {
    console.log(`    • ${name}`);
    console.log(`      ${skill.desc}`);
    if (skill.url) console.log(`      → ${skill.url}`);
    else if (skill.cmd) console.log(`      → cmd: ${skill.cmd}`);
    else console.log(`      → repo: ${skill.repo}`);
  }
  
  // Try to get live skills from VoltAgent
  console.log('\n  Querying VoltAgent/awesome-agent-skills...');
  const liveSkills = await fetchGitHubSkills();
  if (liveSkills.length) {
    console.log(`  Found ${liveSkills.length} additional skills`);
    skills['_live'] = { skills: liveSkills };
  }
  
  // Save toolchain history
  const stateDir = path.join(PROJECT_ROOT, '.acds', 'state');
  const toolchainFile = path.join(stateDir, 'toolchain_history.json');
  
  if (!fs.existsSync(stateDir)) fs.mkdirSync(stateDir, { recursive: true });
  
  const history = fs.existsSync(toolchainFile) 
    ? JSON.parse(fs.readFileSync(toolchainFile, 'utf8'))
    : { iterations: [] };
  
  history.iterations.push({
    timestamp: new Date().toISOString(),
    stack,
    detectedStack,
    changeType,
    skills: Object.entries(skills).map(([name, s]) => ({ name, desc: s.desc, repo: s.repo, url: s.url })),
    liveSkillsCount: liveSkills.length
  });
  
  fs.writeFileSync(toolchainFile, JSON.stringify(history, null, 2));
  console.log(`\n  Toolchain history saved: ${toolchainFile}`);
  
  // Output for consumption
  // Log dependency tracking (feature: track-deps)
  const trackDepsIdx = process.argv.indexOf('--track-deps');
  if (trackDepsIdx !== -1 && process.argv[trackDepsIdx + 1]) {
    const dep = process.argv[trackDepsIdx + 1];
    history.iterations[history.iterations.length - 1].dependency = dep;
    history.iterations[history.iterations.length - 1].dependency_raw = process.argv.slice(trackDepsIdx + 1).join(' ');
    console.log(`\n  Tracking dependency: ${dep}`);
  }

  console.log('\n  ACDS_TOOLCHAIN_JSON=' + JSON.stringify(skills));
}

main().catch(err => {
  console.error(`\n💥 Toolchain error: ${err.message}`);
  process.exit(1);
});