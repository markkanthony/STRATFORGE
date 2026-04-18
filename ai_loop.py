"""
ai_loop.py - AI Optimizer Loop using Anthropic

This module implements the AI optimization loop that:
1. Reads latest backtest results
2. Analyzes performance trends
3. Proposes minimal targeted changes (config first, strategy if needed)
4. Validates changes before applying
5. Prevents duplicates
6. Stops based on success/plateau/overfit criteria

STRICT RULES:
- Only edits config.strategy section
- Never edits backtest, windows, time, visualization, or risk constraints
- Validates all changes before writing
- Uses exact-match hashing to prevent duplicates
- Logs all changes and reasoning
"""

import json
import hashlib
import ast
import copy
import importlib
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone
import yaml

# Anthropic client
try:
    from anthropic import Anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False
    Anthropic = None


class AIOptimizerLoop:
    """
    AI-driven optimization loop for StratForge.
    
    Uses Anthropic's Claude to iteratively improve strategy performance
    by making minimal, targeted changes to config.strategy or strategy.py.
    """
    
    def __init__(self, api_key: Optional[str] = None, max_iterations: int = 50):
        """
        Initialize AI optimizer loop.
        
        Args:
            api_key: Anthropic API key (reads from env if not provided)
            max_iterations: Maximum number of optimization iterations
        """
        if not ANTHROPIC_AVAILABLE:
            raise ImportError("anthropic package not installed. Run: pip install anthropic")
        
        self.client = Anthropic(api_key=api_key) if api_key else Anthropic()
        self.max_iterations = max_iterations
        self.results_dir = Path("results")
        self.config_path = Path("config.yaml")
        self.strategy_path = Path("strategy.py")
        
        # Tracking state
        self.history: List[Dict] = []
        self.best_val_sharpe: float = float('-inf')
        self.iterations_since_improvement: int = 0
        self.seen_hashes: set = set()
        self.consecutive_overfit_count: int = 0
        
    def run(self) -> Dict[str, Any]:
        """
        Run the AI optimization loop.
        
        Returns:
            Summary of optimization run
        """
        print("=" * 80)
        print("StratForge AI Optimization Loop")
        print("=" * 80)
        
        # Load initial state
        print("\n[1] Loading initial state...")
        try:
            self._load_history()
            print(f"  ✓ Loaded {len(self.history)} previous runs")
        except Exception as e:
            print(f"  ⚠ No previous history found: {e}")
        
        # Main optimization loop
        iteration = 0
        stop_reason = None
        
        while iteration < self.max_iterations:
            iteration += 1
            print(f"\n{'=' * 80}")
            print(f"Iteration {iteration}/{self.max_iterations}")
            print(f"{'=' * 80}")
            
            # Check stop criteria
            stop_reason = self._check_stop_criteria()
            if stop_reason:
                print(f"\n✓ Stopping: {stop_reason}")
                break
            
            # Get AI proposal
            print(f"\n[{iteration}.1] Requesting AI proposal...")
            try:
                proposal = self._get_ai_proposal()
                print(f"  ✓ Received proposal: {proposal['change_type']}")
                print(f"  Hypothesis: {proposal['hypothesis'][:100]}...")
            except Exception as e:
                print(f"  ✗ Failed to get proposal: {e}")
                stop_reason = f"AI proposal failed: {e}"
                break
            
            # Check for duplicates
            print(f"\n[{iteration}.2] Checking for duplicates...")
            is_duplicate, config_hash = self._check_duplicate(proposal)
            if is_duplicate:
                print(f"  ⚠ Duplicate configuration detected, skipping...")
                self._log_diff(None, proposal, duplicate=True)
                continue
            print(f"  ✓ New configuration (hash: {config_hash[:8]}...)")
            
            # Validate proposal
            print(f"\n[{iteration}.3] Validating proposal...")
            valid, errors = self._validate_proposal(proposal)
            if not valid:
                print(f"  ✗ Validation failed:")
                for error in errors:
                    print(f"    - {error}")
                self._log_diff(None, proposal, validation_errors=errors)
                continue
            print(f"  ✓ Proposal valid")
            
            # Apply changes
            print(f"\n[{iteration}.4] Applying changes...")
            try:
                self._apply_proposal(proposal)
                self.seen_hashes.add(config_hash)
                print(f"  ✓ Changes applied")
            except Exception as e:
                print(f"  ✗ Failed to apply changes: {e}")
                continue
            
            # Run backtest
            print(f"\n[{iteration}.5] Running backtest...")
            try:
                import run
                importlib.reload(run)
                run_data = run.run_backtest_full()
                print(f"  ✓ Backtest complete")
            except Exception as e:
                print(f"  ✗ Backtest failed: {e}")
                stop_reason = f"Backtest execution failed: {e}"
                break
            
            # Log diff
            self._log_diff(run_data, proposal)
            
            # Update tracking
            self._update_tracking(run_data)
            
        # Generate summary
        summary = self._generate_summary(iteration, stop_reason)
        return summary
    
    def _load_history(self) -> None:
        """Load previous run history from history.jsonl"""
        history_path = self.results_dir / "history.jsonl"
        if not history_path.exists():
            return
        
        with open(history_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    self.history.append(json.loads(line))
        
        # Find best validation sharpe
        for entry in self.history:
            val_sharpe = entry.get("val_sharpe")
            if val_sharpe and val_sharpe > self.best_val_sharpe:
                self.best_val_sharpe = val_sharpe
    
    def _check_stop_criteria(self) -> Optional[str]:
        """
        Check if any stop criteria are met.
        
        Returns:
            Stop reason if criteria met, None otherwise
        """
        # No runs yet
        if len(self.history) == 0:
            return None
        
        latest = self.history[-1]
        
        # Success criteria
        val_sharpe = latest.get("val_sharpe", float('-inf'))
        val_drawdown = latest.get("val_drawdown", 0)
        val_trades = latest.get("val_trades", 0)
        train_sharpe = latest.get("train_sharpe", 0)
        
        if (val_sharpe > 2.0 and 
            val_drawdown > -0.15 and 
            abs(train_sharpe - val_sharpe) < 1.0 and 
            val_trades >= 50):
            return "Success criteria met"
        
        # Plateau detection
        if len(self.history) >= 8:
            recent_8 = self.history[-8:]
            sharpes = [r.get("val_sharpe", float('-inf')) for r in recent_8 
                      if r.get("val_trades", 0) >= 30]
            if sharpes:
                max_improvement = max(sharpes) - min(sharpes)
                if max_improvement < 0.1:
                    return "Plateau detected (no improvement >= 0.1 in last 8 runs)"
        
        # Overfit detection
        if len(self.history) >= 3:
            recent_3 = self.history[-3:]
            overfit_count = 0
            for r in recent_3:
                t_sharpe = r.get("train_sharpe", 0)
                v_sharpe = r.get("val_sharpe", 0)
                if t_sharpe - v_sharpe > 1.5:
                    overfit_count += 1
            
            if overfit_count >= 3:
                return "Overfit detected (train-val gap > 1.5 for 3 consecutive runs)"
        
        return None
    
    def _get_ai_proposal(self) -> Dict[str, Any]:
        """
        Get AI proposal for next optimization step.
        
        Returns:
            Proposal dictionary with hypothesis, change_type, config, strategy_code, reasoning
        """
        # Build context
        context = self._build_context()
        
        # Build prompt
        prompt = self._build_prompt(context)
        
        # Call Anthropic API
        message = self.client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=4096,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        
        # Parse response
        response_text = message.content[0].text
        
        # Extract JSON from response
        proposal = self._parse_ai_response(response_text)
        
        return proposal
    
    def _build_context(self) -> Dict[str, Any]:
        """Build context for AI prompt"""
        # Load current config
        with open(self.config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        
        # Load current strategy
        with open(self.strategy_path, "r", encoding="utf-8") as f:
            strategy_code = f.read()
        
        # Get recent history (last 5 runs)
        recent_history = self.history[-5:] if len(self.history) > 0 else []
        
        # Load latest results if available
        latest_path = self.results_dir / "latest.json"
        latest_results = None
        if latest_path.exists():
            with open(latest_path, "r", encoding="utf-8") as f:
                latest_results = json.load(f)
        
        return {
            "config": config,
            "strategy_code": strategy_code,
            "recent_history": recent_history,
            "latest_results": latest_results,
            "best_val_sharpe": self.best_val_sharpe,
            "iterations_since_improvement": self.iterations_since_improvement
        }
    
    def _build_prompt(self, context: Dict[str, Any]) -> str:
        """Build prompt for AI"""
        prompt = f"""You are an expert quantitative trading strategy optimizer for StratForge.

Your goal is to improve validation Sharpe ratio while maintaining:
- Low drawdown (< 15%)
- Good train/validation consistency (gap < 1.0)
- Sufficient trades (>= 50)

CURRENT STATE:
- Best validation Sharpe so far: {context['best_val_sharpe']:.2f}
- Iterations since improvement: {context['iterations_since_improvement']}

RECENT HISTORY (last 5 runs):
{json.dumps(context['recent_history'], indent=2)}

LATEST RESULTS:
{json.dumps(context['latest_results'], indent=2) if context['latest_results'] else "No results yet"}

CURRENT CONFIG (strategy section only):
{yaml.dump(context['config'].get('strategy', {}), default_flow_style=False)}

CURRENT STRATEGY CODE:
```python
{context['strategy_code']}
```

RULES:
1. Prefer config-only changes (Tier 1) over strategy rewrites (Tier 2)
2. Make minimal, targeted changes
3. Only edit config.strategy section (never backtest, windows, time, visualization, risk constraints)
4. If rewriting strategy, keep same function signature and output format
5. Base decisions on validation metrics, not train metrics
6. Avoid overfitting

RESPOND WITH VALID JSON ONLY (no markdown, no explanation outside JSON):
{{
  "hypothesis": "Clear hypothesis about what change will improve performance and why",
  "change_type": "config" | "strategy" | "both",
  "config": {{...only include config.strategy section with changes...}},
  "strategy_code": "...full strategy.py code if rewriting, otherwise null...",
  "reasoning": "Brief explanation of why this change should help"
}}"""
        
        return prompt
    
    def _parse_ai_response(self, response_text: str) -> Dict[str, Any]:
        """
        Parse AI response and extract JSON.
        
        Args:
            response_text: Raw response from AI
            
        Returns:
            Parsed proposal dictionary
        """
        # Try to find JSON in response
        import re
        
        # Look for JSON block
        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
        if not json_match:
            raise ValueError("No JSON found in AI response")
        
        json_str = json_match.group(0)
        proposal = json.loads(json_str)
        
        # Validate required fields
        required = ["hypothesis", "change_type", "reasoning"]
        for field in required:
            if field not in proposal:
                raise ValueError(f"Missing required field: {field}")
        
        # Ensure config and strategy_code exist
        if "config" not in proposal:
            proposal["config"] = None
        if "strategy_code" not in proposal:
            proposal["strategy_code"] = None
        
        return proposal
    
    def _check_duplicate(self, proposal: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Check if proposal is duplicate.
        
        Returns:
            (is_duplicate, config_hash)
        """
        # Load current config and strategy
        with open(self.config_path, "r", encoding="utf-8") as f:
            current_config = yaml.safe_load(f)
        
        with open(self.strategy_path, "r", encoding="utf-8") as f:
            current_strategy = f.read()
        
        # Build proposed config
        proposed_config = copy.deepcopy(current_config)
        if proposal.get("config"):
            proposed_config["strategy"] = proposal["config"]
        
        # Build proposed strategy
        proposed_strategy = proposal.get("strategy_code") or current_strategy
        
        # Compute hash
        config_str = json.dumps(proposed_config.get("strategy", {}), sort_keys=True)
        combined = config_str + "|" + proposed_strategy
        config_hash = hashlib.sha256(combined.encode("utf-8")).hexdigest()
        
        is_duplicate = config_hash in self.seen_hashes
        return is_duplicate, config_hash
    
    def _validate_proposal(self, proposal: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Validate AI proposal before applying.
        
        Returns:
            (is_valid, error_messages)
        """
        errors = []
        
        # Validate change_type
        if proposal["change_type"] not in ["config", "strategy", "both"]:
            errors.append(f"Invalid change_type: {proposal['change_type']}")
        
        # Validate config changes
        if proposal.get("config"):
            # Check that only strategy section is modified
            # This is enforced by only accepting config.strategy in the proposal
            # Additional validation: ensure no forbidden fields
            forbidden_keys = ["mode", "indicators", "patterns"]  # These are allowed
            # But we need to make sure structure is valid
            if not isinstance(proposal["config"], dict):
                errors.append("Config must be a dictionary")
        
        # Validate strategy code if provided
        if proposal.get("strategy_code"):
            try:
                ast.parse(proposal["strategy_code"])
            except SyntaxError as e:
                errors.append(f"Strategy code syntax error: {e}")
            
            # Check for required function
            if "def generate_signals" not in proposal["strategy_code"]:
                errors.append("Strategy code must contain generate_signals function")
        
        return (len(errors) == 0, errors)
    
    def _apply_proposal(self, proposal: Dict[str, Any]) -> None:
        """Apply validated proposal to config and/or strategy"""
        # Apply config changes
        if proposal.get("config"):
            with open(self.config_path, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)
            
            # Update only strategy section
            config["strategy"] = proposal["config"]
            
            with open(self.config_path, "w", encoding="utf-8") as f:
                yaml.dump(config, f, default_flow_style=False, sort_keys=False)
        
        # Apply strategy changes
        if proposal.get("strategy_code"):
            with open(self.strategy_path, "w", encoding="utf-8") as f:
                f.write(proposal["strategy_code"])
    
    def _update_tracking(self, run_data: Dict[str, Any]) -> None:
        """Update tracking state after run"""
        val_metrics = run_data.get("validation", {}).get("metrics", {})
        val_sharpe = val_metrics.get("performance", {}).get("sharpe")
        
        if val_sharpe and val_sharpe > self.best_val_sharpe:
            self.best_val_sharpe = val_sharpe
            self.iterations_since_improvement = 0
        else:
            self.iterations_since_improvement += 1
        
        # Update history
        self.history.append({
            "run": run_data.get("run"),
            "timestamp": run_data.get("timestamp"),
            "train_sharpe": run_data.get("train", {}).get("metrics", {}).get("performance", {}).get("sharpe"),
            "val_sharpe": val_sharpe,
            "train_drawdown": run_data.get("train", {}).get("metrics", {}).get("risk", {}).get("max_drawdown"),
            "val_drawdown": val_metrics.get("risk", {}).get("max_drawdown"),
            "train_trades": run_data.get("train", {}).get("metrics", {}).get("trades", {}).get("num_trades"),
            "val_trades": val_metrics.get("trades", {}).get("num_trades")
        })
    
    def _log_diff(self, run_data: Optional[Dict], proposal: Dict[str, Any], 
                  duplicate: bool = False, validation_errors: Optional[List[str]] = None) -> None:
        """Log proposal diff to results/run_NNN.diff.json"""
        # Determine run number
        if run_data:
            run_number = run_data.get("run")
        else:
            # Get next run number from results dir
            existing_runs = []
            for file in self.results_dir.glob("run_*.json"):
                try:
                    num = int(file.stem.split("_")[1])
                    existing_runs.append(num)
                except (IndexError, ValueError):
                    continue
            run_number = max(existing_runs) + 1 if existing_runs else 1
        
        # Build diff data
        diff_data = {
            "run": run_number,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "hypothesis": proposal.get("hypothesis"),
            "change_type": proposal.get("change_type"),
            "reasoning": proposal.get("reasoning"),
            "duplicate": duplicate,
            "validation_errors": validation_errors,
            "config_changes": proposal.get("config"),
            "strategy_changed": bool(proposal.get("strategy_code"))
        }
        
        # Save diff file
        diff_path = self.results_dir / f"run_{run_number:03d}.diff.json"
        diff_path.parent.mkdir(parents=True, exist_ok=True)
        with open(diff_path, "w", encoding="utf-8") as f:
            json.dump(diff_data, f, indent=2, ensure_ascii=False)
    
    def _generate_summary(self, iterations: int, stop_reason: Optional[str]) -> Dict[str, Any]:
        """Generate optimization summary"""
        summary = {
            "total_iterations": iterations,
            "stop_reason": stop_reason or "Max iterations reached",
            "best_val_sharpe": self.best_val_sharpe,
            "final_history_length": len(self.history),
            "unique_configurations_tried": len(self.seen_hashes)
        }
        
        print("\n" + "=" * 80)
        print("OPTIMIZATION SUMMARY")
        print("=" * 80)
        print(f"Total iterations: {summary['total_iterations']}")
        print(f"Stop reason: {summary['stop_reason']}")
        print(f"Best validation Sharpe: {summary['best_val_sharpe']:.3f}")
        print(f"Unique configurations: {summary['unique_configurations_tried']}")
        print("=" * 80)
        
        return summary


def run_optimization_loop(api_key: Optional[str] = None, max_iterations: int = 50) -> Dict[str, Any]:
    """
    Main entry point for AI optimization loop.
    
    Args:
        api_key: Anthropic API key (optional, reads from env if not provided)
        max_iterations: Maximum number of optimization iterations
        
    Returns:
        Optimization summary
    """
    loop = AIOptimizerLoop(api_key=api_key, max_iterations=max_iterations)
    return loop.run()


if __name__ == "__main__":
    try:
        summary = run_optimization_loop()
        print("\n✓ Optimization complete")
    except Exception as e:
        print(f"\n✗ Optimization failed: {e}")
        import traceback
        traceback.print_exc()
