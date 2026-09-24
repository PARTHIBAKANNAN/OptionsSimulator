import sys, asyncio, asyncpg
sys.path.insert(0, '/home/ubuntu/optionssimulator-app')
from backend.app.config import WebConfig

async def main():
    cfg = WebConfig.load()
    conn = await asyncpg.connect(cfg.supabase_db_url)
    row = await conn.fetchrow(
        "SELECT * FROM options_positions WHERE order_id = 'a34aff6e-12de-4a26-a649-ee58e5f93da7'"
    )
    if row:
        for k, v in dict(row).items():
            print(f'{k}: {v}')
    else:
        print("Order not found")
    await conn.close()

if __name__ == '__main__':
    asyncio.run(main())
