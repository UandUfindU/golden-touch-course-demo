"""
BacktestResult - Data structures for backtest results and metrics.

Contains:
- Trade record
- Equity curve
- Performance metrics (Sharpe, MaxDD, etc.)
"""
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from datetime import datetime
import numpy as np


class Trade(BaseModel):
    """Single trade record."""
    entry_time: int = Field(description="Entry timestamp (ms)")
    exit_time: Optional[int] = Field(default=None, description="Exit timestamp (ms)")
    direction: str = Field(description="'long' or 'short'")
    entry_price: float = Field(description="Entry price")
    exit_price: Optional[float] = Field(default=None, description="Exit price")
    quantity: float = Field(description="Position size")
    pnl: float = Field(default=0.0, description="Profit/Loss")
    pnl_pct: float = Field(default=0.0, description="PnL percentage")
    is_closed: bool = Field(default=False, description="Whether trade is closed")
    entry_context: Optional[Dict[str, float]] = Field(default=None, description="Indicator values at entry")


class EquityPoint(BaseModel):
    """Single point on equity curve."""
    timestamp: int = Field(description="Timestamp (ms)")
    equity: float = Field(description="Total equity value")
    cash: float = Field(description="Cash balance")
    position_value: float = Field(description="Value of open positions")
    regime: str = Field(default="Normal", description="Market regime (Bull/Bear/Range)")


class PerformanceMetrics(BaseModel):
    """Backtest performance metrics."""
    # Core metrics
    total_return: float = Field(description="Total return percentage")
    annualized_return: float = Field(default=0.0, description="Annualized return")
    sharpe_ratio: float = Field(default=0.0, description="Sharpe ratio (risk-free=0)")
    sortino_ratio: float = Field(default=0.0, description="Sortino ratio")
    max_drawdown: float = Field(default=0.0, description="Maximum drawdown percentage")
    max_drawdown_duration: int = Field(default=0, description="Max drawdown duration in bars")
    win_rate: float = Field(default=0.0, description="Win rate percentage")
    profit_factor: float = Field(default=0.0, description="Profit factor (gross profit / gross loss)")
    total_trades: int = Field(default=0, description="Total number of trades")
    winning_trades: int = Field(default=0, description="Number of winning trades")
    losing_trades: int = Field(default=0, description="Number of losing trades")
    avg_win: float = Field(default=0.0, description="Average winning trade")
    avg_loss: float = Field(default=0.0, description="Average losing trade")
    largest_win: float = Field(default=0.0, description="Largest single win")
    largest_loss: float = Field(default=0.0, description="Largest single loss")
    
    # Trade quality metrics
    avg_holding_time_bars: float = Field(default=0.0, description="Average holding time in bars")
    avg_win_holding_time: float = Field(default=0.0, description="Avg holding time for winning trades")
    avg_loss_holding_time: float = Field(default=0.0, description="Avg holding time for losing trades")
    risk_reward_ratio: float = Field(default=0.0, description="Risk/Reward ratio (avg_win / abs(avg_loss))")
    
    # Advanced Analysis
    entry_analysis: Optional[Dict[str, Dict[str, float]]] = Field(
        default=None, 
        description="Stats of indicators at entry (Win vs Loss)"
    )
    regime_performance: Optional[Dict[str, float]] = Field(
        default=None,
        description="Performance breakdown by market regime"
    )
    
    # Risk metrics  
    max_consecutive_wins: int = Field(default=0, description="Max consecutive winning trades")
    max_consecutive_losses: int = Field(default=0, description="Max consecutive losing trades")
    recovery_time_bars: int = Field(default=0, description="Bars to recover from max drawdown")
    worst_single_day_pnl: float = Field(default=0.0, description="Worst single day PnL")
    commission_total: float = Field(default=0.0, description="Total commission paid")
    commission_pct_of_pnl: float = Field(default=0.0, description="Commission as % of gross profit")
    
    # Signal statistics (for LLM feedback)
    buy_signals_count: int = Field(default=0, description="Number of buy signals triggered")
    sell_signals_count: int = Field(default=0, description="Number of sell signals triggered")
    
    # Time-based breakdown (optional, can be None)
    monthly_returns: Optional[Dict[str, float]] = Field(default=None, description="Monthly return breakdown")
    top_10_wins: Optional[List[Dict[str, Any]]] = Field(default=None, description="Top 10 winning trades")
    top_10_losses: Optional[List[Dict[str, Any]]] = Field(default=None, description="Top 10 losing trades")


