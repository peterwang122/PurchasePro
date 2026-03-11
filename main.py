from purchase_pro.config import load_config
from purchase_pro.db import Database
from purchase_pro.monitor import ProductMonitor


def main() -> None:
    config = load_config()
    db = Database(config)
    try:
        ProductMonitor(config, db).run_forever()
    finally:
        db.close()


if __name__ == "__main__":
    main()
