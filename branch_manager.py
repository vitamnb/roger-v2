# branch_manager.py -- Freqtrade Strategy Branch Manager
# Manages isolated Freqtrade instances for parallel strategy testing

import os, sys, json, shutil, subprocess, argparse, time, sqlite3
from datetime import datetime

BASE_DIR = r"C:\Users\vitamnb\.openclaw\freqtrade"
USER_DATA = os.path.join(BASE_DIR, "user_data")
BRANCH_DIR = os.path.join(BASE_DIR, "branches")
MAIN_CONFIG = os.path.join(USER_DATA, "config.json")
MAIN_STRATEGY = os.path.join(USER_DATA, "strategies", "roger_strategy.py")
MAIN_DB = os.path.join(BASE_DIR, "tradesv3.dryrun.sqlite")
BASE_PORT = 8082

os.makedirs(BRANCH_DIR, exist_ok=True)

def load_json(path):
    with open(path) as f:
        return json.load(f)

def save_json(path, data):
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)

def get_branch_config(name):
    return os.path.join(BRANCH_DIR, name, "config.json")

def get_branch_strategy(name):
    return os.path.join(BRANCH_DIR, name, "strategies", "roger_strategy.py")

def get_branch_db(name):
    return os.path.join(BRANCH_DIR, name, "tradesv3.dryrun.sqlite")

def get_branch_state(name):
    path = os.path.join(BRANCH_DIR, name, "state.json")
    if os.path.exists(path):
        return load_json(path)
    return {}

def save_branch_state(name, state):
    path = os.path.join(BRANCH_DIR, name, "state.json")
    save_json(path, state)

def get_port(name):
    """Deterministic port assignment based on branch name hash."""
    return BASE_PORT + (hash(name) % 1000)

def branch_exists(name):
    return os.path.exists(os.path.join(BRANCH_DIR, name))

def create_branch(name, from_strategy=None, from_config=None, description=""):
    """Create a new branch from base or existing strategy."""
    if branch_exists(name):
        print(f"[FAIL] Branch '{name}' already exists.")
        return False

    branch_path = os.path.join(BRANCH_DIR, name)
    os.makedirs(os.path.join(branch_path, "strategies"), exist_ok=True)

    # Copy strategy
    src_strategy = from_strategy or MAIN_STRATEGY
    shutil.copy2(src_strategy, get_branch_strategy(name))

    # Copy and modify config
    src_config = from_config or MAIN_CONFIG
    config = load_json(src_config)
    config["bot_name"] = f"Roger Branch - {name}"
    port = get_port(name)
    config["api_server"]["listen_port"] = port
    config["db_url"] = f"sqlite:///{get_branch_db(name)}"
    config["user_data_dir"] = branch_path
    save_json(get_branch_config(name), config)

    # Initialize state
    state = {
        "name": name,
        "created": datetime.utcnow().isoformat(),
        "description": description,
        "port": port,
        "status": "created",
        "base_strategy": os.path.basename(src_strategy),
    }
    save_branch_state(name, state)

    print(f"[OK] Branch '{name}' created at port {port}")
    print(f"     Config: {get_branch_config(name)}")
    print(f"     Strategy: {get_branch_strategy(name)}")
    print(f"     DB: {get_branch_db(name)}")
    print(f"     Start: freqtrade trade --config {get_branch_config(name)} --strategy RogerStrategy")
    return True

def list_branches():
    """List all branches with status and PnL."""
    branches = []
    if not os.path.exists(BRANCH_DIR):
        print("No branches directory found.")
        return

    for name in sorted(os.listdir(BRANCH_DIR)):
        path = os.path.join(BRANCH_DIR, name)
        if not os.path.isdir(path):
            continue

        state = get_branch_state(name)
        port = state.get("port", get_port(name))
        status = state.get("status", "unknown")
        desc = state.get("description", "")

        # Check if process is running
        pid_file = os.path.join(path, "freqtrade.pid")
        running = os.path.exists(pid_file)
        if running:
            try:
                with open(pid_file) as f:
                    pid = int(f.read().strip())
                # Check if process exists
                import psutil
                running = psutil.pid_exists(pid)
            except:
                running = False

        # Get PnL from DB
        pnl = "N/A"
        db_path = get_branch_db(name)
        if os.path.exists(db_path):
            try:
                conn = sqlite3.connect(db_path)
                cur = conn.cursor()
                cur.execute("SELECT COUNT(*), SUM(profit_ratio) FROM trades WHERE is_open=0")
                total, sum_pnl = cur.fetchone()
                if sum_pnl:
                    pnl = f"{sum_pnl*100:+.2f}% ({total} trades)"
                else:
                    pnl = f"0.00% ({total} trades)"
                conn.close()
            except Exception as e:
                pnl = f"err: {e}"

        branches.append({
            "name": name,
            "port": port,
            "running": running,
            "status": "live" if running else status,
            "pnl": pnl,
            "desc": desc[:60],
        })

    if not branches:
        print("No branches found.")
        return

    print(f"\n{'Name':<20} {'Port':<6} {'Status':<8} {'PnL':<25} {'Description':<40}")
    print("-" * 100)
    for b in branches:
        print(f"{b['name']:<20} {b['port']:<6} {b['status']:<8} {b['pnl']:<25} {b['desc']:<40}")
    print()

