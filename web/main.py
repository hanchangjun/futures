from fastapi import FastAPI, Depends, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, PlainTextResponse
from sqlalchemy.orm import Session
from typing import List, Optional
import uvicorn
import os
import sys
import csv
import io
import json
from datetime import timedelta

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.connection import get_db, engine, Base
from database.models import StockBar, ChanSignal, BacktestResult, TradeRecord
from scripts.import_data import run_import
from strategy.chan_strategy import run_strategy
from datafeed.base import parse_timestamp, PriceBar
from pydantic import BaseModel
from datetime import datetime
from strategy.real_time import RealTimeTradingSystem

# 自动创建表
Base.metadata.create_all(bind=engine)

app = FastAPI(title="ChanQuant System")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static Files & Templates
app.mount("/static", StaticFiles(directory="web/static"), name="static")
templates = Jinja2Templates(directory="web/templates")

class ActionRequest(BaseModel):
    symbol: str
    period: str
    count: int = 2000
    days: Optional[int] = 30
    filter_period: Optional[str] = None
    tq_user: Optional[str] = None
    tq_pass: Optional[str] = None
    strategy_name: Optional[str] = "standard"

@app.get("/api/trades")
def get_trades(
    symbol: Optional[str] = None, 
    status: Optional[str] = None, 
    limit: int = 100, 
    db: Session = Depends(get_db)
):
    """
    Get trade history
    """
    query = db.query(TradeRecord)
    if symbol:
        query = query.filter(TradeRecord.symbol == symbol)
    if status:
        query = query.filter(TradeRecord.status == status)
        
    trades = query.order_by(TradeRecord.entry_time.desc()).limit(limit).all()
    return {"data": trades}

@app.get("/api/export/bars/{symbol}/{period}")
def export_bars(symbol: str, period: str, days: int = 365, db: Session = Depends(get_db)):
    """
    Export bars for a specific symbol and period within the last N days to CSV.
    """
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    
    # Query bars
    bars = db.query(StockBar).filter(
        StockBar.symbol == symbol,
        StockBar.period == period,
        StockBar.dt >= start_date
    ).order_by(StockBar.dt.asc()).all()
    
    # Create CSV in memory
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow(['dt', 'symbol', 'period', 'open', 'high', 'low', 'close', 'volume', 'amount'])
    
    # Write data
    for bar in bars:
        writer.writerow([
            bar.dt,
            bar.symbol,
            bar.period,
            bar.open,
            bar.high,
            bar.low,
            bar.close,
            bar.volume,
            bar.amount
        ])
    
    output.seek(0)
    
    filename = f"{symbol}_{period}_{datetime.now().strftime('%Y%m%d')}.csv"
    
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode('utf-8-sig')), # use utf-8-sig for Excel compatibility
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@app.get("/")
def dashboard(request: Request):
    response = templates.TemplateResponse("index.html", {"request": request})
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

@app.get("/api/bars/{symbol}/{period}")
def read_bars(symbol: str, period: str, limit: int = 1000, db: Session = Depends(get_db)):
    bars = db.query(StockBar).filter(
        StockBar.symbol == symbol,
        StockBar.period == period
    ).order_by(StockBar.dt.desc()).limit(limit).all()
    return bars[::-1]

@app.get("/api/signals")
def read_signals(symbol: Optional[str] = None, period: Optional[str] = None, signal_type: Optional[str] = None, page: int = 1, limit: int = 20, db: Session = Depends(get_db)):
    query = db.query(ChanSignal).order_by(ChanSignal.dt.desc())
    if symbol:
        query = query.filter(ChanSignal.symbol == symbol)
    if period:
        query = query.filter(ChanSignal.period == period)
    if signal_type:
        # Support comma-separated list: "1B,2B"
        if ',' in signal_type:
            types = [t.strip() for t in signal_type.split(',')]
            query = query.filter(ChanSignal.signal_type.in_(types))
        else:
            query = query.filter(ChanSignal.signal_type == signal_type)
    
    total = query.count()
    offset = (page - 1) * limit
    signals = query.offset(offset).limit(limit).all()
    
    data = []
    for s in signals:
        data.append({
            "dt": s.dt,
            "symbol": s.symbol,
            "period": s.period,
            "signal_type": s.signal_type,
            "price": s.price,
            "description": s.desc
        })
    return {
        "total": total,
        "page": page,
        "limit": limit,
        "data": data
    }

