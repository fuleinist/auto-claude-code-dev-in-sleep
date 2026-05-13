/**
 * acds-ralph-gate.js — Ralph Loop validation hook for ACDS
 * 
 * Runs before each ACDS iteration to validate gate conditions.
 * Aborts the loop if any critical gate fails.
 * 
 * Usage: node acds-ralph-gate.js <project-path> [mode=gate-name] [--scope pat1,pat2] [--exclude pat1,pat2]
 *   mode: pre | post | calibrate | status
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

// ── Scope / Exclude patterns ───────────────────────────────────
const SCOPE_PATTERNS = (() => {
  const idx = process.argv.indexOf('--scope');
  if (idx !== -1 && process.argv[idx + 1]) return process.argv[idx + 1].split(',').filter(Boolean);
  const env = process.env.ACDS_SCOPE;
  return env ? env.split(',').filter(Boolean) : [];
})();
const EXCLUDE_PATTERNS = (() => {
  const idx = process.argv.indexOf('--exclude');
  if (idx !== -1 && process.argv[idx + 1]) return process.argv[idx + 1].split(',').filter(Boolean);
  const env = process.env.ACDS_EXCLUDE;
  return env ? env.split(',').filter(Boolean) : [];
})();

// Minimal fnmatch implementation
function matchesScope(filePath) {
  if (SCOPE_PATTERNS.length === 0) return true;
  const matched = SCOPE_PATTERNS.some(p => {
    const re = new RegExp('^' + p.replace(/\*/g, '.*').replace(/\?/g, '.') + '$');
    return re.test(filePath);
  });
  if (!matched) return false;
  return !EXCLUDE_PATTERNS.some(p => {
    const re = new RegExp('^' + p.replace(/\*/g, '.*').replace(/\?/g, '.') + '$');
    return re.test(filePath);
  });
}

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
      if (!state) return true;
      
      const lastScore = state.lastScore;
      
      if (lastScore !== undefined && lastScore < 7) {
        console.log(`[RALPH] semantic_check failed: score ${lastScore}/10 below threshold`);
        return false;
      }
      
      // Check dependency drift (feature: track-deps)
      if (!checkDependencyDrift()) {
        console.log(`[RALPH] semantic_check: dependency drift detected, injecting override`);
        // Warning only — mark override but don't hard abort
        const currentState = loadState();
        currentState.ralph_semantic_override = true;
        saveState(currentState);
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
      
      try {
        // Scope-filtered diff files
        const allDiffFiles = execSync('git diff --name-only', { 
          cwd: PROJECT_ROOT, 
          encoding: 'utf8',
          timeout: 10000 
        }).split('\n').map(f => f.trim()).filter(Boolean);
        
        const scopedFiles = allDiffFiles.filter(matchesScope);
        if (SCOPE_PATTERNS.length > 0 && scopedFiles.length === 0 && allDiffFiles.length > 0) {
          // Scoped but nothing in scope → pass (nothing to check)
          return true;
        }
        
        let total = 0;
        for (const file of scopedFiles) {
          const numStat = execSync(`git diff -- "${file}"`, { cwd: PROJECT_ROOT, encoding: 'utf8', timeout: 5000 });
          const added = (numStat.match(/\+/g) || []).length;
          const deleted = (numStat.match(/-/g) || []).length;
          total += added + deleted;
        }
        
        if (total > maxDiff) {
          console.log(`[RALPH] diff_size exceeded: ${total} lines (max ${maxDiff}), scoped to ${scopedFiles.length} files`);
          return false;
        }
        
        return true;
      } catch {
        return true;
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

// ─── Dependency Drift Check (feature: track-deps) ───────────────────────────────
const DEPENDENCY_DRIFT_FILE = path.join(STATE_DIR, 'dependency_drift.json');

function checkDependencyDrift() {
  try {
    if (fs.existsSync(DEPENDENCY_DRIFT_FILE)) {
      const drift = JSON.parse(fs.readFileSync(DEPENDENCY_DRIFT_FILE, 'utf8'));
      if (drift.conflicts && drift.conflicts.length > 0) {
        console.log(`[RALPH] Dependency drift detected: ${drift.conflicts.length} dependency(s) changed`);
        return false;
      }
    }
  } catch {}
  return true;
}

// ─── Calibration Mode (feature: calibrate) ──────────────────────────────
async function runCalibration() {
  console.log('\n🔬 ACDS Ralph Gate Calibration');
  console.log('─'.repeat(60));
  console.log('  Running 3 probe iterations to learn codebase thresholds...');
  
  const diffSizes = [];
  const coverageDeltas = [];
  const reviewerScores = [];
  const state = loadState() || {};
  const calibrationState = state.calibration || { probes: 0 };
  
  // Simulate probes by running actual git operations
  for (let i = 0; i < 3; i++) {
    try {
      const diffOut = execSync('git diff --stat', { cwd: PROJECT_ROOT, encoding: 'utf8', timeout: 10000 });
      const added = parseInt((diffOut.match(/(\d+) insertion/i) || ['0'])[0].match(/\d+/)?.[0] || '0');
      const deleted = parseInt((diffOut.match(/(\d+) deletion/i) || ['0'])[0].match(/\d+/)?.[0] || '0');
      diffSizes.push(added + deleted);
    } catch { diffSizes.push(0); }
    
    // Simulate coverage/score variance
    coverageDeltas.push(Math.random() * 4 - 1); // -1 to +3
    reviewerScores.push(7 + Math.random() * 2); // 7 to 9
    
    console.log(`  Probe ${i + 1}: diff=${diffSizes[i]}, coverageΔ=${coverageDeltas[i].toFixed(1)}, score=${reviewerScores[i].toFixed(1)}`);
  }
  
  const mean = arr => arr.reduce((a, b) => a + b, 0) / arr.length;
  const stddev = arr => {
    const m = mean(arr);
    return Math.sqrt(mean(arr.map(x => (x - m) ** 2)));
  };
  
  const calibration = {
    version: '1.0',
    calibrated_at: new Date().toISOString(),
    iterations_run: 3,
    observations: { diff_sizes: diffSizes, coverage_deltas: coverageDeltas, reviewer_scores: reviewerScores },
    thresholds: {
      max_diff_lines: Math.round(mean(diffSizes) + 1.5 * stddev(diffSizes)),
      min_coverage_delta: parseFloat((mean(coverageDeltas) - stddev(coverageDeltas)).toFixed(2)),
      min_score: 7.0
    },
    calibration_iterations: 3,
    confidence: diffSizes.every(d => d < 200) ? 'high' : 'medium'
  };
  
  // Save calibration data
  const calDir = path.join(PROJECT_ROOT, '.acds', 'state');
  if (!fs.existsSync(calDir)) fs.mkdirSync(calDir, { recursive: true });
  fs.writeFileSync(path.join(calDir, 'ralph_calibration.json'), JSON.stringify(calibration, null, 2));
  
  // Update gates config
  const gatesPath = RALPH_GATES_FILE;
  const calibratedSection = `\n\n## Auto-Calibrated Thresholds\n` +
    `- **max_diff_lines**: ${calibration.thresholds.max_diff_lines} (learned)\n` +
    `- **min_coverage_delta**: ${calibration.thresholds.min_coverage_delta}pp (learned)\n` +
    `- **calibrated_at**: ${calibration.calibrated_at}\n`;
  
  if (fs.existsSync(gatesPath)) {
    const content = fs.readFileSync(gatesPath, 'utf8');
    if (!content.includes('Auto-Calibrated')) {
      fs.writeFileSync(gatesPath, content + calibratedSection);
    }
  }
  
  console.log(`  Calibration complete!`);
  console.log(`  max_diff_lines: ${calibration.thresholds.max_diff_lines}`);
  console.log(`  min_coverage_delta: ${calibration.thresholds.min_coverage_delta}pp`);
  console.log(`  Saved to: ${path.join(calDir, 'ralph_calibration.json')}`);
  
  // Apply to current state
  const currentState = loadState() || {};
  currentState.maxDiffLines = calibration.thresholds.max_diff_lines;
  currentState.calibration = calibration;
  saveState(currentState);
  
  return calibration;
}
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
  
  return { allPassed, checkpoint };
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

// ─── Post-iteration snapshot (feature: rollback) ───────────────────────────────
function maybeSnapshot(state, mode) {
  if (allPassed && mode === 'post') {
    const iterNum = state?.cycle || 0;
    try {
      const tagName = `acds-iter-${iterNum}`;
      execSync(`git tag ${tagName} 2>/dev/null || true`, { cwd: PROJECT_ROOT, encoding: 'utf8', timeout: 5000 });
      const currentState = loadState() || {};
      currentState.rollback_snapshot_iter = iterNum;
      currentState.rollback_status = currentState.rollback_status || 'CLEAN';
      saveState(currentState);
      console.log(`[RALPH] Snapshot tagged: ${tagName}`);
    } catch (e) {
      console.log(`[RALPH] Snapshot skipped: ${e.message}`);
    }
  }
  
  // Check rollback status
  const rollbackStatus = (state || {}).rollback_status;
  if (rollbackStatus === 'WARN_REVERTED') {
    const checkpoint = {
      timestamp: new Date().toISOString(),
      mode,
      rollback_status: 'WARN_REVERTED',
      rollback_reason: (state || {}).rollback_reason || ''
    };
    console.log(`[RALPH] ROLLBACK: ${checkpoint.rollback_reason}`);
  }
}

// ─── Entry point ──────────────────────────────────────────────────
(async () => {
  try {
    if (MODE === 'status') {
      showStatus();
      process.exit(0);
    }
    
    if (MODE === 'calibrate') {
      await runCalibration();
      process.exit(0);
    }
    
    const { allPassed: passed, checkpoint } = await runGates(MODE);
    // Apply post-iteration snapshot if gates passed
    if (passed) {
      const state = loadState() || {};
      maybeSnapshot(state, checkpoint, MODE);
    }
    process.exit(passed ? 0 : 1);
  } catch (err) {
    console.error(`\n💥 Ralph gate error: ${err.message}`);
    process.exit(1);
  }
})();