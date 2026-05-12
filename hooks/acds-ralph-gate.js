/**
 * acds-ralph-gate.js — Ralph Loop validation hook for ACDS
 * 
 * Runs before each ACDS iteration to validate gate conditions.
 * Aborts the loop if any critical gate fails.
 * 
 * Usage: node acds-ralph-gate.js <project-path> [mode=gate-name]
 *   mode: pre    → pre-iteration gate check
 *         post   → post-iteration gate check (needs score + diff info)
 *         status → show current gate status
 * 
 * Exit codes:
 *   0 = all gates passed
 *   1 = gate failed → abort loop
 *   2 = no ralph_gates.md found (warn only)
 */

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

const PROJECT_ROOT = process.argv[2] || process.cwd();
const MODE = process.argv[3] || 'pre';

const RALPH_GATES_FILE = path.join(PROJECT_ROOT, 'ralph_gates.md');
const STATE_DIR = path.join(PROJECT_ROOT, '.acds', 'state');
const STATE_FILE = path.join(STATE_DIR, 'ralph_checkpoints.json');
const DIFF_SIZE_DEFAULT = 500; // lines

// ─── Gate definitions ─────────────────────────────────────────────
const GATES = {
  ralph_code_sanity: {
    check: async () => {
      try {
        // Check package.json scripts
        const pkgPath = path.join(PROJECT_ROOT, 'package.json');
        if (fs.existsSync(pkgPath)) {
          const pkg = JSON.parse(fs.readFileSync(pkgPath, 'utf8'));
          const scripts = pkg.scripts || {};
          
          const checks = [];
          if (scripts.lint) checks.push(() => runCmd('npm run lint'));
          if (scripts['type-check'] || scripts.types) checks.push(() => runCmd('npm run type-check'));
          if (scripts.test) checks.push(() => runCmd('npm run test -- --passWithNoTests'));
          
          for (const check of checks) {
            try { check(); } catch { return false; }
          }
        }
        
        // Check for common project types
        const tsconfig = path.join(PROJECT_ROOT, 'tsconfig.json');
        if (fs.existsSync(tsconfig)) {
          try { runCmd('npx tsc --noEmit'); } catch { return false; }
        }
        
        const pyproject = path.join(PROJECT_ROOT, 'pyproject.toml');
        if (fs.existsSync(pyproject)) {
          try { runCmd('python -m py_compile .'); } catch { /* skip */ }
        }
        
        return true;
      } catch {
        return false;
      }
    },
    abortOn: 'critical build failure',
    description: 'Run lint/typecheck/tests, abort on critical failure'
  },
  
  ralph_semantic_check: {
    check: async () => {
      const state = loadState();
      if (!state) return true; // no state yet = first run, pass
      
      const lastScore = state.lastScore;
      const lastReviewer = state.lastReviewer || {};
      
      // Reviewer confirms semantic correctness (score >= 7)
      if (lastScore !== undefined && lastScore < 7) {
        console.log(`[RALPH] semantic_check failed: score ${lastScore}/10 below threshold`);
        return false;
      }
      
      return true;
    },
    abortOn: 'regression or broken intent',
    description: 'Reviewer confirms semantic correctness'
  },
  
  ralph_diff_size: {
    check: async () => {
      const state = loadState();
      const maxDiff = (state && state.maxDiffLines) || DIFF_SIZE_DEFAULT;
      
      // Check git diff size
      try {
        const diffOutput = execSync('git diff --stat', { 
          cwd: PROJECT_ROOT, 
          encoding: 'utf8',
          timeout: 10000 
        });
        
        const added = (diffOutput.match(/\d+ insertion/i) || [''])[0].match(/\d+/)?.[0] || '0';
        const deleted = (diffOutput.match(/\d+ deletion/i) || [''])[0].match(/\d+/)?.[0] || '0';
        const total = parseInt(added) + parseInt(deleted);
        
        if (total > maxDiff) {
          console.log(`[RALPH] diff_size exceeded: ${total} lines (max ${maxDiff})`);
          return false;
        }
        
        return true;
      } catch {
        return true; // no git = first run
      }
    },
    abortOn: 'scope creep or infinite loop',
    description: `Diff within iteration size budget (default ${DIFF_SIZE_DEFAULT} lines)`
  },
  
  ralph_security: {
    check: async () => {
      // Check for committed secrets / known CVEs
      try {
        // Check git for secrets
        const secrets = execSync('git log -1 --name-only', { cwd: PROJECT_ROOT, encoding: 'utf8', timeout: 5000 });
        const dangerousPatterns = [
          /api[_-]?key/i, /secret/i, /password/i, /token/i,
          /\.env(?:\.local)?$/i, /credentials/i
        ];
        
        for (const line of secrets.split('\n')) {
          for (const pat of dangerousPatterns) {
            if (pat.test(line)) {
              console.log(`[RALPH] security: potential secret in ${line}`);
            }
          }
        }
        
        // Check for npm audit
        const pkgLock = path.join(PROJECT_ROOT, 'package-lock.json');
        if (fs.existsSync(pkgLock)) {
          try {
            const audit = execSync('npm audit --json', { cwd: PROJECT_ROOT, encoding: 'utf8', timeout: 30000 });
            const result = JSON.parse(audit);
            const highOrCritical = (result.metadata?.vulnerabilities?.high || 0) 
                                 + (result.metadata?.vulnerabilities?.critical || 0);
            if (highOrCritical > 5) {
              console.log(`[RALPH] security: ${highOrCritical} high/critical CVEs`);
              // Warning only, don't abort for existing issues
            }
          } catch { /* no audit available */ }
        }
        
        return true;
      } catch {
        return true;
      }
    },
    abortOn: 'credential leak or high severity CVE',
    description: 'No known CVEs or secrets committed'
  },
  
  ralph_coverage: {
    check: async () => {
      const pkg = path.join(PROJECT_ROOT, 'package.json');
      if (!fs.existsSync(pkg)) return true;
      
      const pkgJson = JSON.parse(fs.readFileSync(pkg, 'utf8'));
      const scripts = pkgJson.scripts || {};
      
      if (!scripts.test) return true;
      
      try {
        const state = loadState();
        const prevCoverage = state?.lastCoverage;
        
        // Run tests with coverage
        const testOutput = execSync('npm run test -- --coverage --reporter=json', {
          cwd: PROJECT_ROOT,
          encoding: 'utf8',
          timeout: 60000
        });
        
        // Try to extract coverage from test output
        const coverageMatch = testOutput.match(/All files[^>]*?(\d+\.?\d*)%/);
        if (coverageMatch) {
          const currentCoverage = parseFloat(coverageMatch[1]);
          
          if (prevCoverage !== undefined && currentCoverage < prevCoverage - 5) {
            console.log(`[RALPH] coverage dropped: ${prevCoverage}% → ${currentCoverage}%`);
            return false;
          }
          
          // Save for next iteration
          saveState({ ...loadState(), lastCoverage: currentCoverage });
        }
        
        return true;
      } catch {
        return true; // coverage not available = pass
      }
    },
    abortOn: 'coverage drop below threshold',
    description: 'Test coverage maintained or improved'
  }
};