def compare_branches():
    """Compare all branches by PnL and trade count."""
    results = []
    for name in sorted(os.listdir(BRANCH_DIR)):
        path = os.path.join(BRANCH_DIR, name)
        if not os.path.isdir(path):
            continue

        db_path = get_branch_db(name)
        if not os.path.exists(db_path):
            continue

        try:
            conn = sqlite3.connect(db_path)
            cur = conn.cursor()

            # Closed trades
            cur.execute("SELECT COUNT(*), SUM(profit_ratio), AVG(profit_ratio) FROM trades WHERE is_open=0")
            closed_count, sum_pnl, avg_pnl = cur.fetchone()
            closed_count = closed_count or 0
            sum_pnl = sum_pnl or 0
            avg_pnl = avg_pnl or 0

            # Open trades
            cur.execute("SELECT COUNT(*) FROM trades WHERE is_open=1")
            open_count = cur.fetchone()[0] or 0

            conn.close()

            results.append({
                "name": name,
                "closed": closed_count,
                "open": open_count,
                "total_pnl": sum_pnl * 100,
                "avg_pnl": avg_pnl * 100,
            })
        except Exception as e:
            print(f"[WARN] Could not read {name}: {e}")

    if not results:
        print("No branches with trade data found.")
        return

    results.sort(key=lambda x: x["total_pnl"], reverse=True)

    print(f"\n{'Rank':<5} {'Branch':<20} {'Closed':<7} {'Open':<5} {'Total PnL':<12} {'Avg/Trade':<12}")
    print("-" * 65)
    for i, r in enumerate(results):
        print(f"{i+1:<5} {r['name']:<20} {r['closed']:<7} {r['open']:<5} {r['total_pnl']:>+10.2f}% {r['avg_pnl']:>+10.2f}%")
    print()

def delete_branch(name):
    """Delete a branch and all its data."""
    if not branch_exists(name):
        print(f"[FAIL] Branch '{name}' does not exist.")
        return False

    path = os.path.join(BRANCH_DIR, name)
    state = get_branch_state(name)
    running = state.get("status") == "live"

    if running:
        print(f"[WARN] Branch '{name}' appears to be running. Stop it first.")
        return False

    shutil.rmtree(path)
    print(f"[OK] Branch '{name}' deleted.")
    return True

def promote_branch(name):
    """Promote a branch strategy to main."""
    if not branch_exists(name):
        print(f"[FAIL] Branch '{name}' does not exist.")
        return False

    src_strategy = get_branch_strategy(name)
    if not os.path.exists(src_strategy):
        print(f"[FAIL] Strategy file not found: {src_strategy}")
        return False

    # Backup main
    backup = MAIN_STRATEGY + ".backup." + datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    shutil.copy2(MAIN_STRATEGY, backup)

    # Promote
    shutil.copy2(src_strategy, MAIN_STRATEGY)
    print(f"[OK] Branch '{name}' strategy promoted to MAIN.")
    print(f"     Backup saved: {backup}")
    print(f"     Restart Freqtrade (core) to use the new strategy.")
    return True

def main():
    parser = argparse.ArgumentParser(description="Freqtrade Strategy Branch Manager")
    sub = parser.add_subparsers(dest="cmd")

    create = sub.add_parser("create", help="Create a new branch")
    create.add_argument("name", help="Branch name")
    create.add_argument("--from-strategy", help="Source strategy file (default: main)")
    create.add_argument("--from-config", help="Source config file (default: main)")
    create.add_argument("--desc", default="", help="Description")

    sub.add_parser("list", help="List all branches")
    sub.add_parser("compare", help="Compare branches by PnL")

    delete = sub.add_parser("delete", help="Delete a branch")
    delete.add_argument("name", help="Branch name")

    promote = sub.add_parser("promote", help="Promote branch strategy to main")
    promote.add_argument("name", help="Branch name")

    args = parser.parse_args()

    if args.cmd == "create":
        create_branch(args.name, args.from_strategy, args.from_config, args.desc)
    elif args.cmd == "list":
        list_branches()
    elif args.cmd == "compare":
        compare_branches()
    elif args.cmd == "delete":
        delete_branch(args.name)
    elif args.cmd == "promote":
        promote_branch(args.name)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