class BacktestResult(BaseModel):
    """Complete backtest result."""
    success: bool = Field(description="Whether backtest completed successfully")
    error: Optional[str] = Field(default=None, description="Error message if failed")
    
    # Configuration
    initial_capital: float = Field(description="Starting capital")
    commission_rate: float = Field(description="Commission rate used")
    
    # Results
    final_equity: float = Field(default=0.0, description="Final equity value")
    trades: List[Trade] = Field(default_factory=list, description="List of all trades")
    equity_curve: List[EquityPoint] = Field(default_factory=list, description="Equity curve")
    metrics: Optional[PerformanceMetrics] = Field(default=None, description="Performance metrics")
    
    # Metadata
    start_time: Optional[int] = Field(default=None, description="Backtest start timestamp")
    end_time: Optional[int] = Field(default=None, description="Backtest end timestamp")
    bars_processed: int = Field(default=0, description="Number of bars processed")

    @staticmethod
    def calculate_metrics(trades: List[Trade], equity_curve: List[EquityPoint], 
                          initial_capital: float) -> PerformanceMetrics:
        """Calculate performance metrics from trades and equity curve."""
        if not equity_curve:
            return PerformanceMetrics(total_return=0.0)
        
        # Total return
        final_equity = equity_curve[-1].equity
        total_return = (final_equity - initial_capital) / initial_capital * 100
        
        # Trade statistics
        closed_trades = [t for t in trades if t.is_closed]
        total_trades = len(closed_trades)
        
        if total_trades == 0:
            return PerformanceMetrics(total_return=total_return, total_trades=0)
        
        winning_trades = [t for t in closed_trades if t.pnl > 0]
        losing_trades = [t for t in closed_trades if t.pnl <= 0]
        
        win_rate = len(winning_trades) / total_trades * 100 if total_trades > 0 else 0
        
        # Average win/loss
        avg_win = np.mean([t.pnl for t in winning_trades]) if winning_trades else 0
        avg_loss = np.mean([t.pnl for t in losing_trades]) if losing_trades else 0
        
        # Largest win/loss
        largest_win = max([t.pnl for t in winning_trades]) if winning_trades else 0
        largest_loss = min([t.pnl for t in losing_trades]) if losing_trades else 0
        
        # Profit factor
        gross_profit = sum(t.pnl for t in winning_trades)
        gross_loss = abs(sum(t.pnl for t in losing_trades))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
        
        # Maximum Drawdown
        equity_values = [ep.equity for ep in equity_curve]
        peak = equity_values[0]
        max_dd = 0
        for eq in equity_values:
            if eq > peak:
                peak = eq
            dd = (peak - eq) / peak * 100
            if dd > max_dd:
                max_dd = dd
        
        # Sharpe Ratio (simplified, assuming daily returns)
        returns = []
        for i in range(1, len(equity_values)):
            ret = (equity_values[i] - equity_values[i-1]) / equity_values[i-1]
            returns.append(ret)
        
        sharpe = 0.0
        if returns and np.std(returns) > 0:
            sharpe = np.mean(returns) / np.std(returns) * np.sqrt(252)  # Annualized
        
        # Sortino Ratio
        negative_returns = [r for r in returns if r < 0]
        sortino = 0.0
        if negative_returns and np.std(negative_returns) > 0:
            sortino = np.mean(returns) / np.std(negative_returns) * np.sqrt(252)
        
        # === NEW METRICS ===
        
        # Holding time calculation (in bars, approximated from timestamps)
        holding_times = []
        win_holding_times = []
        loss_holding_times = []
        for t in closed_trades:
            if t.entry_time and t.exit_time:
                # Assuming daily bars = 86400000 ms
                bars = max(1, (t.exit_time - t.entry_time) // 86400000)
                holding_times.append(bars)
                if t.pnl > 0:
                    win_holding_times.append(bars)
                else:
                    loss_holding_times.append(bars)
        
        avg_holding_time = np.mean(holding_times) if holding_times else 0
        avg_win_holding = np.mean(win_holding_times) if win_holding_times else 0
        avg_loss_holding = np.mean(loss_holding_times) if loss_holding_times else 0
        
        # Risk/Reward ratio
        risk_reward = abs(avg_win / avg_loss) if avg_loss != 0 else 0
        
        # Consecutive wins/losses
        max_consec_wins = 0
        max_consec_losses = 0
        current_wins = 0
        current_losses = 0
        for t in closed_trades:
            if t.pnl > 0:
                current_wins += 1
                current_losses = 0
                max_consec_wins = max(max_consec_wins, current_wins)
            else:
                current_losses += 1
                current_wins = 0
                max_consec_losses = max(max_consec_losses, current_losses)
        
        # Recovery time from max drawdown
        recovery_bars = 0
        peak = equity_values[0]
        max_dd_idx = 0
        max_dd_value = 0
        for i, eq in enumerate(equity_values):
            if eq > peak:
                peak = eq
            dd = (peak - eq) / peak
            if dd > max_dd_value:
                max_dd_value = dd
                max_dd_idx = i
        
        # Find when we recovered from max DD
        if max_dd_idx > 0:
            dd_peak = max(equity_values[:max_dd_idx+1])
            for i in range(max_dd_idx, len(equity_values)):
                if equity_values[i] >= dd_peak:
                    recovery_bars = i - max_dd_idx
                    break
        
        # Worst single day PnL
        worst_day = min(returns) * 100 if returns else 0
        
        # Commission Stats
        total_pnl = sum(t.pnl for t in closed_trades)
        total_commission = sum((t.entry_price * t.quantity * 0.001) + (t.exit_price * t.quantity * 0.001) for t in closed_trades if t.exit_price) # Approximate if not recorded
        # Better: use the actual commission we might have stored, but Trade model doesn't store commission directly yet.
        # We'll approximate from PnL difference if needed, but BacktestRunner calculates it.
        # For now, let's assume PnL is Net. Gross would be PnL + Comm.
        # Let's add commission tracking to Trade model in future. For now, set to 0 or estimated.
        commission_total = 0.0 
        commission_pct = 0.0
        
        # Market Regime (Trend vs Range) - Simple Heuristic
        # Trend: Close > SMA(50)
        # We need the full price series for this. `equity_curve` implies time, but we don't have price history here easily.
        # We'll skip complex implementation here and leave it for the Runner to populate if needed.
        
        # Top 10 wins and losses
        sorted_wins = sorted(winning_trades, key=lambda t: t.pnl, reverse=True)[:10]
        sorted_losses = sorted(losing_trades, key=lambda t: t.pnl)[:10]
        
        top_10_wins = [{"pnl": t.pnl, "entry_time": t.entry_time, "exit_time": t.exit_time} for t in sorted_wins]
        top_10_losses = [{"pnl": t.pnl, "entry_time": t.entry_time, "exit_time": t.exit_time} for t in sorted_losses]
        
        # Monthly returns (simplified - group by month from timestamps)
        from datetime import datetime
        monthly = {}
        for i in range(1, len(equity_curve)):
            ts = equity_curve[i].timestamp
            try:
                from datetime import timezone
                dt = datetime.fromtimestamp(ts / 1000, tz=timezone.utc)
                month_key = dt.strftime("%Y-%m")
                if month_key not in monthly:
                    monthly[month_key] = {"start": equity_curve[i-1].equity, "end": equity_curve[i].equity}
                else:
                    monthly[month_key]["end"] = equity_curve[i].equity
            except:
                pass
        
        monthly_returns = {}
        for month, vals in monthly.items():
            if vals["start"] > 0:
                monthly_returns[month] = (vals["end"] - vals["start"]) / vals["start"] * 100
        
        # Advanced Analysis: Entry Conditions
        entry_analysis = {}
        # Collect all keys present in entry_context
        all_keys = set()
        for t in trades:
            if t.entry_context:
                all_keys.update(t.entry_context.keys())
        
        for key in all_keys:
            win_values = [t.entry_context[key] for t in trades if t.pnl > 0 and t.entry_context and key in t.entry_context and t.entry_context[key] is not None]
            loss_values = [t.entry_context[key] for t in trades if t.pnl <= 0 and t.entry_context and key in t.entry_context and t.entry_context[key] is not None]
            
            stats = {
                'win_avg': float(np.mean(win_values)) if win_values else 0.0,
                'loss_avg': float(np.mean(loss_values)) if loss_values else 0.0,
                'win_std': float(np.std(win_values)) if win_values else 0.0,
                'loss_std': float(np.std(loss_values)) if loss_values else 0.0
            }

            entry_analysis[key] = stats

        # Advanced Analysis: Regime Performance
        regime_performance = {}
        if equity_curve and len(equity_curve) > 1:
            regime_returns = {} # {regime: [daily_returns]}
            
            for i in range(1, len(equity_curve)):
                prev = equity_curve[i-1]
                curr = equity_curve[i]
                
                # Calculate period return
                ret = (curr.equity - prev.equity) / prev.equity if prev.equity > 0 else 0.0
                regime = curr.regime
                
                if regime not in regime_returns:
                    regime_returns[regime] = []
                regime_returns[regime].append(ret)
            
            # Aggregate
            for regime, rets in regime_returns.items():
                # Avoid calculating total return by compounding, just mean daily return for MVP
                # Or cumulative return? Let's do Cumulative for that regime
                cum_ret = 1.0
                for r in rets:
                    cum_ret *= (1 + r)
                regime_performance[regime] = (cum_ret - 1.0) * 100
        else:
             regime_performance = {"Normal": 0.0}

        return PerformanceMetrics(
            total_return=total_return,
            sharpe_ratio=sharpe,
            sortino_ratio=sortino,
            max_drawdown=max_dd,
            win_rate=win_rate,
            profit_factor=profit_factor if profit_factor != float('inf') else 999.0,
            total_trades=total_trades,
            winning_trades=len(winning_trades),
            losing_trades=len(losing_trades),
            avg_win=avg_win,
            avg_loss=avg_loss,
            largest_win=largest_win,
            largest_loss=largest_loss,
            # Enhanced Metrics
            avg_holding_time_bars=avg_holding_time,
            avg_win_holding_time=avg_win_holding,
            avg_loss_holding_time=avg_loss_holding,
            risk_reward_ratio=risk_reward,
            max_consecutive_wins=max_consec_wins,
            max_consecutive_losses=max_consec_losses,
            recovery_time_bars=recovery_bars,
            worst_single_day_pnl=worst_day,
            commission_total=commission_total,
            commission_pct_of_pnl=commission_pct,
            top_10_wins=top_10_wins,
            top_10_losses=top_10_losses,
            monthly_returns=monthly_returns if monthly_returns else None,
            entry_analysis=entry_analysis if entry_analysis else None,
            regime_performance=regime_performance if regime_performance else None
        )