@app.get("/api/docs/strategy")
def read_strategy_docs():
    try:
        with open("docs/缠论策略说明.md", "r", encoding="utf-8") as f:
            content = f.read()
        return PlainTextResponse(content)
    except Exception as e:
        return PlainTextResponse(f"Error loading documentation: {str(e)}", status_code=500)

@app.get("/api/analysis/{symbol}/{period}")
def analyze_symbol(symbol: str, period: str, limit: int = 1000, strategy_name: str = "standard", db: Session = Depends(get_db)):
    try:
        # 1. Get Bars
        bars_db = db.query(StockBar).filter(
            StockBar.symbol == symbol,
            StockBar.period == period
        ).order_by(StockBar.dt.desc()).limit(limit).all()
        
        if not bars_db:
            return {"centers": [], "bis": []}
            
        bars_db = bars_db[::-1] # Sort asc
        
        # Convert to PriceBar
        bars = []
        for b in bars_db:
            bars.append(PriceBar(
                date=parse_timestamp(b.dt),
                open=b.open,
                high=b.high,
                low=b.low,
                close=b.close,
                volume=b.volume
            ))
            
        # 2. Chan Calculations
        from chan.k_merge import merge_klines
        chan_bars = merge_klines(bars)
        
        bis = []
        centers = []
        signals = []
        
        if strategy_name == "pure_chan":
            from strategy.pure_chan_strategy import PureChanTheoryEngine, calculate_macd, PureChanStrategy
            
            # Use PureChanStrategy wrapper if possible, or manually call steps
            # Here we need intermediate results (centers, bis) which PureChanStrategy.run() doesn't return (it returns signals)
            # So we reproduce steps manually or modify PureChanStrategy to expose them.
            # Manual reproduction is safer for now to avoid changing PureChanStrategy signature again.
            
            engine = PureChanTheoryEngine(symbol)
            
            # Calculate MACD
            difs, deas, macd_bars = calculate_macd(bars)
            
            fractals = engine.detect_fractal(chan_bars, level='standard')
            bis = engine.construct_bi(fractals, chan_bars, difs, deas, macd_bars)
            centers = engine.identify_segment_and_zhongshu(bis)
            
            # Use PureChanStrategy to get signals
            strat = PureChanStrategy(symbol, period)
            signals = strat.run(bars)

        elif strategy_name == "rebar":
            from strategy.rebar_strategy import RebarOptimizedChanSystem
            
            strat = RebarOptimizedChanSystem()
            strat.analyze(bars)
            
            # Get results directly from strategy instance
            bis = strat.笔列表
            centers = strat.中枢列表
            raw_signals = strat.买卖点记录
            
            # Serialize immediately for Rebar Strategy (different object structure)
            res_bis = []
            for b in bis:
                res_bis.append({
                    "start_dt": b.start_time.isoformat() if hasattr(b.start_time, 'isoformat') else str(b.start_time),
                    "start_price": b.start_price,
                    "end_dt": b.end_time.isoformat() if hasattr(b.end_time, 'isoformat') else str(b.end_time),
                    "end_price": b.end_price,
                    "direction": "Trend.UP" if b.direction == 'up' else "Trend.DOWN"
                })
                
            res_centers = []
            for c in centers:
                res_centers.append({
                    "zg": c.ZG,
                    "zd": c.ZD,
                    "start_dt": c.start_time.isoformat() if hasattr(c.start_time, 'isoformat') else str(c.start_time),
                    "end_dt": c.end_time.isoformat() if hasattr(c.end_time, 'isoformat') else str(c.end_time)
                })
                
            res_signals = []
            for s in raw_signals:
                res_signals.append({
                    "type": s.type,
                    "price": s.price,
                    "dt": s.time.isoformat() if hasattr(s.time, 'isoformat') else str(s.time),
                    "desc": f"Score: {s.score:.1f} {s.extra_info}",
                    "score": s.score
                })
                
            return {
                "centers": res_centers,
                "bi_list": res_bis,
                "bis_count": len(bis),
                "strategy": strategy_name,
                "signals": res_signals
            }
            
        else:
            # Standard Strategy
            from chan.fractal import find_fractals
            from chan.bi import find_bi
            from chan.center import find_zhongshu
            
            fractals = find_fractals(chan_bars)
            bis = find_bi(chan_bars, fractals)
            centers = find_zhongshu(bis)

            # Calculate Signals
            from strategy.chan_strategy import ChanStrategy
            strat = ChanStrategy(symbol, period)
            signals = strat.run(bars)
        
        # 3. Serialize
        res_centers = []
        for c in centers:
            # Get start and end time from Bi
            if c.start_bi_index >= len(bis) or c.end_bi_index >= len(bis):
                continue
                
            start_bi = bis[c.start_bi_index]
            end_bi = bis[c.end_bi_index]
            
            # Defensive coding for date attribute
            s_date = getattr(start_bi.start_fx, 'date', getattr(start_bi.start_fx, 'dt', None))
            e_date = getattr(end_bi.end_fx, 'date', getattr(end_bi.end_fx, 'dt', None))
            
            if s_date is None or e_date is None:
                continue

            res_centers.append({
                "zg": c.zg,
                "zd": c.zd,
                "start_dt": s_date.isoformat(),
                "end_dt": e_date.isoformat()
            })
            
        # Serialize Bis
        res_bis = []
        for b in bis:
            res_bis.append({
                "start_dt": b.start_fx.date.isoformat(),
                "start_price": b.start_fx.price,
                "end_dt": b.end_fx.date.isoformat(),
                "end_price": b.end_fx.price,
                "direction": str(b.direction)
            })

        return {
            "centers": res_centers,
            "bi_list": res_bis,
            "bis_count": len(bis),
            "strategy": strategy_name,
            "signals": signals
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"centers": [], "bis_count": 0, "error": str(e)}


