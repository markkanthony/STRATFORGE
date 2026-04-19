# AI Loop Implementation Specification

## Overview

The `ai_loop.py` module implements an AI-driven optimization loop using Anthropic's Claude to iteratively improve trading strategy performance.

## Architecture

### Core Class: `AIOptimizerLoop`

Main orchestrator that manages:
- State tracking across iterations
- AI proposal generation
- Validation and duplicate prevention
- Change application
- Stop criteria evaluation

## Allowed Config Edits Enforcement

###  Rule: Only `config.strategy` is Editable

**Implementation:**
1. **Prompt Construction** (`_build_prompt`):
   - Only shows `config.strategy` section to AI
   - Explicitly instructs: "Only edit config.strategy section"
   - Lists forbidden sections: backtest, windows, time, visualization, risk constraints

2. **Proposal Parsing** (`_parse_ai_response`):
   - Expects only strategy section in config field

3. **Application** (`_apply_proposal`):
   - Loads full config
   - **Only updates** `config["strategy"]` section
   - Preserves all other sections unchanged
   - Writes back complete config

4. **Validation** (`_validate_proposal`):
   - Checks proposal structure
   - Ensures strategy code is valid Python (ast.parse)
   - Verifies required functions exist

**Result:** AI physically cannot modify other config sections because:
- It doesn't see them in the prompt
- The apply function only overwrites strategy section
- All other sections are preserved from original config

## Duplicate Detection Logic

### Hash-Based Exact Matching

**Implementation** (`_check_duplicate`):

```python
# Combines config.strategy + strategy.py content
config_str = json.dumps(proposed_config["strategy"], sort_keys=True)
combined = config_str + "|" + proposed_strategy
config_hash = hashlib.sha256(combined.encode("utf-8")).hexdigest()
```

**Tracking:**
- `seen_hashes`: Set of SHA256 hashes
- Hash computed from: `config.strategy JSON + "|" + strategy.py code`
- Checks if hash exists before applying changes
- Logs duplicate rejections to diff file

**Benefits:**
- Exact match detection
- Prevents identical retries
- Fast O(1) lookup
- Cryptographically secure hashing

## Stop Criteria Logic

### Four Stop Conditions

**1. Success Criteria** (Target Achieved):
```python
if (val_sharpe > 2.0 and 
    val_drawdown > -0.15 and 
    abs(train_sharpe - val_sharpe) < 1.0 and 
    val_trades >= 50):
    return "Success criteria met"
```

**2. Plateau Detection** (No Improvement):
```python
if len(history) >= 8:
    recent_8_sharpes = [sharpe for run in last_8_runs if trades >= 30]
    if max(sharpes) - min(sharpes) < 0.1:
        return "Plateau detected"
```
- Looks at last 8 runs
- Ignores runs with < 30 trades
- Stops if max improvement < 0.1

**3. Overfit Detection** (Train/Val Divergence):
```python
if len(history) >= 3:
    recent_3 = history[-3:]
    overfit_count = sum(1 for r in recent_3 
                       if r.train_sharpe - r.val_sharpe > 1.5)
    if overfit_count >= 3:
        return "Overfit detected"
```
- Checks last 3 runs
- Counts runs with train-val gap > 1.5
- Stops if all 3 are overfitting

**4. Hard Cap**:
```python
while iteration < max_iterations:  # default: 50
```

## Performance Tracking

### State Maintained

```python
self.history: List[Dict]  # All run results
self.best_val_sharpe: float  # Best validation Sharpe seen
self.iterations_since_improvement: int  # Plateau tracking
self.seen_hashes: set  # Duplicate prevention
```

### Update Logic (`_update_tracking`):

```python
if current_val_sharpe > best_val_sharpe:
    best_val_sharpe = current_val_sharpe
    iterations_since_improvement = 0
else:
    iterations_since_improvement += 1
```

### History Entry Format:

```python
{
    "run": int,
    "timestamp": str,
    "train_sharpe": float,
    "val_sharpe": float,
    "train_drawdown": float,
    "val_drawdown": float,
    "train_trades": int,
    "val_trades": int
}
```

## AI Prompting Strategy

### Tier 1: Config-Only Changes (Preferred)

```
change_type: "config"
config: {...strategy section only...}
strategy_code: null
```

### Tier 2: Strategy Rewrite (When Needed)

```
change_type: "strategy" or "both"
config: {...optional config changes...}
strategy_code: "...full strategy.py..."
```

### Prompt Structure:

1. **Goal Statement**: Improve val_sharpe while maintaining constraints
2. **Current State**: Best sharpe, iterations since improvement
3. **Recent History**: Last 5 runs with metrics
4. **Latest Results**: Full metrics from last run
5. **Current Config**: Only strategy section shown
6. **Current Strategy**: Full strategy.py code
7. **Rules**: Explicit constraints and preferences
8. **Response Format**: JSON schema

## Diff Logging

### File: `results/run_NNN.diff.json`

**Structure:**
```json
{
  "run": 1,
  "timestamp": "2024-04-19T...",
  "hypothesis": "Increasing EMA periods should reduce