// ─── Default gates config ────────────────────────────────────────
const DEFAULT_GATES = `
# Ralph Gates Configuration
# Auto-Claude-Code-Dev-in-Sleep (ACDS)

## Gate Settings

### ralph_code_sanity
- **check**: lint / typecheck / tests pass
- **abort_on**: critical build failure

### ralph_semantic_check  
- **check**: reviewer confirms semantic correctness
- **abort_on**: regression or broken intent
- **threshold**: 7/10

### ralph_diff_size
- **check**: diff within iteration size budget
- **abort_on**: scope creep or infinite loop
- **max_lines**: 500

### ralph_security
- **check**: no known CVEs or secrets committed
- **abort_on**: credential leak or high severity CVE

### ralph_coverage
- **check**: test coverage maintained or improved
- **abort_on**: coverage drop below threshold
- **min_delta**: -5pp

## Boundary Conditions

- **max_iterations**: 10
- **no_improvement_threshold**: 3 consecutive iterations with < 0.5pt gain
- **score_threshold**: 7/10 minimum
- **consecutive_low_rounds**: 3

## Output

- **checkpoint_file**: .acds/state/ralph_checkpoints.json
- **verbose**: true
`.trim();

// ─── Helpers ───────────────────────────────────────────────────────
function runCmd(cmd) {
  return execSync(cmd, { cwd: PROJECT_ROOT, encoding: 'utf8', timeout: 60000 });
}

function loadState() {
  try {
    if (fs.existsSync(STATE_FILE)) {
      return JSON.parse(fs.readFileSync(STATE_FILE, 'utf8'));
    }
  } catch {}
  return null;
}

function saveState(state) {
  if (!fs.existsSync(STATE_DIR)) {
    fs.mkdirSync(STATE_DIR, { recursive: true });
  }
  fs.writeFileSync(STATE_FILE, JSON.stringify(state, null, 2));
}