@app.post("/api/action/import")
def trigger_import(action: ActionRequest):
    # Calculate count from days if needed
    count = action.count
    if action.days and action.days > 0:
        # Approximate bars per day based on period
        bars_per_day = 1
        p = action.period.lower()
        if p.endswith("m") or p.endswith("min"):
            minutes = int(''.join(filter(str.isdigit, p)))
            # Assuming ~10 hours of trading per day for futures (generous buffer)
            # 10 * 60 = 600 minutes
            bars_per_day = int(600 / minutes)
        elif p.endswith("h"):
            hours = int(''.join(filter(str.isdigit, p)))
            bars_per_day = int(10 / hours)
        elif p == "1d" or p == "day":
            bars_per_day = 1
            
        # Add buffer
        estimated_count = action.days * bars_per_day
        # Use the larger of count or estimated_count if count was default
        if estimated_count > count:
            count = estimated_count
            
    success = run_import(
        symbol=action.symbol,
        period=action.period,
        count=count,
        tq_user=action.tq_user,
        tq_pass=action.tq_pass
    )
    return {"status": "success" if success else "failed", "message": f"Import finished (requested {count} bars)"}

@app.post("/api/action/strategy")
def trigger_strategy(action: ActionRequest):
    count = run_strategy(
        symbol=action.symbol,
        period=action.period,
        count=action.count,
        source="db", # Default to DB for strategy run
        strategy_name=action.strategy_name
    )
    return {"status": "success", "message": f"Strategy executed. Generated {count} signals."}

@app.post("/api/action/simple_backtest")
def trigger_simple_backtest(action: ActionRequest, db: Session = Depends(get_db)):
    """
    Run the vectorized simple swing strategy backtest.
    """
    from strategy.simple_backtest import run_simple_swing_strategy
    
    try:
        result = run_simple_swing_strategy(
            symbol=action.symbol,
            period=action.period,
            db=db,
            days=action.days if action.days else 365
        )
        
        if "error" in result:
            return {"status": "error", "message": result["error"]}
            
        return {"status": "success", "result": result}
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"status": "error", "message": str(e)}

@app.post("/api/action/backtest")
def trigger_backtest(action: ActionRequest, db: Session = Depends(get_db)):
    from types import SimpleNamespace
    from runner.event_backtest import run_event_backtest
    
    # Mock args object
    args = SimpleNamespace(
        symbol=action.symbol,
        period=action.period,
        source="db", # Default to DB for web backtest
        tq_username=action.tq_user,
        tq_password=action.tq_pass,
        tq_count=action.count,
        tdx_count=action.count,
        csv_dir=".",
        csv_path=None,
        tdx_host="119.147.212.81",
        tdx_port=7727,
        tdx_market=None,
        debug=False,
        equity=50000.0,
        slow=60,
        atr=14,
        days=action.days,
        filter_period=action.filter_period,
        strategy_name=action.strategy_name
    )
    
    try:
        result = run_event_backtest(args)
        
        # Serialize trades (convert datetime to string for JSON storage)
        trades = result.get('trades', [])
        safe_trades = []
        for t in trades:
            t_copy = t.copy()
            if 'dt' in t_copy and isinstance(t_copy['dt'], datetime):
                t_copy['dt'] = t_copy['dt'].isoformat()
            safe_trades.append(t_copy)

        # Save to DB
        db_result = BacktestResult(
            symbol=action.symbol,
            period=action.period,
            days=action.days,
            filter_period=action.filter_period,
            start_dt=datetime.now(), # Approximate, or extract from result if available
            end_dt=datetime.now(),
            initial_capital=result.get('initial_capital', 0),
            final_equity=result.get('final_equity', 0),
            pnl=result.get('pnl', 0),
            roi=result.get('roi', 0),
            total_trades=result.get('total_trades', 0),
            win_rate=result.get('win_rate', 0),
            trades=safe_trades,
            logs=result.get('logs', []),
            positions=result.get('positions', {})
        )
        db.add(db_result)
        db.commit()
        db.refresh(db_result)
        
        return {"status": "success", "result": result, "db_id": db_result.id}
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"status": "error", "message": str(e)}

@app.get("/api/backtests")
def read_backtests(limit: int = 10, db: Session = Depends(get_db)):
    results = db.query(BacktestResult).order_by(BacktestResult.created_at.desc()).limit(limit).all()
    return results

@app.get("/api/docs/file/{filename}")
def read_doc_file(filename: str):
    """
    Read a markdown documentation file from the docs directory.
    """
    safe_filename = os.path.basename(filename)
    file_path = os.path.join("docs", safe_filename)
    
    if not os.path.exists(file_path):
        return PlainTextResponse(f"File not found: {safe_filename}", status_code=404)
        
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        return PlainTextResponse(content)
    except Exception as e:
        return PlainTextResponse(f"Error reading file: {str(e)}", status_code=500)

@app.get("/api/config/rebar")
def get_rebar_config():
    """
    Get Rebar Strategy Configuration (params.json).
    """
    config_path = "strategy/rebar/params.json"
    if not os.path.exists(config_path):
        return {"error": "Config file not found"}
    
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        return {"error": f"Failed to load config: {str(e)}"}

@app.post("/api/config/rebar")
async def update_rebar_config(request: Request):
    """
    Update Rebar Strategy Configuration.
    """
    config_path = "strategy/rebar/params.json"
    try:
        new_config = await request.json()
        # Basic validation: check if it's a dict
        if not isinstance(new_config, dict):
             return {"error": "Invalid config format", "status": "failed"}
             
        # Write to file
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(new_config, f, indent=4, ensure_ascii=False)
            
        return {"status": "success", "message": "Config updated successfully"}
    except Exception as e:
        return {"error": f"Failed to update config: {str(e)}", "status": "failed"}