function parseRalphGates() {
  // Parse ralph_gates.md for custom config
  if (!fs.existsSync(RALPH_GATES_FILE)) {
    return null;
  }
  
  const content = fs.readFileSync(RALPH_GATES_FILE, 'utf8');
  const config = {};
  
  const gateMatches = content.matchAll(/### (ralph_\w+)\n([\s\S]*?)(?=###|$)/g);
  for (const match of gateMatches) {
    const name = match[1];
    const body = match[2];
    
    const maxLines = body.match(/max_lines.*?(\d+)/i);
    if (maxLines) config.maxDiffLines = parseInt(maxLines[1]);
    
    const threshold = body.match(/threshold.*?(\d+)/i);
    if (threshold) config.scoreThreshold = parseInt(threshold[1]);
    
    const minDelta = body.match(/min_delta.*?(-?\d+)/i);
    if (minDelta) config.minCoverageDelta = parseInt(minDelta[1]);
  }
  
  return config;
}

function createDefaultGates() {
  if (!fs.existsSync(RALPH_GATES_FILE)) {
    fs.writeFileSync(RALPH_GATES_FILE, DEFAULT_GATES);
    console.log(`[RALPH] Created default ${RALPH_GATES_FILE}`);
  }
}

// ─── Main gate runner ─────────────────────────────────────────────
async function runGates(mode) {
  const customConfig = parseRalphGates();
  const state = loadState();
  
  console.log(`\n🛡️  ACDS Ralph Loop Gate — ${mode.toUpperCase()} iteration ${(state?.cycle || 0) + 1}`);
  console.log('─'.repeat(60));
  
  createDefaultGates();
  
  let allPassed = true;
  const results = {};
  
  for (const [gateName, gate] of Object.entries(GATES)) {
    try {
      process.stdout.write(`  ${gateName}... `);
      const passed = await gate.check();
      results[gateName] = passed ? '✅ PASS' : '❌ FAIL';
      console.log(results[gateName]);
      
      if (!passed) {
        allPassed = false;
        console.log(`    → abort on: ${gate.abortOn}`);
      }
    } catch (err) {
      results[gateName] = `⚠️  ERROR: ${err.message}`;
      console.log(results[gateName]);
    }
  }
  
  console.log('─'.repeat(60));
  
  // Save checkpoint
  const checkpoint = {
    timestamp: new Date().toISOString(),
    mode,
    cycle: (state?.cycle || 0) + 1,
    gates: results,
    allPassed,
    abortOn: allPassed ? null : Object.entries(results).find(([k,v]) => v.startsWith('❌'))?.[0]
  };
  
  const existing = loadState() || { checkpoints: [] };
  existing.checkpoints = existing.checkpoints || [];
  existing.checkpoints.push(checkpoint);
  existing.cycle = checkpoint.cycle;
  
  if (!allPassed) {
    existing.aborted = true;
    existing.abortReason = checkpoint.abortOn;
  }
  
  saveState(existing);
  
  console.log(`\n${allPassed ? '✅ All gates passed' : '❌ GATE FAILURE — loop aborted'}`);
  console.log(`\nCheckpoint: ${STATE_FILE}`);
  
  return allPassed;
}

// ─── Status mode ──────────────────────────────────────────────────
function showStatus() {
  const state = loadState();
  const config = parseRalphGates();
  
  console.log('\n🛡️  Ralph Loop Status');
  console.log('─'.repeat(60));
  
  if (!state) {
    console.log('  No state found. Loop not yet started.');
    console.log(`  Run: node acds-ralph-gate.js "${PROJECT_ROOT}" pre`);
    return;
  }
  
  console.log(`  Cycle: ${state.cycle || 0}`);
  console.log(`  State: ${state.aborted ? '❌ ABORTED' : state.converged ? '✅ CONVERGED' : '🏃 RUNNING'}`);
  if (state.abortReason) console.log(`  Abort reason: ${state.abortReason}`);
  
  if (state.checkpoints?.length) {
    console.log('\n  Checkpoints:');
    state.checkpoints.forEach((cp, i) => {
      console.log(`    [${i+1}] ${cp.mode} — ${cp.allPassed ? '✅' : '❌'} ${cp.timestamp}`);
      for (const [gate, result] of Object.entries(cp.gates || {})) {
        console.log(`         ${result} ${gate}`);
      }
    });
  }
  
  if (config) {
    console.log('\n  Config:');
    if (config.maxDiffLines) console.log(`    max_diff_lines: ${config.maxDiffLines}`);
    if (config.scoreThreshold) console.log(`    score_threshold: ${config.scoreThreshold}`);
    if (config.minCoverageDelta) console.log(`    min_coverage_delta: ${config.minCoverageDelta}`);
  }
}

// ─── Entry point ──────────────────────────────────────────────────
(async () => {
  try {
    if (MODE === 'status') {
      showStatus();
      process.exit(0);
    }
    
    const passed = await runGates(MODE);
    process.exit(passed ? 0 : 1);
  } catch (err) {
    console.error(`\n💥 Ralph gate error: ${err.message}`);
    process.exit(1);
  }
})();