@app.get("/api/test/run")
def run_system_diagnostics(type: str = "full"):
    """
    Triggers the integration test suite and returns the report.
    type: 'full', 'signal_filter', 'rebar', 'real_time'
    """
    try:
        # Import here to avoid circular dependency
        # Ensure tests package is in path
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        # Always promote project root to top of path to ensure local tests package is found
        if project_root in sys.path:
            sys.path.remove(project_root)
        sys.path.insert(0, project_root)
            
        import tests.integration_test
        from tests.integration_test import run_diagnostics
        
        result = run_diagnostics(type)
        return result
    except Exception as e:
        import traceback
        debug_info = f"sys.path: {sys.path}\nProject Root: {project_root}\nRoot Contents: {os.listdir(project_root)}"
        return {
            "status": "ERROR",
            "report": f"Failed to run tests: {str(e)}\n\nDebug Info:\n{debug_info}\n\nTraceback:\n{traceback.format_exc()}",
            "timestamp": datetime.now().isoformat()
        }

class RealtimeStartRequest(BaseModel):
    symbol: str
    data_source: str = "tdx"
    webhook_url: Optional[str] = None

_RTS_INSTANCE: Optional[RealTimeTradingSystem] = None

@app.get("/api/realtime/status")
def realtime_status():
    global _RTS_INSTANCE
    if _RTS_INSTANCE and _RTS_INSTANCE.running:
        return {
            "running": True,
            "symbol": _RTS_INSTANCE.symbol,
            "period": _RTS_INSTANCE.period,
            "data_source": _RTS_INSTANCE.data_source,
            "update_interval": _RTS_INSTANCE.update_interval,
            "last_signal_time": _RTS_INSTANCE.last_signal_time
        }
    return {"running": False}

@app.post("/api/realtime/start")
def realtime_start(req: RealtimeStartRequest):
    global _RTS_INSTANCE
    if _RTS_INSTANCE and _RTS_INSTANCE.running:
        return {"status": "already_running"}
    try:
        _RTS_INSTANCE = RealTimeTradingSystem(
            symbol=req.symbol,
            webhook_url=req.webhook_url,
            data_source=req.data_source
        )
        _RTS_INSTANCE.start(background=True)
        return {"status": "started", "symbol": req.symbol, "data_source": req.data_source}
    except Exception as e:
        return {"status": "error", "error": str(e)}

@app.post("/api/realtime/stop")
def realtime_stop():
    global _RTS_INSTANCE
    if not _RTS_INSTANCE or not _RTS_INSTANCE.running:
        return {"status": "not_running"}
    try:
        _RTS_INSTANCE.stop()
        return {"status": "stopped"}
    except Exception as e:
        return {"status": "error", "error": str(e)}

@app.on_event("startup")
async def _auto_start_realtime():
    try:
        auto = os.getenv("REALTIME_AUTO_START", "false").lower() in ("1", "true", "yes", "y")
        if not auto:
            return
        symbol = os.getenv("REALTIME_SYMBOL", "rb2505")
        source = os.getenv("REALTIME_SOURCE", "tdx")
        webhook = os.getenv("REALTIME_WEBHOOK", None)
        global _RTS_INSTANCE
        if not _RTS_INSTANCE or not _RTS_INSTANCE.running:
            _RTS_INSTANCE = RealTimeTradingSystem(
                symbol=symbol,
                webhook_url=webhook,
                data_source=source
            )
            _RTS_INSTANCE.start(background=True)
    except Exception:
        pass

@app.on_event("shutdown")
async def _auto_stop_realtime():
    try:
        global _RTS_INSTANCE
        if _RTS_INSTANCE and _RTS_INSTANCE.running:
            _RTS_INSTANCE.stop()
    except Exception:
        pass

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
